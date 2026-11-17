"""Compose and export the country-sized passport JPEG."""

import io
from collections.abc import Callable
from contextlib import closing

import numpy as np
from PIL import Image

from errors import SubjectTooSmallError


def compose_photo(
    photo: Image.Image,
    alpha: np.ndarray,
    bounds: tuple[int, int, int, int],
    size_mm: tuple[int, int],
    check_cancelled: Callable[[], None],
) -> bytes:
    check_cancelled()
    px1, px2, py1, py2 = bounds
    width_mm, height_mm = size_mm
    center_x = px1 + ((px2 - px1) / 2.0)

    # Preserve the 10% top margin and bottom-anchored composition.
    canvas_h = (py2 - py1) / 0.90
    canvas_w, canvas_h = int(canvas_h * (width_mm / height_mm)), int(canvas_h)
    if canvas_w < 1 or canvas_h < 1:
        raise SubjectTooSmallError()

    position = (int(canvas_w / 2 - center_x), int(canvas_h - py2))
    with closing(Image.new("RGB", (canvas_w, canvas_h), (255, 255, 255))) as canvas:
        with closing(Image.fromarray(alpha)) as mask:
            canvas.paste(photo, position, mask)
        check_cancelled()
        output_size = (int(width_mm * 11.81), int(height_mm * 11.81))
        final_image = canvas.resize(output_size, Image.Resampling.LANCZOS)

    with closing(final_image), io.BytesIO() as output:
        final_image.save(output, format="JPEG", quality=95)
        check_cancelled()
        return output.getvalue()
