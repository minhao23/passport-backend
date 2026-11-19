"""Compare native output hashes and process peak RSS in fresh processes."""

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path


def reference_person_alpha(runtime, image, check_cancelled):
    """The pre-runtime-tuning detection path, including its retained caches."""
    import cv2
    import numpy as np

    from errors import LowConfidenceError, PersonNotDetectedError

    height, width = image.shape[:2]
    with runtime.yolo_lock:
        check_cancelled()
        result = runtime.get_detector().predict(image, conf=0.1, verbose=False)[0]
    check_cancelled()
    if len(result.boxes) == 0 or int(result.boxes.cls[0].item()) != 0:
        raise PersonNotDetectedError()
    if result.boxes.conf[0].item() < 0.65:
        raise LowConfidenceError()
    if result.masks is not None:
        mask = result.masks.data[0].cpu().numpy()
        mask = cv2.resize(mask, (width, height), interpolation=cv2.INTER_LINEAR)
        return mask.astype(np.float32, copy=False)
    x1, y1, x2, y2 = map(int, result.boxes[0].xyxy[0].cpu().numpy())
    alpha = np.zeros((height, width), dtype=np.float32)
    alpha[y1:y2, x1:x2] = 1.0
    return alpha


def probe(args):
    import resource
    from concurrent.futures import ThreadPoolExecutor
    from contextlib import closing

    import numpy as np
    from PIL import Image
    from rembg import new_session, remove
    from ultralytics import ASSETS

    from errors import LowConfidenceError, PersonNotDetectedError
    from services import image_processor as processor
    from services import model_runtime

    if args.profile == "reference":
        import onnxruntime as ort

        from services.modnet_session import ModnetPortraitSession

        model_runtime.create_rembg_session = lambda name: (
            ModnetPortraitSession(
                name, ort.SessionOptions(), providers=["CPUExecutionProvider"]
            )
            if name == ModnetPortraitSession.name()
            else new_session(name, providers=["CPUExecutionProvider"])
        )
        processor.person_alpha = lambda image, check: reference_person_alpha(
            model_runtime, image, check
        )

    paths = [Path(path) for path in args.image] or [
        ASSETS / "bus.jpg",
        ASSETS / "zidane.jpg",
    ]
    for path in paths:
        if not path.is_file():
            raise FileNotFoundError(f"Missing fixture: {path}; supply --image instead")

    divisor = 1024**2 if sys.platform == "darwin" else 1024

    def peak_mib():
        return round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / divisor, 1)

    report = {
        "profile": args.profile,
        "imports_peak_mib": peak_mib(),
        "mask_hashes": {},
        "jpeg_hashes": {},
        "photo_errors": {},
    }
    model_runtime.load_models()
    report["models_peak_mib"] = peak_mib()

    with ThreadPoolExecutor(max_workers=1) as worker:
        for index, path in enumerate(paths):
            key = f"{index}:{path.name}"
            with Image.open(path) as opened:
                with closing(opened.convert("RGB")) as rgb:

                    def mask_hash():
                        with closing(
                            remove(
                                rgb,
                                session=model_runtime.get_background_session(),
                                only_mask=True,
                            )
                        ) as mask:
                            return hashlib.sha256(
                                np.asarray(mask).tobytes()
                            ).hexdigest()

                    for round_number in range(args.rounds):
                        report["mask_hashes"][f"{key}:{round_number}"] = worker.submit(
                            mask_hash
                        ).result()

            photo = path.read_bytes()
            for round_number in range(args.rounds):
                for country in ("United States", "United Kingdom"):
                    output_key = f"{key}:{round_number}:{country}"
                    try:
                        jpeg = worker.submit(
                            processor.create_passport_photo, photo, country
                        ).result()
                    except PersonNotDetectedError:
                        report["photo_errors"][output_key] = "PERSON_NOT_DETECTED"
                    except LowConfidenceError:
                        report["photo_errors"][output_key] = "LOW_CONFIDENCE"
                    else:
                        report["jpeg_hashes"][output_key] = hashlib.sha256(
                            jpeg
                        ).hexdigest()
            detector = model_runtime.get_detector()
            if args.profile == "optimized" and detector.predictor is not None:
                predictor = detector.predictor
                assert predictor.results is None
                assert predictor.batch is None
                assert predictor.dataset is None

    report["peak_mib"] = peak_mib()
    print("MEMORY_PROBE_RESULT=" + json.dumps(report), flush=True)


def compare(args):
    reports = []
    for profile in ("reference", "optimized"):
        command = [
            sys.executable,
            str(Path(__file__).resolve()),
            "--profile",
            profile,
            "--app-dir",
            args.app_dir,
            "--rounds",
            str(args.rounds),
        ]
        for image in args.image:
            command.extend(["--image", str(Path(image).resolve())])
        environment = os.environ.copy()
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        if profile == "optimized":
            environment.update(
                {
                    "MALLOC_ARENA_MAX": "2",
                    "OMP_NUM_THREADS": "1",
                    "OPENBLAS_NUM_THREADS": "1",
                    "MKL_NUM_THREADS": "1",
                }
            )
        completed = subprocess.run(
            command, env=environment, text=True, capture_output=True, check=True
        )
        lines = [
            line.removeprefix("MEMORY_PROBE_RESULT=")
            for line in completed.stdout.splitlines()
            if line.startswith("MEMORY_PROBE_RESULT=")
        ]
        if len(lines) != 1:
            raise RuntimeError(f"Incomplete native probe: {completed.stdout}")
        reports.append(json.loads(lines[0]))

    reference, optimized = reports
    for field in ("mask_hashes", "jpeg_hashes", "photo_errors"):
        if reference[field] != optimized[field]:
            raise AssertionError(f"Output parity failed: {field}")
    print(
        json.dumps(
            {
                "mask_parity": "PASS",
                "jpeg_parity": "PASS" if optimized["jpeg_hashes"] else "UNVERIFIED",
                "identical_masks": len(optimized["mask_hashes"]),
                "identical_jpegs": len(optimized["jpeg_hashes"]),
                "reference_peak_mib": reference["peak_mib"],
                "optimized_peak_mib": optimized["peak_mib"],
                "peak_reduction_mib": round(
                    reference["peak_mib"] - optimized["peak_mib"], 1
                ),
            },
            indent=2,
        ),
        flush=True,
    )
    if not optimized["jpeg_hashes"] and not args.mask_only:
        raise AssertionError(
            "No accepted portraits; supply representative --image fixtures"
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=("reference", "optimized"))
    parser.add_argument(
        "--app-dir", default=str(Path(__file__).resolve().parents[1] / "src")
    )
    parser.add_argument("--image", action="append", default=[])
    parser.add_argument("--rounds", type=int, default=2)
    parser.add_argument(
        "--mask-only",
        action="store_true",
        help="Allow mask-only parity when YOLO rejects all fixtures; not an end-to-end check",
    )
    arguments = parser.parse_args()
    if arguments.rounds < 1:
        parser.error("--rounds must be positive")
    sys.path.insert(0, str(Path(arguments.app_dir).resolve()))
    try:
        if arguments.profile:
            probe(arguments)
        else:
            compare(arguments)
    except subprocess.CalledProcessError as error:
        print(error.stdout, file=sys.stderr)
        print(error.stderr, file=sys.stderr)
        raise SystemExit(error.returncode) from error
