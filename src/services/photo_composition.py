"""Compose and export the country-sized passport JPEG."""

import io
from collections.abc import Callable
from contextlib import closing

import numpy as np
from PIL import Image

from services.head_framing import FaceBox
from services.photo_framing import plan_framing


def compose_photo(
    photo: Image.Image,
    alpha: np.ndarray,
    bounds: tuple[int, int, int, int],
    size_mm: tuple[int, int],
    check_cancelled: Callable[[], None],
    face: FaceBox | None = None,
) -> bytes:
    check_cancelled()
    width_mm, height_mm = size_mm
    canvas_size, position = plan_framing(photo.size, alpha, bounds, size_mm, face)
    check_cancelled()
    with closing(Image.new("RGB", canvas_size, (255, 255, 255))) as canvas:
        with closing(Image.fromarray(alpha)) as mask:
            canvas.paste(photo, position, mask)
        check_cancelled()
        output_size = (int(width_mm * 11.81), int(height_mm * 11.81))
        final_image = canvas.resize(output_size, Image.Resampling.LANCZOS)

    with closing(final_image), io.BytesIO() as output:
        final_image.save(output, format="JPEG", quality=95)
        check_cancelled()
        return output.getvalue()
