import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
import cv2
import numpy as np
from PIL import Image, UnidentifiedImageError
from ultralytics import YOLO
from rembg import remove
import io
from contextlib import closing
from pathlib import Path
from threading import Event, Lock

from services.rembg_runtime import create_rembg_session
from utils.passport_sizes import passport_photo_sizes_mm
from utils.image_headers import check_dimensions, check_webp_header
from utils.limits import (
    ACCEPTED_IMAGE_FORMATS,
    MAX_FILE_BYTES,
    MAX_WORKING_SIDE,
)
from errors import (
    EmptyPhotoError,
    InvalidCountryError,
    InvalidPhotoError,
    ImageDimensionsError,
    LowConfidenceError,
    PersonNotDetectedError,
    ProcessingCancelledError,
    SubjectSeparationError,
    SubjectTooSmallError,
    UploadTooLargeError,
)

MODEL_PATH = Path(__file__).resolve().parents[2] / "best.pt"
REMBG_MODEL_NAME = "u2net_human_seg"
yolo_lock = Lock()


def load_models():
    global rembg_session, yolo_model
    print("Loading models into memory...")
    rembg_session = create_rembg_session(REMBG_MODEL_NAME)
    yolo_model = YOLO(str(MODEL_PATH))


def person_alpha(original_img: np.ndarray, check_cancelled) -> np.ndarray:
    height, width = original_img.shape[:2]
    # Predictor initialization and request caches are mutable shared state.
    with yolo_lock:
        try:
            check_cancelled()
            results = yolo_model.predict(original_img, conf=0.1, verbose=False)
            check_cancelled()
            result = results[0]
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
        finally:
            # Retain the model/predictor, not the last request's RGB and masks.
            # Ultralytics recreates its source on each predict() invocation.
            predictor = getattr(yolo_model, "predictor", None)
            if predictor is not None:
                predictor.results = None
                predictor.batch = None
                predictor.dataset = None


def subject_bounds(alpha: np.ndarray) -> tuple[int, int, int, int]:
    # Find occupied rows/columns, not a coordinate pair for every subject pixel.
    rows = np.flatnonzero(alpha.any(axis=1))
    if not rows.size:
        raise SubjectSeparationError()
    columns = np.flatnonzero(alpha.any(axis=0))
    return int(columns[0]), int(columns[-1]), int(rows[0]), int(rows[-1])


def scaled_kernel_size(size: int, scale: float) -> int:
    return max(1, 2 * round((size // 2) * scale) + 1)


def create_passport_photo(
    image_bytes: bytes, country: str, cancelled: Event | None = None
) -> bytes:
    """Create a white-background JPEG with a bottom-anchored subject."""
    def check_cancelled():
        if cancelled is not None and cancelled.is_set():
            raise ProcessingCancelledError()

    check_cancelled()
    if country not in passport_photo_sizes_mm:
        raise InvalidCountryError()
        
    target_w_mm, target_h_mm = passport_photo_sizes_mm[country]
    target_ratio = target_w_mm / target_h_mm
    
    if not image_bytes:
        raise EmptyPhotoError()
    if len(image_bytes) > MAX_FILE_BYTES:
        raise UploadTooLargeError()
    check_webp_header(image_bytes)
    try:
        # Restrict plugins: unsupported formats must not allocate during open.
        with Image.open(io.BytesIO(image_bytes), formats=list(ACCEPTED_IMAGE_FORMATS)) as header:
            if header.format not in ACCEPTED_IMAGE_FORMATS:
                raise InvalidPhotoError()
            image_format = header.format
            width, height = header.size
            check_dimensions(width, height)
    except Image.DecompressionBombError as exc:
        raise ImageDimensionsError() from exc
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        if isinstance(exc, (InvalidPhotoError, ImageDimensionsError)):
            raise
        raise InvalidPhotoError() from exc

    nparr = np.frombuffer(image_bytes, np.uint8)
    decode_flag = cv2.IMREAD_COLOR
    if image_format == "JPEG":
        # JPEG can downsample during decoding rather than allocating full RGB.
        for factor, flag in (
            (8, cv2.IMREAD_REDUCED_COLOR_8),
            (4, cv2.IMREAD_REDUCED_COLOR_4),
            (2, cv2.IMREAD_REDUCED_COLOR_2),
        ):
            if max(width, height) >= MAX_WORKING_SIDE * factor:
                decode_flag = flag
                break
    try:
        original_img = cv2.imdecode(nparr, decode_flag)
    except cv2.error as exc:
        raise InvalidPhotoError() from exc
    
    if original_img is None:
        raise InvalidPhotoError()

    H, W = original_img.shape[:2]
    check_dimensions(W, H)
    # Preserve the old kernels' relative size when shrinking the working image.
    edge_scale = min(1.0, MAX_WORKING_SIDE / min(max(width, height), 2048))
    if max(H, W) > MAX_WORKING_SIDE:
        scale = MAX_WORKING_SIDE / max(H, W)
        original_img = cv2.resize(
            original_img, (max(1, round(W * scale)), max(1, round(H * scale))),
            interpolation=cv2.INTER_AREA,
        )
        H, W = original_img.shape[:2]

    yolo_alpha = person_alpha(original_img, check_cancelled)

    # Keep only a soft mask from rembg, not a second full RGB/RGBA cutout.
    check_cancelled()
    with closing(Image.fromarray(cv2.cvtColor(original_img, cv2.COLOR_BGR2RGB))) as full_pil:
        del original_img, nparr
        with closing(remove(full_pil, session=rembg_session, only_mask=True)) as rembg_mask:
            # Native inference cannot be interrupted; stop at the next checkpoint.
            check_cancelled()
            final_alpha = np.array(rembg_mask, dtype=np.float32)
        final_alpha /= 255.0

        check_cancelled()
        print("Merging alphas...")
        kernel_size = scaled_kernel_size(31, edge_scale)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
        yolo_bin = (yolo_alpha > 0.5).astype(np.uint8)
        eroded = cv2.erode(yolo_bin, kernel, iterations=1)
        dilated = cv2.dilate(yolo_bin, kernel, iterations=2)

        transition = (dilated == 1) & (eroded == 0)
        yolo_alpha *= 2.0
        np.clip(yolo_alpha, 0.0, 1.0, out=yolo_alpha)
        np.multiply(final_alpha, yolo_alpha, out=final_alpha, where=transition)
        final_alpha[dilated == 0] = 0.0
        del yolo_alpha, yolo_bin, eroded, dilated, transition

        # Calculate bounds before 8-bit quantization, preserving soft-mask support.
        px1, px2, py1, py2 = subject_bounds(final_alpha)
        final_alpha *= 255.0
        final_alpha_u8 = final_alpha.astype(np.uint8)
        del final_alpha
        blur_size = scaled_kernel_size(7, edge_scale)
        final_alpha_u8 = cv2.GaussianBlur(final_alpha_u8, (blur_size, blur_size), 0)

        print("Calculating Proportions...")
        check_cancelled()
        center_x = px1 + ((px2 - px1) / 2.0)

        # Preserve the existing 10% top margin and bottom-anchored composition.
        canvas_h = (py2 - py1) / 0.90
        canvas_w, canvas_h = int(canvas_h * target_ratio), int(canvas_h)
        if canvas_w < 1 or canvas_h < 1:
            raise SubjectTooSmallError()

        paste_x = int(canvas_w / 2 - center_x)
        paste_y = int(canvas_h - py2)
        with closing(Image.new("RGB", (canvas_w, canvas_h), (255, 255, 255))) as white_bg:
            with closing(Image.fromarray(final_alpha_u8)) as final_mask:
                white_bg.paste(full_pil, (paste_x, paste_y), final_mask)
            del final_alpha_u8

            print("Exporting...")
            check_cancelled()
            final_pixel_w = int(target_w_mm * 11.81)
            final_pixel_h = int(target_h_mm * 11.81)
            final_img = white_bg.resize(
                (final_pixel_w, final_pixel_h), Image.Resampling.LANCZOS
            )

        with closing(final_img), io.BytesIO() as output:
            final_img.save(output, format="JPEG", quality=95)
            check_cancelled()
            return output.getvalue()
