import asyncio
import io
import json
import unittest
import zlib
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from threading import Event, Lock
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import cv2
import numpy as np
from backend_test_utils import photo_bytes, request_app
from fastapi import UploadFile
from PIL import Image
from starlette.datastructures import Headers

# Unit tests exercise orchestration without importing native inference runtimes.
inference_stubs = patch.dict(
    "sys.modules",
    {
        "rembg": SimpleNamespace(remove=Mock(), new_session=Mock()),
        "ultralytics": SimpleNamespace(YOLO=Mock()),
    },
)
inference_stubs.start()


def tearDownModule():
    # Discovery imports all modules first; the shared cleanup stack can otherwise
    # remove these stubs after a different test module finishes.
    face_stub.stop()
    inference_stubs.stop()


from api import process_image
from errors import (
    ImageDimensionsError,
    InvalidPhotoError,
    LowConfidenceError,
    PersonNotDetectedError,
    ProcessingCancelledError,
    SubjectFramingError,
    SubjectSeparationError,
    SubjectTooSmallError,
    UploadTooLargeError,
)
from main import app
from services import image_processor, model_runtime, segmentation
from services.processing_jobs import ProcessingPool, processing_pool
from utils import image_loading
from utils.image_loading import check_webp_header
from utils.limits import (
    MAX_ACTIVE_JOBS,
    MAX_FILE_BYTES,
    MAX_REQUEST_BYTES,
    MAX_WAITING_JOBS,
    MAX_WORKING_SIDE,
)
from utils.passport_sizes import passport_photo_sizes_mm

face_stub = patch("services.image_processor.detect_face", return_value=None)
face_stub.start()


def webp_chunk(kind, payload):
    return (
        kind + len(payload).to_bytes(4, "little") + payload + b"\0" * (len(payload) & 1)
    )


def webp_container(chunks):
    payload = b"WEBP" + chunks
    return b"RIFF" + len(payload).to_bytes(4, "little") + payload


def person_result(size=(32, 32), confidence=0.9, class_id=0, mask=None):
    boxes = MagicMock()
    boxes.__len__.return_value = 1
    boxes.conf = np.array([confidence])
    boxes.cls = np.array([class_id])
    boxes[0].xyxy[0].cpu().numpy.return_value = np.array([0, 0, *size])
    masks = None
    if mask is not None:
        masks = MagicMock()
        masks.data[0].cpu().numpy.return_value = mask
    return SimpleNamespace(boxes=boxes, masks=masks)


@contextmanager
def mock_pipeline(detector=None, *, size=(32, 32), session=None, **removal):
    if detector is None:
        detector = Mock(predict=Mock(return_value=[person_result(size)]))
    with (
        patch.object(model_runtime, "yolo_model", detector, create=True),
        patch.object(
            model_runtime,
            "rembg_session",
            session if session is not None else object(),
            create=True,
        ),
        patch("rembg.remove", **removal) as remove,
    ):
        yield remove


@contextmanager
def reserved_slots(count=MAX_ACTIVE_JOBS + MAX_WAITING_JOBS):
    permits = [processing_pool.try_acquire() for _ in range(count)]
    try:
        yield permits
    finally:
        for permit in permits:
            if permit is not None:
                permit.release_if_unused()


class WebPHeaderTests(unittest.TestCase):
    def test_oversized_headers_rejected_before_any_decoder(self):
        for width, height in ((5000, 5000), (10001, 1)):
            headers = [
                webp_chunk(
                    b"VP8X",
                    b"\0" * 4
                    + (width - 1).to_bytes(3, "little")
                    + (height - 1).to_bytes(3, "little"),
                ),
                webp_chunk(
                    b"VP8L",
                    b"\x2f"
                    + ((width - 1) | ((height - 1) << 14)).to_bytes(4, "little"),
                ),
                webp_chunk(
                    b"VP8 ",
                    b"\0" * 3
                    + b"\x9d\x01\x2a"
                    + width.to_bytes(2, "little")
                    + height.to_bytes(2, "little"),
                ),
            ]
            for header in headers:
                with (
                    self.subTest(width=width, height=height, kind=header[:4]),
                    patch.object(Image, "open") as pillow,
                    patch.object(cv2, "imdecode") as opencv,
                ):
                    with self.assertRaises(ImageDimensionsError):
                        image_processor.create_passport_photo(
                            webp_container(header), "United States"
                        )
                    pillow.assert_not_called()
                    opencv.assert_not_called()

    def test_small_canvas_cannot_hide_oversized_bitstream(self):
        canvas = webp_chunk(b"VP8X", b"\0" * 10)
        bits = (4999 | (4999 << 14)).to_bytes(4, "little")
        with self.assertRaises(ImageDimensionsError):
            check_webp_header(
                webp_container(canvas + webp_chunk(b"VP8L", b"\x2f" + bits))
            )

    def test_real_still_webp_variants_pass_preflight(self):
        for mode in ("RGB", "RGBA"):
            for lossless in (False, True):
                with self.subTest(mode=mode, lossless=lossless):
                    data = photo_bytes(
                        (32, 48), format="WEBP", mode=mode, color=0, lossless=lossless
                    )
                    check_webp_header(data)
                    self.assertEqual(
                        cv2.imdecode(
                            np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR
                        ).shape[:2],
                        (48, 32),
                    )

    def test_truncated_and_animated_webp_are_rejected(self):
        for data in (
            b"RIFF\0\0\0\0WEBP",
            webp_container(webp_chunk(b"VP8L", b"\x2f")),
            webp_container(webp_chunk(b"VP8X", b"\x02" + b"\0" * 9)),
            webp_container(webp_chunk(b"ANMF", b"\0" * 16)),
        ):
            with self.subTest(data=data), self.assertRaises(InvalidPhotoError):
                check_webp_header(data)


class HeifLoadingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        image_loading._register_heif()

    def test_heic_decodes_bgr_without_opencv_codec_and_bounds_working_size(self):
        data = photo_bytes((1200, 800), format="HEIF", quality=95)
        with patch.object(cv2, "imdecode") as opencv:
            photo, scale = image_loading.decode_photo(data)
        opencv.assert_not_called()
        self.assertEqual(photo.shape, (683, 1024, 3))
        self.assertEqual(scale, 1)
        np.testing.assert_allclose(photo[100, 100], [105, 65, 25], atol=3)

    def test_heic_selects_only_the_primary_photo(self):
        with (
            Image.new("RGB", (48, 32), (200, 0, 0)) as first,
            Image.new("RGB", (32, 48), (0, 0, 200)) as primary,
        ):
            output = io.BytesIO()
            first.save(
                output,
                format="HEIF",
                save_all=True,
                append_images=[primary],
                primary_index=1,
                quality=95,
            )
        photo, _ = image_loading.decode_photo(output.getvalue())
        self.assertEqual(photo.shape, (48, 32, 3))
        np.testing.assert_allclose(photo[10, 10], [200, 0, 0], atol=3)

    def test_heic_orientation_is_applied(self):
        with Image.new("RGB", (48, 32), (20, 60, 100)) as image:
            exif = Image.Exif()
            exif[274] = 6
            output = io.BytesIO()
            image.save(output, format="HEIF", exif=exif.tobytes(), quality=95)
        photo, _ = image_loading.decode_photo(output.getvalue())
        self.assertEqual(photo.shape, (48, 32, 3))

    def test_oversized_heic_is_rejected_before_loading_pixels(self):
        header = MagicMock()
        header.format = "HEIF"
        header.size = (5000, 4001)
        header.__enter__.return_value = header
        with (
            patch.object(Image, "open", return_value=header),
            patch.object(cv2, "imdecode") as opencv,
            self.assertRaises(ImageDimensionsError),
        ):
            image_loading.decode_photo(b"\0\0\0\x10ftypheic\0\0\0\0")
        header.convert.assert_not_called()
        opencv.assert_not_called()

    def test_malformed_heic_returns_a_public_photo_error(self):
        for data in (b"\0\0\0\x10ftypheic\0\0\0\0", b"\0\0\0\x18ftypheic"):
            with self.subTest(data=data), self.assertRaises(InvalidPhotoError):
                image_loading.decode_photo(data)

    def test_upload_limit_accepts_15_mib_but_not_an_extra_byte(self):
        self.assertEqual(MAX_FILE_BYTES, 15 * 1024 * 1024)
        jpeg = photo_bytes((32, 32), format="JPEG")
        padded = jpeg + b"\0" * (MAX_FILE_BYTES - len(jpeg))
        self.assertEqual(image_loading.decode_photo(padded)[0].shape, (32, 32, 3))
        with (
            patch.object(Image, "open") as decoder,
            self.assertRaises(UploadTooLargeError),
        ):
            image_loading.decode_photo(padded + b"\0")
        decoder.assert_not_called()


class ProcessingCheckpointTests(unittest.TestCase):
    def setUp(self):
        self.cancelled = Event()
        self.photo = photo_bytes((32, 32), color=(0, 0, 0))

    def test_cancel_before_decode(self):
        self.cancelled.set()
        with patch.object(cv2, "imdecode") as decode:
            with self.assertRaises(ProcessingCancelledError):
                image_processor.create_passport_photo(
                    self.photo, "United States", self.cancelled
                )
        decode.assert_not_called()

    def test_cancel_after_background_removal_skips_compositing(self):
        def remove(image, **kwargs):
            self.cancelled.set()
            return image.convert("L")

        detector = Mock()
        detector.predict.return_value = [person_result()]
        with (
            mock_pipeline(detector, side_effect=remove),
            patch.object(cv2, "getStructuringElement") as composite,
        ):
            with self.assertRaises(ProcessingCancelledError):
                image_processor.create_passport_photo(
                    self.photo, "United States", self.cancelled
                )
        detector.predict.assert_called_once()
        composite.assert_not_called()

    def test_cancel_after_detection_skips_compositing(self):
        def detect(*args, **kwargs):
            self.cancelled.set()
            return []

        with (
            mock_pipeline(SimpleNamespace(predict=detect)) as remove,
            patch.object(cv2, "getStructuringElement") as composite,
        ):
            with self.assertRaises(ProcessingCancelledError):
                image_processor.create_passport_photo(
                    self.photo, "United States", self.cancelled
                )
        composite.assert_not_called()
        remove.assert_not_called()

    def test_parallel_calls_serialize_shared_detector(self):
        detector_started = Event()
        release_detector = Event()
        second_lock_attempt = Event()
        attempt_lock = Lock()
        detector_lock = model_runtime.yolo_lock
        attempts = 0
        detections = []

        class ObservedLock:
            def __enter__(self):
                nonlocal attempts
                with attempt_lock:
                    attempts += 1
                    if attempts == 2:
                        second_lock_attempt.set()
                detector_lock.acquire()

            def __exit__(self, *args):
                detector_lock.release()

        def detect(*args, **kwargs):
            detections.append(True)
            if len(detections) == 1:
                detector_started.set()
                if not release_detector.wait(5):
                    raise AssertionError("Detector was not released")
            return [SimpleNamespace(boxes=[])]

        with (
            mock_pipeline(SimpleNamespace(predict=detect)) as remove,
            patch.object(model_runtime, "yolo_lock", ObservedLock()),
            ThreadPoolExecutor(max_workers=2) as executor,
        ):
            futures = [
                executor.submit(
                    image_processor.create_passport_photo, self.photo, "United States"
                )
                for _ in range(2)
            ]
            try:
                self.assertTrue(detector_started.wait(2))
                self.assertTrue(second_lock_attempt.wait(2))
                self.assertEqual(len(detections), 1)
            finally:
                release_detector.set()
            for future in futures:
                with self.assertRaises(PersonNotDetectedError):
                    future.result(timeout=2)
        self.assertEqual(len(detections), 2)
        remove.assert_not_called()

    def test_cancel_while_waiting_for_detector_skips_prediction(self):
        gate = Mock()
        gate.__enter__ = Mock(side_effect=self.cancelled.set)
        gate.__exit__ = Mock(return_value=False)
        detector = Mock()
        with (
            mock_pipeline(
                detector, side_effect=lambda image, **_: image.convert("RGBA")
            ),
            patch.object(model_runtime, "yolo_lock", gate),
        ):
            with self.assertRaises(ProcessingCancelledError):
                image_processor.create_passport_photo(
                    self.photo, "United States", self.cancelled
                )
        gate.__enter__.assert_called_once()
        detector.predict.assert_not_called()

    def test_existing_invalid_photo_error_is_preserved_without_token(self):
        with self.assertRaises(InvalidPhotoError):
            image_processor.create_passport_photo(b"not an image", "United States")

    def test_large_dimensions_rejected_before_decode(self):
        header = Mock()
        header.format = "PNG"
        header.size = (5000, 5000)
        header_context = Mock()
        header_context.__enter__ = Mock(return_value=header)
        header_context.__exit__ = Mock(return_value=False)
        with (
            patch.object(Image, "open", return_value=header_context),
            patch.object(cv2, "imdecode") as decode,
        ):
            with self.assertRaises(ImageDimensionsError):
                image_processor.create_passport_photo(self.photo, "United States")
        decode.assert_not_called()

    def test_real_png_and_jpeg_dimensions_rejected_before_decode(self):
        png = bytearray(self.photo)
        png[16:24] = (5000).to_bytes(4, "big") * 2
        png[29:33] = zlib.crc32(png[12:29]).to_bytes(4, "big")
        jpeg_output = io.BytesIO()
        Image.new("RGB", (32, 32)).save(jpeg_output, format="JPEG")
        jpeg = bytearray(jpeg_output.getvalue())
        frame = jpeg.index(b"\xff\xc0")
        jpeg[frame + 5 : frame + 9] = (5000).to_bytes(2, "big") * 2
        for data in (png, jpeg):
            with (
                self.subTest(signature=data[:8]),
                patch.object(cv2, "imdecode") as decode,
            ):
                with self.assertRaises(ImageDimensionsError):
                    image_processor.create_passport_photo(bytes(data), "United States")
                decode.assert_not_called()

    def test_working_resolution_is_bounded(self):
        _, encoded = cv2.imencode(".png", np.zeros((32, 4096, 3), dtype=np.uint8))
        sizes = []

        def remove(image, **kwargs):
            sizes.append(image.size)
            raise ProcessingCancelledError()

        with mock_pipeline(size=(1024, 8), side_effect=remove):
            with self.assertRaises(ProcessingCancelledError):
                image_processor.create_passport_photo(
                    encoded.tobytes(), "United States"
                )
        self.assertEqual(sizes, [(1024, 8)])

    def test_no_detected_subject_raises_expected_error(self):
        detector = Mock()
        detector.predict.return_value = [SimpleNamespace(boxes=[])]
        with mock_pipeline(detector) as remove:
            with self.assertRaises(PersonNotDetectedError):
                image_processor.create_passport_photo(self.photo, "United States")
        remove.assert_not_called()

    def test_actual_image_format_is_checked(self):
        image = Image.new("RGB", (32, 32), "white")
        data = io.BytesIO()
        image.save(data, format="TIFF")
        with patch.object(cv2, "imdecode") as decode:
            with self.assertRaises(InvalidPhotoError):
                image_processor.create_passport_photo(data.getvalue(), "United States")
        decode.assert_not_called()


class ReducedMemoryTests(unittest.TestCase):
    def test_low_memory_defaults_and_docker_model_match(self):
        self.assertEqual(MAX_ACTIVE_JOBS, 1)
        self.assertEqual(MAX_WAITING_JOBS, 2)
        self.assertEqual(MAX_WORKING_SIDE, 1024)
        self.assertEqual(model_runtime.REMBG_MODEL_NAME, "modnet-portrait")
        dockerfile = (
            Path(__file__).resolve().parents[1] / "Dockerfile.backend"
        ).read_text()
        self.assertIn(
            "from services.modnet_session import ModnetPortraitSession",
            dockerfile,
        )
        self.assertNotIn("birefnet_portrait", dockerfile)
        self.assertIn("import main; import rembg; import ultralytics", dockerfile)
        for setting in (
            "MALLOC_ARENA_MAX=2",
            "OMP_NUM_THREADS=1",
            "OPENBLAS_NUM_THREADS=1",
            "MKL_NUM_THREADS=1",
        ):
            self.assertIn(setting, dockerfile)
        route = (
            Path(__file__).resolve().parents[1] / "frontend/app/api/process/route.ts"
        ).read_text()
        self.assertIn("const MAX_ACTIVE_REQUESTS = 3;", route)

    def test_model_loading_uses_one_reusable_cpu_session(self):
        session = object()
        detector = object()
        with (
            patch.object(
                model_runtime, "create_rembg_session", return_value=session
            ) as create,
            patch("ultralytics.YOLO", return_value=detector) as yolo,
            patch.object(model_runtime, "rembg_session", None, create=True),
            patch.object(model_runtime, "yolo_model", None, create=True),
        ):
            model_runtime.load_models()
            create.assert_called_once_with("modnet-portrait")
            yolo.assert_called_once_with(str(model_runtime.MODEL_PATH))
            self.assertIs(model_runtime.rembg_session, session)
            self.assertIs(model_runtime.yolo_model, detector)

    def test_rembg_runtime_limits_allocators_not_precision_or_resolution(self):
        options = SimpleNamespace(
            enable_cpu_mem_arena=True,
            enable_mem_pattern=True,
            graph_optimization_level="default",
            execution_mode=None,
            intra_op_num_threads=0,
            inter_op_num_threads=0,
        )
        session_type = Mock()
        session_type.name.return_value = "u2net_human_seg"
        portrait_type = Mock()
        portrait_type.name.return_value = "modnet-portrait"
        ort = SimpleNamespace(
            SessionOptions=Mock(return_value=options),
            ExecutionMode=SimpleNamespace(ORT_SEQUENTIAL="sequential"),
        )
        with patch.dict(
            "sys.modules",
            {
                "onnxruntime": ort,
                "rembg.sessions.u2net_human_seg": SimpleNamespace(
                    U2netHumanSegSession=session_type
                ),
                "services.modnet_session": SimpleNamespace(
                    ModnetPortraitSession=portrait_type
                ),
            },
        ):
            self.assertIs(
                model_runtime.create_rembg_session("u2net_human_seg"),
                session_type.return_value,
            )
            session_type.assert_called_once_with(
                "u2net_human_seg",
                options,
                providers=["CPUExecutionProvider"],
            )
            self.assertIs(
                model_runtime.create_rembg_session("modnet-portrait"),
                portrait_type.return_value,
            )
            portrait_type.assert_called_once_with(
                "modnet-portrait",
                options,
                providers=["CPUExecutionProvider"],
            )
            self.assertFalse(options.enable_cpu_mem_arena)
            self.assertTrue(options.enable_mem_pattern)
            self.assertEqual(options.graph_optimization_level, "default")
            self.assertEqual(options.execution_mode, "sequential")
            self.assertEqual(options.intra_op_num_threads, 1)
            self.assertEqual(options.inter_op_num_threads, 1)
            session_type.reset_mock()
            with self.assertRaises(ValueError):
                model_runtime.create_rembg_session("birefnet-portrait")
            session_type.assert_not_called()

    def test_detector_clears_request_caches_but_keeps_model_and_predictor(self):
        mask = np.linspace(0, 1, 32 * 32, dtype=np.float32).reshape(32, 32)
        predictor = SimpleNamespace(model=object())
        detector = Mock(predictor=predictor)

        def detect(image, **kwargs):
            result = person_result(mask=mask)
            predictor.results = [result]
            predictor.batch = (["photo"], [image], [""])
            predictor.dataset = [image]
            return predictor.results

        detector.predict.side_effect = detect
        original = np.zeros((32, 32, 3), dtype=np.uint8)
        with patch.object(model_runtime, "yolo_model", detector, create=True):
            for _ in range(3):
                alpha = segmentation.person_alpha(original, lambda: None)
                np.testing.assert_array_equal(alpha, mask)
                self.assertIs(detector.predictor, predictor)
                self.assertIsNotNone(predictor.model)
                self.assertIsNone(predictor.results)
                self.assertIsNone(predictor.batch)
                self.assertIsNone(predictor.dataset)
        self.assertEqual(detector.predict.call_count, 3)
        np.testing.assert_array_equal(mask, alpha)

    def test_detector_error_or_cancellation_also_clears_request_caches(self):
        for cancelled in (False, True):
            predictor = SimpleNamespace(
                results=object(),
                batch=object(),
                dataset=object(),
            )
            token = Event()

            def detect(*args, cancelled=cancelled, token=token, **kwargs):
                if cancelled:
                    token.set()
                return [SimpleNamespace(boxes=[])]

            def check_cancelled(token=token):
                if token.is_set():
                    raise ProcessingCancelledError()

            with (
                self.subTest(cancelled=cancelled),
                patch.object(
                    model_runtime,
                    "yolo_model",
                    SimpleNamespace(
                        predictor=predictor,
                        predict=detect,
                    ),
                    create=True,
                ),
            ):
                with self.assertRaises(
                    ProcessingCancelledError if cancelled else PersonNotDetectedError
                ):
                    segmentation.person_alpha(
                        np.zeros((32, 32, 3), dtype=np.uint8),
                        check_cancelled,
                    )
                self.assertIsNone(predictor.results)
                self.assertIsNone(predictor.batch)
                self.assertIsNone(predictor.dataset)

    def test_wrong_class_and_low_confidence_skip_rembg(self):
        for result, error in (
            (person_result(class_id=1), PersonNotDetectedError),
            (person_result(confidence=0.5), LowConfidenceError),
        ):
            with (
                self.subTest(error=error),
                patch.object(
                    model_runtime,
                    "yolo_model",
                    Mock(predict=Mock(return_value=[result])),
                    create=True,
                ),
                patch("rembg.remove") as remove,
            ):
                with self.assertRaises(error):
                    image_processor.create_passport_photo(
                        photo_bytes(), "United States"
                    )
                remove.assert_not_called()

    def test_subject_bounds_preserve_soft_pixels_without_coordinate_grid(self):
        alpha = np.zeros((1024, 1024), dtype=np.float32)
        alpha[17:1000, 23:999] = 0.001
        with patch.object(np, "where", side_effect=AssertionError):
            self.assertEqual(segmentation.subject_bounds(alpha), (23, 998, 17, 999))

    def test_empty_subject_mask_is_rejected(self):
        with self.assertRaises(SubjectSeparationError):
            segmentation.subject_bounds(np.zeros((32, 32), dtype=np.float32))

    def test_selection_kernel_sizes_scale_and_stay_odd(self):
        for scale in (0.01, 0.5, 0.75, 1.0):
            for size in (31, 41):
                result = segmentation.scaled_kernel_size(size, scale)
                self.assertGreaterEqual(result, 1)
                self.assertEqual(result % 2, 1)
        self.assertEqual(segmentation.scaled_kernel_size(31, 1.0), 31)
        self.assertEqual(segmentation.scaled_kernel_size(41, 1.0), 41)
        self.assertEqual(segmentation.scaled_kernel_size(31, 0.5), 17)
        self.assertEqual(segmentation.scaled_kernel_size(41, 0.5), 21)

    def test_jpeg_is_downsampled_during_decode(self):
        for side, flag in (
            (1024, cv2.IMREAD_COLOR),
            (2048, cv2.IMREAD_REDUCED_COLOR_2),
            (4096, cv2.IMREAD_REDUCED_COLOR_4),
            (8192, cv2.IMREAD_REDUCED_COLOR_8),
        ):
            sizes = []

            def remove(image, sizes=sizes, **kwargs):
                sizes.append(image.size)
                raise ProcessingCancelledError()

            with (
                self.subTest(side=side),
                patch.object(cv2, "imdecode", wraps=cv2.imdecode) as decode,
                mock_pipeline(side_effect=remove),
            ):
                with self.assertRaises(ProcessingCancelledError):
                    image_processor.create_passport_photo(
                        photo_bytes((side, 32), format="JPEG"), "United States"
                    )
                self.assertEqual(decode.call_args.args[1], flag)
                self.assertEqual(max(sizes[0]), 1024)

    def test_face_guide_is_passed_to_composition_before_source_release(self):
        stages = []
        face = (38, 20, 52, 55)

        def locate(photo, person, check_cancelled):
            self.assertEqual(photo.shape, (96, 128, 3))
            self.assertTrue(person.all())
            stages.append("face")
            return face

        def remove(image, **kwargs):
            stages.append("remove")
            return Image.new("L", image.size, 255)

        with (
            mock_pipeline(size=(128, 96), side_effect=remove),
            patch.object(image_processor, "detect_face", side_effect=locate),
            patch.object(
                image_processor, "compose_photo", return_value=b"jpeg"
            ) as export,
        ):
            self.assertEqual(
                image_processor.create_passport_photo(photo_bytes(), "United States"),
                b"jpeg",
            )
        self.assertEqual(stages, ["face", "remove"])
        self.assertEqual(export.call_args.args[-1], face)

    def test_mask_only_pipeline_preserves_country_sizes_and_rgb(self):
        for country, (width_mm, height_mm) in passport_photo_sizes_mm.items():
            stages = []

            def detect(*args, stages=stages, **kwargs):
                stages.append("detect")
                return [person_result((128, 96))]

            def remove(image, stages=stages, **kwargs):
                stages.append("remove")
                self.assertEqual(image.mode, "RGB")
                return Image.new("L", image.size, 255)

            session = object()
            with (
                self.subTest(country=country),
                mock_pipeline(
                    SimpleNamespace(predict=detect),
                    session=session,
                    side_effect=remove,
                ) as removal,
                patch.object(model_runtime, "create_rembg_session") as create,
            ):
                output = image_processor.create_passport_photo(photo_bytes(), country)
                self.assertEqual(stages, ["detect", "remove"])
                self.assertEqual(
                    removal.call_args.kwargs,
                    {
                        "session": session,
                        "only_mask": True,
                    },
                )
                create.assert_not_called()
                with Image.open(io.BytesIO(output)) as result:
                    self.assertEqual(result.format, "JPEG")
                    self.assertEqual(result.mode, "RGB")
                    self.assertEqual(
                        result.size, (int(width_mm * 11.81), int(height_mm * 11.81))
                    )
                    center = result.getpixel((result.width // 2, result.height // 2))
                    np.testing.assert_allclose(center, (25, 65, 105), atol=3)
                    np.testing.assert_allclose(
                        result.getpixel((0, 0)), (255, 255, 255), atol=3
                    )

    def test_coarse_person_gate_preserves_soft_edges_and_fills_interior_holes(self):
        width, height = 128, 96
        rng = np.random.default_rng(42)
        raw_alpha = rng.integers(0, 256, (height, width), dtype=np.uint8)
        yolo_alpha = np.zeros((height, width), dtype=np.float32)
        yolo_alpha[24:72, 32:96] = rng.random((48, 64), dtype=np.float32)
        yolo_alpha[28:68, 36:92] = 1.0
        yolo_alpha[40:56, 48:80] = 0
        original_yolo = yolo_alpha.copy()
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (41, 41))
        binary = (yolo_alpha > 0.5).astype(np.uint8)
        contours, _ = cv2.findContours(
            binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        cv2.drawContours(binary, contours, -1, 1, cv2.FILLED)
        dilated = cv2.dilate(binary, kernel, iterations=2)
        expected = raw_alpha.copy()
        expected[dilated == 0] = 0
        expected_bounds = segmentation.subject_bounds(expected)
        with (
            Image.new("RGB", (width, height), (25, 65, 105)) as photo,
            patch.object(model_runtime, "rembg_session", object(), create=True),
            patch("rembg.remove", return_value=Image.fromarray(raw_alpha)),
            patch.object(cv2, "GaussianBlur") as blur,
        ):
            mask, bounds = segmentation.merge_subject_alpha(
                photo, yolo_alpha, 1.0, lambda: None
            )
            np.testing.assert_array_equal(mask, expected)
            np.testing.assert_array_equal(mask[40:56, 48:80], raw_alpha[40:56, 48:80])
            np.testing.assert_array_equal(yolo_alpha, original_yolo)
            self.assertEqual(bounds, expected_bounds)
            blur.assert_not_called()

    def test_selection_gate_depends_on_working_size_not_upload_size(self):
        for size, expected_kernel in (
            ((512, 256), 21),
            ((1024, 512), 41),
            ((2048, 1024), 41),
        ):
            working_size = (min(size[0], 1024), min(size[1], 512))
            with (
                self.subTest(size=size),
                mock_pipeline(
                    size=working_size,
                    side_effect=lambda image, **_: Image.new("L", image.size, 255),
                ),
                patch.object(
                    cv2, "getStructuringElement", wraps=cv2.getStructuringElement
                ) as kernel,
                patch.object(cv2, "GaussianBlur", wraps=cv2.GaussianBlur) as blur,
            ):
                image_processor.create_passport_photo(
                    photo_bytes(size), "United States"
                )
            kernel.assert_called_once_with(
                cv2.MORPH_ELLIPSE, (expected_kernel, expected_kernel)
            )
            blur.assert_not_called()

    def test_cancellation_closes_temporary_images(self):
        cancelled = Event()
        images = []

        def remove(image, **kwargs):
            mask = Image.new("L", image.size, 255)
            images.extend([image, mask])
            cancelled.set()
            return mask

        with mock_pipeline(size=(128, 96), side_effect=remove):
            with self.assertRaises(ProcessingCancelledError):
                image_processor.create_passport_photo(
                    photo_bytes(), "United States", cancelled
                )
        self.assertEqual(len(images), 2)
        for image in images:
            with self.assertRaises(ValueError):
                image.getpixel((0, 0))

    def test_unusable_rembg_masks_fail_without_export(self):
        for value, error in ((0, SubjectSeparationError), (255, SubjectTooSmallError)):
            alpha = np.zeros((96, 128), dtype=np.uint8)
            alpha[48, 64] = value
            with (
                self.subTest(value=value),
                mock_pipeline(
                    size=(128, 96),
                    return_value=Image.fromarray(alpha),
                ),
            ):
                with self.assertRaises(error):
                    image_processor.create_passport_photo(
                        photo_bytes(), "United States"
                    )

    def test_rejected_framing_closes_images_without_export(self):
        inset_alpha = np.zeros((400, 600), dtype=np.uint8)
        inset_alpha[80:, 210:390] = 255
        for name, size, alpha in (
            ("narrow source", (64, 128), None),
            ("inset mask", (600, 400), inset_alpha),
        ):
            with self.subTest(case=name):
                images = []
                photo = photo_bytes(size)

                def remove(image, *, alpha=alpha, images=images, **kwargs):
                    mask = (
                        Image.fromarray(alpha)
                        if alpha is not None
                        else Image.new("L", image.size, 255)
                    )
                    images.extend((image, mask))
                    return mask

                with (
                    mock_pipeline(size=size, side_effect=remove),
                    patch.object(Image.Image, "save") as export,
                ):
                    with self.assertRaises(SubjectFramingError):
                        image_processor.create_passport_photo(photo, "United States")
                    export.assert_not_called()
                self.assertEqual(len(images), 2)
                for image in images:
                    with self.assertRaises(ValueError):
                        image.getpixel((0, 0))


class PhotoRequestTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.processor = self.enterContext(
            patch("api.create_passport_photo", return_value=b"jpeg")
        )


class DisconnectTests(PhotoRequestTests):
    def setUp(self):
        super().setUp()
        self.request = SimpleNamespace(is_disconnected=AsyncMock(return_value=False))

    def upload(self):
        return UploadFile(
            io.BytesIO(b"test photo"),
            filename="photo.png",
            headers=Headers({"content-type": "image/png"}),
        )

    async def process(self, country="United States", upload=None):
        return await process_image(self.request, country, upload or self.upload())

    async def test_already_disconnected_does_not_start_worker(self):
        self.request.is_disconnected.return_value = True
        response = await self.process()
        self.assertEqual(response.status_code, 499)
        self.processor.assert_not_called()

    async def test_disconnect_reaches_running_worker(self):
        started = Event()
        observed = Event()

        def process(photo, country, cancelled):
            started.set()
            if cancelled.wait(timeout=2):
                observed.set()
                raise ProcessingCancelledError()
            raise AssertionError("Disconnect was not propagated to the worker")

        async def disconnected():
            return started.is_set()

        self.request.is_disconnected = disconnected
        self.processor.side_effect = process
        response = await self.process()
        self.assertEqual(response.status_code, 499)
        self.assertTrue(observed.is_set())

    async def test_success_and_photo_errors_keep_existing_contract(self):
        response = await self.process()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.media_type, "image/jpeg")
        self.assertEqual(response.body, b"jpeg")

        for error in (InvalidPhotoError(), SubjectFramingError()):
            with self.subTest(error=type(error).__name__):
                self.processor.side_effect = error
                response = await self.process()
            self.assertEqual(response.status_code, 422)
            payload = json.loads(response.body)
            tips = payload.pop("tips", None)
            self.assertEqual(payload, {"code": "PHOTO_ISSUE", "detail": error.message})
            self.assertEqual(response.headers["cache-control"], "no-store")
            if isinstance(error, SubjectFramingError):
                self.assertEqual(
                    payload["detail"],
                    "We couldn't frame this photo cleanly without leaving white borders "
                    "along the sides.",
                )
                self.assertEqual(
                    tips,
                    [
                        "Adjust the crop: widen or reset it to show more of both shoulders.",
                        "Take a new photo: hold the camera farther away so your whole head "
                        "and both shoulders are visible.",
                    ],
                )
            else:
                self.assertIsNone(tips)

    async def test_unexpected_worker_errors_are_logged_without_exposing_details(self):
        before = set(asyncio.all_tasks())
        self.processor.side_effect = RuntimeError("private model path")
        with patch("api.logger.exception") as log:
            response = await self.process()
        self.assertEqual(response.status_code, 500)
        self.assertEqual(json.loads(response.body)["code"], "INTERNAL_SERVER_ERROR")
        self.assertNotIn(b"private model path", response.body)
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(set(asyncio.all_tasks()), before)
        log.assert_called_once()

    async def test_upload_read_failure_cleans_up_tasks_and_admission(self):
        upload = self.upload()
        before = set(asyncio.all_tasks())
        with (
            patch.object(upload, "read", side_effect=OSError("temporary file failed")),
            patch("api.logger.exception"),
        ):
            response = await self.process(upload=upload)
        self.assertEqual(response.status_code, 500)
        self.assertEqual(set(asyncio.all_tasks()), before)
        self.processor.assert_not_called()
        with reserved_slots() as permits:
            self.assertTrue(all(permits))

    async def test_invalid_country_does_not_start_worker(self):
        response = await self.process("invalid")
        self.assertEqual(response.status_code, 400)
        self.processor.assert_not_called()

    async def test_worker_finishes_without_leaking_disconnect_watcher(self):
        before = set(asyncio.all_tasks())
        await self.process()
        self.assertEqual(set(asyncio.all_tasks()), before)

    async def test_handler_cancellation_signals_worker(self):
        started = Event()
        stopped = Event()

        def process(photo, country, cancelled):
            started.set()
            if cancelled.wait(timeout=2):
                stopped.set()
            return b"discarded"

        self.processor.side_effect = process
        task = asyncio.create_task(self.process())
        self.assertTrue(await asyncio.to_thread(started.wait, 2))
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertTrue(await asyncio.to_thread(stopped.wait, 2))


class UploadBoundaryTests(PhotoRequestTests):
    def multipart(self, data=b"photo", content_type="image/png"):
        return (
            b'--boundary\r\nContent-Disposition: form-data; name="file"; '
            b'filename="photo.png"\r\nContent-Type: '
            + content_type.encode()
            + b"\r\n\r\n"
            + data
            + b"\r\n--boundary--\r\n"
        )

    async def request(
        self, body, declared_length=None, receive_delay=0, disconnect=None
    ):
        headers = [(b"content-type", b"multipart/form-data; boundary=boundary")]
        if declared_length is not None:
            headers.append((b"content-length", str(declared_length).encode()))
        sent, read = await request_app(
            app,
            body=body,
            headers=headers,
            receive_delay=receive_delay,
            disconnect=disconnect,
        )
        start = next(
            message for message in sent if message["type"] == "http.response.start"
        )
        payload = b"".join(
            message.get("body", b"")
            for message in sent
            if message["type"] == "http.response.body"
        )
        return start["status"], payload, dict(start["headers"]), read

    async def test_declared_oversize_rejected_without_reading(self):
        status, body, _, read = await self.request(b"unused", MAX_REQUEST_BYTES + 1)
        self.assertEqual(status, 413)
        self.assertEqual(json.loads(body)["code"], "PHOTO_ISSUE")
        self.assertEqual(read, 0)
        self.processor.assert_not_called()

    async def test_streamed_oversize_and_false_length_are_rejected(self):
        body = self.multipart(b"x" * (MAX_REQUEST_BYTES + 1))
        for declared in (None, 1):
            status, payload, _, read = await self.request(body, declared)
            self.assertEqual(status, 413)
            self.assertEqual(json.loads(payload)["code"], "PHOTO_ISSUE")
            self.assertLessEqual(read, MAX_REQUEST_BYTES + 64 * 1024)
            self.processor.assert_not_called()

    async def test_file_limit_below_aggregate_limit(self):
        status, _, _, _ = await self.request(
            self.multipart(b"x" * (MAX_FILE_BYTES + 1))
        )
        self.assertEqual(status, 413)
        self.processor.assert_not_called()

    async def test_busy_rejected_before_body_read(self):
        with reserved_slots() as permits:
            self.assertTrue(all(permits))
            status, payload, headers, read = await self.request(self.multipart())
        self.assertEqual(status, 503)
        self.assertEqual(json.loads(payload)["code"], "SERVICE_BUSY")
        self.assertEqual(headers[b"retry-after"], b"10")
        self.assertEqual(read, 0)

    async def test_allowed_type_and_exact_limit_pass(self):
        body = self.multipart(b"x" * MAX_FILE_BYTES)
        status, _, headers, _ = await self.request(body, len(body))
        self.assertEqual(status, 200)
        self.assertEqual(headers[b"cache-control"], b"no-store")
        self.assertEqual(len(self.processor.call_args.args[0]), MAX_FILE_BYTES)

    async def test_mime_rejection_releases_admission(self):
        status, _, _, _ = await self.request(self.multipart(content_type="image/tiff"))
        self.assertEqual(status, 400)
        status, _, _, _ = await self.request(self.multipart())
        self.assertEqual(status, 200)

    async def test_no_detection_contract(self):
        self.processor.side_effect = PersonNotDetectedError()
        status, body, _, _ = await self.request(self.multipart())
        self.assertEqual(status, 422)
        self.assertEqual(json.loads(body)["code"], "PERSON_NOT_DETECTED")

    async def test_malformed_multipart_releases_admission(self):
        status, _, _, _ = await self.request(b"invalid multipart body")
        self.assertEqual(status, 400)
        permit = processing_pool.try_acquire()
        self.assertIsNotNone(permit)
        permit.release_if_unused()

    async def test_stalled_upload_times_out_and_releases_admission(self):
        with patch("request_limits.MAX_UPLOAD_SECONDS", 0.01):
            status, payload, _, _ = await self.request(
                self.multipart(), receive_delay=0.1
            )
        self.assertEqual(status, 408)
        self.assertEqual(json.loads(payload)["code"], "PHOTO_ISSUE")
        permit = processing_pool.try_acquire()
        self.assertIsNotNone(permit)
        permit.release_if_unused()

    async def test_upload_deadline_does_not_cut_off_inference(self):
        import time

        def process(*args):
            time.sleep(0.05)
            return b"jpeg"

        self.processor.side_effect = process
        with patch("request_limits.MAX_UPLOAD_SECONDS", 0.01):
            status, _, _, _ = await self.request(self.multipart())
        self.assertEqual(status, 200)

    async def test_one_photo_runs_and_two_wait_in_order(self):
        started = {b"first": Event()}
        releases = {name: Event() for name in started}
        queued = [asyncio.Event() for _ in range(MAX_WAITING_JOBS)]
        calls = []
        reads = []
        tasks = []
        start_waiters = processing_pool.start_waiters
        from starlette.datastructures import UploadFile as StarletteUploadFile

        read_file = StarletteUploadFile.read

        async def record_read(file, size=-1):
            data = await read_file(file, size)
            reads.append(data)
            return data

        def notify_waiting():
            start_waiters()
            count = len(processing_pool.waiting)
            if count:
                queued[count - 1].set()

        def process(photo, *args):
            calls.append(photo)
            if photo in started:
                started[photo].set()
                if not releases[photo].wait(5):
                    raise AssertionError("Active job was not released")
            return b"jpeg"

        self.processor.side_effect = process
        with (
            patch.object(processing_pool, "start_waiters", side_effect=notify_waiting),
            patch.object(StarletteUploadFile, "read", record_read),
        ):
            try:
                for name, event in started.items():
                    tasks.append(
                        asyncio.create_task(self.request(self.multipart(name)))
                    )
                    self.assertTrue(await asyncio.to_thread(event.wait, 2))
                self.assertEqual(processing_pool.active, 1)
                for index, name in enumerate((b"second", b"third")):
                    tasks.append(
                        asyncio.create_task(self.request(self.multipart(name)))
                    )
                    await asyncio.wait_for(queued[index].wait(), 2)
                self.assertEqual(calls, [b"first"])
                self.assertEqual(reads, [b"first"])
                self.assertTrue(all(not task.done() for task in tasks))
                status, _, _, read = await self.request(self.multipart(b"fourth"))
                self.assertEqual((status, read), (503, 0))
                releases[b"first"].set()
                responses = await asyncio.wait_for(asyncio.gather(*tasks), 3)
                self.assertEqual([response[0] for response in responses], [200] * 3)
                self.assertEqual(calls, [b"first", b"second", b"third"])
                self.assertEqual(reads, calls)
            finally:
                for release in releases.values():
                    release.set()
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)

    async def occupy_workers(self):
        permits = []
        for _ in range(MAX_ACTIVE_JOBS):
            permit = processing_pool.try_acquire()
            self.assertIsNotNone(permit)
            self.addCleanup(permit.release_if_unused)
            await permit.wait_for_turn()
            permits.append(permit)
        return permits

    async def test_queued_disconnect_removes_photo_without_processing(self):
        active = await self.occupy_workers()
        disconnect = asyncio.Event()
        queued = asyncio.Event()
        start_waiters = processing_pool.start_waiters

        def notify_waiting():
            start_waiters()
            if processing_pool.waiting:
                queued.set()

        with patch.object(processing_pool, "start_waiters", side_effect=notify_waiting):
            task = asyncio.create_task(
                self.request(self.multipart(), disconnect=disconnect)
            )
            try:
                await asyncio.wait_for(queued.wait(), 2)
                disconnect.set()
                response = await asyncio.wait_for(task, 2)
                self.assertEqual(response[0], 499)
                self.assertEqual(len(processing_pool.waiting), 0)
                self.assertEqual(processing_pool.active, MAX_ACTIVE_JOBS)
                self.processor.assert_not_called()
            finally:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
                for permit in active:
                    permit.release_if_unused()

    async def test_queue_timeout_releases_waiting_slot_without_processing(self):
        active = await self.occupy_workers()
        try:
            with patch("services.photo_requests.MAX_QUEUE_WAIT_SECONDS", 0.01):
                status, payload, _, _ = await self.request(self.multipart())
            self.assertEqual(status, 503)
            self.assertIn("waited too long", json.loads(payload)["detail"])
            self.assertEqual(len(processing_pool.waiting), 0)
            self.processor.assert_not_called()
            with reserved_slots(MAX_WAITING_JOBS) as replacements:
                self.assertTrue(all(replacements))
        finally:
            for permit in active:
                permit.release_if_unused()


class ProcessingQueueTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # Exercise the default single-worker queue independently of HTTP.
        self.pool = ProcessingPool(capacity=1)
        self.permits = []
        self.waiters = []
        self.release_native = Event()

    async def asyncTearDown(self):
        self.release_native.set()
        for task in self.waiters:
            task.cancel()
        await asyncio.gather(*self.waiters, return_exceptions=True)
        for permit in self.permits:
            permit.release_if_unused()
        await asyncio.to_thread(
            self.pool.executor.shutdown, wait=True, cancel_futures=True
        )

    def reserve(self):
        permit = self.pool.try_acquire()
        self.assertIsNotNone(permit)
        self.permits.append(permit)
        return permit

    async def enqueue(self, permit):
        task = asyncio.create_task(permit.wait_for_turn())
        self.waiters.append(task)
        # Let the task register its queue entry before inspecting ordering.
        await asyncio.sleep(0)
        return task

    async def test_cancelled_waiters_do_not_accumulate_executor_jobs(self):
        active = self.reserve()
        await active.wait_for_turn()
        with patch.object(self.pool.executor, "submit") as submit:
            for _ in range(50):
                permit = self.reserve()
                task = await self.enqueue(permit)
                self.assertEqual(len(self.pool.waiting), 1)
                task.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await task
                self.assertEqual(len(self.pool.waiting), 0)
                self.assertEqual(self.pool.active, 1)
            submit.assert_not_called()

    async def test_cancellation_after_turn_granted_advances_next_waiter(self):
        active = self.reserve()
        await active.wait_for_turn()
        first = self.reserve()
        first_task = await self.enqueue(first)
        second = self.reserve()
        second_task = await self.enqueue(second)
        active.release_if_unused()
        first_task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await first_task
        await asyncio.wait_for(second_task, 2)
        self.assertEqual(self.pool.active, 1)
        self.assertEqual(len(self.pool.waiting), 0)

    async def test_cancelling_running_request_does_not_start_next_native_job(self):
        active = self.reserve()
        await active.wait_for_turn()
        started = Event()

        def native_job():
            started.set()
            self.release_native.wait(3)

        future = active.submit(native_job)
        self.assertTrue(await asyncio.to_thread(started.wait, 2))
        successor = self.reserve()
        waiting = await self.enqueue(successor)
        result = asyncio.wrap_future(future)
        result.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await result
        active.release_if_unused()
        self.assertFalse(waiting.done())
        self.assertEqual(len(self.pool.waiting), 1)
        self.release_native.set()
        await asyncio.wait_for(waiting, 2)
        self.assertEqual(self.pool.active, 1)

    async def test_failed_native_job_advances_queue(self):
        active = self.reserve()
        await active.wait_for_turn()
        successor = self.reserve()
        waiting = await self.enqueue(successor)

        def fail():
            raise InvalidPhotoError()

        with self.assertRaises(InvalidPhotoError):
            await asyncio.wrap_future(active.submit(fail))
        await asyncio.wait_for(waiting, 2)
        self.assertEqual(self.pool.active, 1)

    async def test_submit_requires_a_worker_slot(self):
        active = self.reserve()
        await active.wait_for_turn()
        waiting = self.reserve()
        await self.enqueue(waiting)
        with self.assertRaises(RuntimeError):
            waiting.submit(lambda: b"must not run")


class NativeCapacityTests(unittest.IsolatedAsyncioTestCase):
    async def test_cancelled_job_keeps_its_slot_while_other_worker_progresses(self):
        # Retain coverage if a higher-memory deployment opts into concurrency.
        pool = ProcessingPool(capacity=2, max_waiting=0)
        permits = [pool.try_acquire() for _ in range(2)]
        started = [Event(), Event()]
        releases = [Event(), Event()]
        completed = Event()

        def native_job(index):
            started[index].set()
            if not releases[index].wait(5):
                raise AssertionError("Native job was not released")
            return b"jpeg"

        try:
            for permit in permits:
                await permit.wait_for_turn()
            futures = [
                permit.submit(native_job, index) for index, permit in enumerate(permits)
            ]
            futures[1].add_done_callback(lambda _: completed.set())
            for event in started:
                self.assertTrue(await asyncio.to_thread(event.wait, 2))
            waiter = asyncio.wrap_future(futures[0])
            waiter.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await waiter
            permits[0].release_if_unused()
            self.assertIsNone(pool.try_acquire())
            releases[1].set()
            self.assertTrue(await asyncio.to_thread(completed.wait, 2))
            replacement = pool.try_acquire()
            self.assertIsNotNone(replacement)
            permits.append(replacement)
            await replacement.wait_for_turn()
            result = await asyncio.wrap_future(
                replacement.submit(lambda: b"next photo")
            )
            self.assertEqual(result, b"next photo")
            self.assertFalse(futures[0].done())
        finally:
            for release in releases:
                release.set()
            for permit in permits:
                if permit is not None:
                    permit.release_if_unused()
            await asyncio.to_thread(
                pool.executor.shutdown, wait=True, cancel_futures=True
            )

    async def test_running_native_job_keeps_permit_after_await_is_cancelled(self):
        pool = ProcessingPool(capacity=1, max_waiting=0)
        permit = pool.try_acquire()
        await permit.wait_for_turn()
        started = Event()
        release = Event()

        def native_job():
            started.set()
            release.wait(timeout=3)
            return b"jpeg"

        try:
            future = permit.submit(native_job)
            completed = Event()
            future.add_done_callback(lambda _: completed.set())
            self.assertTrue(await asyncio.to_thread(started.wait, 2))
            waiter = asyncio.wrap_future(future)
            waiter.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await waiter
            permit.release_if_unused()
            self.assertIsNone(pool.try_acquire())
            release.set()
            await asyncio.to_thread(future.result, 2)
            self.assertTrue(await asyncio.to_thread(completed.wait, 2))
            replacement = pool.try_acquire()
            self.assertIsNotNone(replacement)
            replacement.release_if_unused()
        finally:
            release.set()
            pool.executor.shutdown(wait=True, cancel_futures=True)


if __name__ == "__main__":
    unittest.main()
