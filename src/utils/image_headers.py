from errors import ImageDimensionsError, InvalidPhotoError
from utils.limits import MAX_SOURCE_PIXELS, MAX_SOURCE_SIDE


def check_dimensions(width, height):
    if width < 1 or height < 1:
        raise InvalidPhotoError()
    if width * height > MAX_SOURCE_PIXELS or max(width, height) > MAX_SOURCE_SIDE:
        raise ImageDimensionsError()


def check_webp_header(data):
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
        kind = data[offset:offset + 4]
        size = int.from_bytes(data[offset + 4:offset + 8], "little")
        start = offset + 8
        offset = start + size + (size & 1)
        if offset > end:
            raise InvalidPhotoError()
        header = data[start:start + min(size, 10)]
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
                    int.from_bytes(header[6:8], "little") & 0x3fff,
                    int.from_bytes(header[8:10], "little") & 0x3fff,
                )
            else:
                if size < 5 or header[0] != 0x2f:
                    raise InvalidPhotoError()
                bits = int.from_bytes(header[1:5], "little")
                image_size = (1 + (bits & 0x3fff), 1 + ((bits >> 14) & 0x3fff))
            check_dimensions(*image_size)
    if image_size is None or (canvas is not None and canvas != image_size):
        raise InvalidPhotoError()
