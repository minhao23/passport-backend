"""Locate a face and estimate crown-to-chin support without measuring the torso."""

from collections.abc import Callable
from functools import lru_cache
from math import ceil, floor
from pathlib import Path
from threading import Lock

import cv2
import numpy as np

FaceBox = tuple[int, int, int, int]
HeadBounds = tuple[int, int, int, int]
FACE_MODEL_PATH = (
    Path(__file__).resolve().parents[1] / "assets" / "face_detection_yunet_2023mar.onnx"
)
MAX_FACE_SIDE = 640
face_lock = Lock()


@lru_cache(maxsize=1)
def _face_detector():
    return cv2.FaceDetectorYN.create(str(FACE_MODEL_PATH), "", (320, 320), 0.9, 0.3, 50)


def detect_face(
    photo: np.ndarray, person_alpha: np.ndarray, check_cancelled: Callable[[], None]
) -> FaceBox | None:
    """Use bounded CPU inference and keep only a face inside the selected person."""
    check_cancelled()
    height, width = photo.shape[:2]
    scale = min(1.0, MAX_FACE_SIDE / max(width, height))
    preview = (
        cv2.resize(photo, (round(width * scale), round(height * scale)))
        if scale < 1
        else photo
    )
    with face_lock:
        check_cancelled()
        detector = _face_detector()
        detector.setInputSize((preview.shape[1], preview.shape[0]))
        _, faces = detector.detect(preview)
    check_cancelled()
    if faces is None:
        return None

    candidates = []
    for face in faces:
        x, y, w, h = face[:4] / scale
        left, top = max(0, floor(x)), max(0, floor(y))
        right, bottom = min(width, ceil(x + w)), min(height, ceil(y + h))
        if right <= left or bottom <= top:
            continue
        if np.mean(person_alpha[top:bottom, left:right] > 0.5) >= 0.5:
            candidates.append((left, top, right - left, bottom - top))
    return max(candidates, key=lambda box: box[2] * box[3], default=None)


def _support_bounds(alpha: np.ndarray, top: int, bottom: int) -> HeadBounds | None:
    support = alpha[top : bottom + 1] >= 32
    rows = np.flatnonzero(support.any(axis=1))
    columns = np.flatnonzero(support.any(axis=0))
    if not rows.size:
        return None
    return (
        int(columns[0]),
        int(columns[-1]),
        top + int(rows[0]),
        bottom,
    )


def find_head_bounds(
    alpha: np.ndarray, face: FaceBox | None = None
) -> HeadBounds | None:
    """Prefer a face guide; otherwise require a recognizable head/neck silhouette."""
    if face is not None:
        x, y, width, height = face
        facial_mask = alpha[y : y + height, x : x + width]
        if not facial_mask.size or np.mean(facial_mask >= 128) < 0.5:
            return None
        bottom = min(alpha.shape[0] - 1, ceil(y + height * 1.08))
        return _support_bounds(alpha, 0, bottom)

    opaque = alpha >= 128
    rows = np.flatnonzero(opaque.any(axis=1))
    if not rows.size:
        return None
    top = int(rows[0])
    occupied = opaque[top : int(rows[-1]) + 1]
    left = occupied.argmax(axis=1)
    right = alpha.shape[1] - 1 - occupied[:, ::-1].argmax(axis=1)
    spans = np.where(occupied.any(axis=1), right - left + 1, 0)
    spans = np.convolve(np.pad(spans, (2, 2), mode="edge"), np.ones(5) / 5, "valid")
    peak = 0.0
    for offset, span in enumerate(spans):
        peak = max(peak, float(span))
        if peak < 8 or span <= 0 or span > peak * 0.65:
            continue
        # A neck narrows shortly below a head, then widens into shoulders.
        # The distance is relative to head width, never total body height.
        if not peak * 0.7 <= offset <= peak * 2:
            continue
        end = min(len(spans), offset + ceil(peak * 0.6))
        shoulders = np.flatnonzero(spans[offset:end] >= peak * 0.9)
        if not shoulders.size:
            continue
        shoulder = offset + int(shoulders[0])
        if shoulder <= offset:
            continue
        neck = offset + int(np.argmin(spans[offset:shoulder]))
        return _support_bounds(alpha, top, top + neck)
    return None
