"""Detect the subject and retain the portrait model's soft alpha details."""

from collections.abc import Callable
from contextlib import closing

import cv2
import numpy as np
from PIL import Image

from errors import LowConfidenceError, PersonNotDetectedError, SubjectSeparationError
from services import model_runtime

SubjectBounds = tuple[int, int, int, int]
CancellationCheck = Callable[[], None]


def person_alpha(
    original_img: np.ndarray, check_cancelled: CancellationCheck
) -> np.ndarray:
    height, width = original_img.shape[:2]
    detector = model_runtime.get_detector()
    # Predictor initialization and request caches are mutable shared state.
    with model_runtime.yolo_lock:
        try:
            check_cancelled()
            results = detector.predict(original_img, conf=0.1, verbose=False)
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
            # Keep the predictor, not the last request's RGB and masks.
            predictor = getattr(detector, "predictor", None)
            if predictor is not None:
                predictor.results = None
                predictor.batch = None
                predictor.dataset = None


def subject_bounds(alpha: np.ndarray) -> SubjectBounds:
    # Avoid allocating a coordinate pair for every subject pixel.
    rows = np.flatnonzero(alpha.any(axis=1))
    if not rows.size:
        raise SubjectSeparationError()
    columns = np.flatnonzero(alpha.any(axis=0))
    return int(columns[0]), int(columns[-1]), int(rows[0]), int(rows[-1])


def scaled_kernel_size(size: int, scale: float) -> int:
    return max(1, 2 * round((size // 2) * scale) + 1)


def merge_subject_alpha(
    photo: Image.Image,
    yolo_alpha: np.ndarray,
    edge_scale: float,
    check_cancelled: CancellationCheck,
) -> tuple[np.ndarray, SubjectBounds]:
    from rembg import remove

    check_cancelled()
    with closing(
        remove(photo, session=model_runtime.get_background_session(), only_mask=True)
    ) as rembg_mask:
        # Native inference finishes its current call before cancellation can stop it.
        check_cancelled()
        final_alpha = np.array(rembg_mask, dtype=np.uint8)

    check_cancelled()
    # A selection gate needs room for uncertain outlines, not edge smoothing.
    kernel_size = scaled_kernel_size(41, edge_scale)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
    yolo_bin = (yolo_alpha > 0.5).astype(np.uint8)
    # YOLO selects the subject, but its coarse interior holes are not transparency.
    contours, _ = cv2.findContours(yolo_bin, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(yolo_bin, contours, -1, 1, cv2.FILLED)
    dilated = cv2.dilate(yolo_bin, kernel, iterations=2)
    final_alpha[dilated == 0] = 0.0
    del yolo_alpha, yolo_bin, dilated, contours
    check_cancelled()
    # Extra smoothing destroys individual strands and spreads background colour.
    return final_alpha, subject_bounds(final_alpha)
