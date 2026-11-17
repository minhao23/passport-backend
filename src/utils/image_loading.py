"""Validate image headers and decode a bounded working image."""

import io

import cv2
import numpy as np
from PIL import Image, UnidentifiedImageError

from errors import (
    EmptyPhotoError,
    ImageDimensionsError,
    InvalidPhotoError,
    UploadTooLargeError,
)
from utils.image_headers import check_dimensions, check_webp_header
from utils.limits import ACCEPTED_IMAGE_FORMATS, MAX_FILE_BYTES, MAX_WORKING_SIDE


def decode_photo(image_bytes: bytes) -> tuple[np.ndarray, float]:
    """Return BGR pixels and the scale used by the existing smoothing kernels."""
    if not image_bytes:
        raise EmptyPhotoError()
    if len(image_bytes) > MAX_FILE_BYTES:
        raise UploadTooLargeError()
    check_webp_header(image_bytes)

    try:
        # Restrict plugins before a decoder can allocate unsupported image data.
        with Image.open(
            io.BytesIO(image_bytes), formats=list(ACCEPTED_IMAGE_FORMATS)
        ) as header:
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

    decode_flag = cv2.IMREAD_COLOR
    if image_format == "JPEG":
        # Downsample during JPEG decoding rather than allocating full RGB first.
        for factor, flag in (
            (8, cv2.IMREAD_REDUCED_COLOR_8),
            (4, cv2.IMREAD_REDUCED_COLOR_4),
            (2, cv2.IMREAD_REDUCED_COLOR_2),
        ):
            if max(width, height) >= MAX_WORKING_SIDE * factor:
                decode_flag = flag
                break

    try:
        image = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), decode_flag)
    except cv2.error as exc:
        raise InvalidPhotoError() from exc
    if image is None:
        raise InvalidPhotoError()

    decoded_height, decoded_width = image.shape[:2]
    check_dimensions(decoded_width, decoded_height)
    edge_scale = min(1.0, MAX_WORKING_SIDE / min(max(width, height), 2048))
    if max(decoded_height, decoded_width) > MAX_WORKING_SIDE:
        scale = MAX_WORKING_SIDE / max(decoded_height, decoded_width)
        image = cv2.resize(
            image,
            (
                max(1, round(decoded_width * scale)),
                max(1, round(decoded_height * scale)),
            ),
            interpolation=cv2.INTER_AREA,
        )
    return image, edge_scale
