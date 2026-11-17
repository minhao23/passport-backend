"""Orchestrate the bounded passport-photo processing pipeline."""

from contextlib import closing
from threading import Event

import cv2
from PIL import Image

from errors import InvalidCountryError, ProcessingCancelledError
from services.photo_composition import compose_photo
from services.segmentation import merge_subject_alpha, person_alpha
from utils.image_loading import decode_photo
from utils.passport_sizes import passport_photo_sizes_mm


def create_passport_photo(
    image_bytes: bytes, country: str, cancelled: Event | None = None
) -> bytes:
    """Create a white-background JPEG with a bottom-anchored subject."""

    def check_cancelled() -> None:
        if cancelled is not None and cancelled.is_set():
            raise ProcessingCancelledError()

    check_cancelled()
    if country not in passport_photo_sizes_mm:
        raise InvalidCountryError()
    original_img, edge_scale = decode_photo(image_bytes)
    yolo_alpha = person_alpha(original_img, check_cancelled)

    check_cancelled()
    with closing(
        Image.fromarray(cv2.cvtColor(original_img, cv2.COLOR_BGR2RGB))
    ) as full_pil:
        # Drop source pixels before native background removal allocates its buffers.
        del original_img
        alpha, bounds = merge_subject_alpha(
            full_pil, yolo_alpha, edge_scale, check_cancelled
        )
        del yolo_alpha
        return compose_photo(
            full_pil, alpha, bounds, passport_photo_sizes_mm[country], check_cancelled
        )
