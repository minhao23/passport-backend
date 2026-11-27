"""Validate image headers and decode a bounded working image."""

import io
from contextlib import closing
from functools import cache

import cv2
import numpy as np
from PIL import Image, UnidentifiedImageError

from errors import (
    EmptyPhotoError,
    ImageDimensionsError,
    InvalidPhotoError,
    UploadTooLargeError,
)
from utils.limits import (
    ACCEPTED_IMAGE_FORMATS,
    MAX_FILE_BYTES,
    MAX_SOURCE_PIXELS,
    MAX_SOURCE_SIDE,
    MAX_WORKING_SIDE,
)


def check_dimensions(width: int, height: int) -> None:
    if width < 1 or height < 1:
        raise InvalidPhotoError()
    if width * height > MAX_SOURCE_PIXELS or max(width, height) > MAX_SOURCE_SIDE:
        raise ImageDimensionsError()


def check_webp_header(data: bytes) -> None:
    """Bound WebP canvases and bitstreams before Pillow constructs a decoder."""
    if not (data[:4] == b"RIFF" and data[8:12] == b"WEBP"):
        return
    end = int.from_bytes(data[4:8], "little") + 8
    if end != len(data):
        raise InvalidPhotoError()
    offset = 12
    canvas = None
    image_size = None
    while offset < end:
        if offset + 8 > end:
            raise InvalidPhotoError()
        kind = data[offset : offset + 4]
        size = int.from_bytes(data[offset + 4 : offset + 8], "little")
        start = offset + 8
        offset = start + size + (size & 1)
        if offset > end:
            raise InvalidPhotoError()
        header = data[start : start + min(size, 10)]
        if kind == b"VP8X":
            if size != 10 or canvas is not None or start != 20:
                raise InvalidPhotoError()
            canvas = (
                1 + int.from_bytes(header[4:7], "little"),
                1 + int.from_bytes(header[7:10], "little"),
            )
            check_dimensions(*canvas)
            if header[0] & 2:
                raise InvalidPhotoError()
        elif kind in (b"ANIM", b"ANMF"):
            # Passport input is a still photo, not an animation with frame canvases.
            raise InvalidPhotoError()
        elif kind in (b"VP8 ", b"VP8L"):
            if image_size is not None:
                raise InvalidPhotoError()
            if kind == b"VP8 ":
                if size < 10 or header[0] & 1 or header[3:6] != b"\x9d\x01\x2a":
                    raise InvalidPhotoError()
                image_size = (
                    int.from_bytes(header[6:8], "little") & 0x3FFF,
                    int.from_bytes(header[8:10], "little") & 0x3FFF,
                )
            else:
                if size < 5 or header[0] != 0x2F:
                    raise InvalidPhotoError()
                bits = int.from_bytes(header[1:5], "little")
                image_size = (1 + (bits & 0x3FFF), 1 + ((bits >> 14) & 0x3FFF))
            check_dimensions(*image_size)
    if image_size is None or (canvas is not None and canvas != image_size):
        raise InvalidPhotoError()


@cache
def _register_heif() -> None:
    from pillow_heif import register_heif_opener

    register_heif_opener(
        decode_threads=1, thumbnails=False, depth_images=False, aux_images=False
    )


def decode_photo(image_bytes: bytes) -> tuple[np.ndarray, float]:
    """Return bounded BGR pixels and a working-image selection-gate scale."""
    if not image_bytes:
        raise EmptyPhotoError()
    if len(image_bytes) > MAX_FILE_BYTES:
        raise UploadTooLargeError()
    check_webp_header(image_bytes)
    heif = image_bytes[4:8] == b"ftyp"
    if heif:
        _register_heif()
    formats = ACCEPTED_IMAGE_FORMATS if heif else ACCEPTED_IMAGE_FORMATS - {"HEIF"}
    image = None

    try:
        # Restrict plugins before a decoder can allocate unsupported image data.
        with Image.open(io.BytesIO(image_bytes), formats=list(formats)) as header:
            if header.format not in ACCEPTED_IMAGE_FORMATS:
                raise InvalidPhotoError()
            image_format = header.format
            width, height = header.size
            check_dimensions(width, height)
            if image_format == "HEIF":
                # libheif applies HEIF rotation/mirroring and converts HDR to 8-bit.
                # Only the primary photo is decoded; depth/auxiliary images stay off.
                with closing(header.convert("RGB")) as rgb:
                    image = cv2.cvtColor(np.asarray(rgb), cv2.COLOR_RGB2BGR)
    except Image.DecompressionBombError as exc:
        raise ImageDimensionsError() from exc
    except (UnidentifiedImageError, OSError, ValueError, RuntimeError, EOFError) as exc:
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
        if image is None:
            image = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), decode_flag)
    except cv2.error as exc:
        raise InvalidPhotoError() from exc
    if image is None:
        raise InvalidPhotoError()

    decoded_height, decoded_width = image.shape[:2]
    check_dimensions(decoded_width, decoded_height)
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
    edge_scale = max(image.shape[:2]) / MAX_WORKING_SIDE
    return image, edge_scale
