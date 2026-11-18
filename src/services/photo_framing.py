"""Choose a country-aspect frame without padding cropped shoulders."""

from math import ceil, floor

import numpy as np

from errors import SubjectFramingError, SubjectTooSmallError
from services.head_framing import FaceBox, find_head_bounds

FALLBACK_HEADROOM = 0.10
EDGE_BAND = 0.05
MIN_EDGE_COVERAGE = 0.90


def _lower_edge_coverage(
    alpha: np.ndarray, bottom: int, height: int
) -> np.ndarray | None:
    band_height = max(1, ceil(height * EDGE_BAND))
    if bottom > alpha.shape[0] or bottom - band_height < 0:
        return None
    return np.mean(alpha[bottom - band_height : bottom] >= 128, axis=0)


def plan_framing(
    image_size: tuple[int, int],
    alpha: np.ndarray,
    bounds: tuple[int, int, int, int],
    size_mm: tuple[int, int],
    face: FaceBox | None = None,
) -> tuple[tuple[int, int], tuple[int, int]]:
    """Keep the largest clean country-aspect crop without clipping the head."""
    px1, px2, py1, py2 = bounds
    width_mm, height_mm = size_mm
    aspect = width_mm / height_mm
    source_width, source_height = image_size
    if py2 <= py1:
        raise SubjectTooSmallError()
    head = find_head_bounds(alpha, face)
    if head is None:
        if face is not None:
            raise SubjectFramingError()
        # Do not zoom blindly when neither face nor silhouette gives a head cue.
        # Keep an already clean frame; otherwise reject rather than cut the head.
        height = int((py2 - py1) / (1 - FALLBACK_HEADROOM))
        width = int(height * aspect)
        if width < 1 or height < 1:
            raise SubjectTooSmallError()
        position = (int(width / 2 - (px1 + px2) / 2), int(height - py2))
        left = -position[0]
        coverage = _lower_edge_coverage(alpha, py2, height)
        if (
            left >= 0
            and left + width <= source_width
            and coverage is not None
            and np.all(coverage[[left, left + width - 1]] >= MIN_EDGE_COVERAGE)
        ):
            return (width, height), position
        raise SubjectFramingError()

    head_left, head_right, head_top, head_bottom = head
    head_height = head_bottom - head_top + 1
    center_x = face[0] + face[2] / 2 if face else (head_left + head_right + 1) / 2
    side_margin = max(1, ceil((head_right - head_left + 1) * 0.02))
    top_margin = min(1, head_top)
    min_width = max(
        head_right - head_left + 1 + side_margin * 2,
        ceil((head_height + top_margin) * aspect),
    )
    # Cumulative counts keep the position search from repeatedly scanning pixels.
    row_counts = np.empty((alpha.shape[0] + 1, alpha.shape[1]), dtype=np.uint32)
    row_counts[0] = 0
    np.cumsum(alpha >= 128, axis=0, dtype=np.uint32, out=row_counts[1:])

    # Each smaller source crop means more zoom at export. Stop at the first fit
    # so head size never forces extra cropping, and the search stays bounded.
    for crop_width in range(source_width, min_width - 1, -1):
        crop_height = floor(crop_width / aspect)
        min_top = max(0, head_bottom - crop_height + 1)
        max_top = min(head_top - top_margin, source_height - crop_height)
        if min_top > max_top:
            continue
        min_left = max(0, head_right + side_margin - crop_width + 1)
        max_left = min(head_left - side_margin, source_width - crop_width)
        if min_left > max_left:
            continue

        tops = np.arange(min_top, max_top + 1)
        bottoms = tops + crop_height
        band_height = max(1, ceil(crop_height * EDGE_BAND))
        band_starts = bottoms - band_height
        required = ceil(band_height * MIN_EDGE_COVERAGE)
        left_edges = slice(min_left, max_left + 1)
        right_edges = slice(min_left + crop_width - 1, max_left + crop_width)
        clean = (
            row_counts[bottoms, left_edges] - row_counts[band_starts, left_edges]
            >= required
        )
        clean &= (
            row_counts[bottoms, right_edges] - row_counts[band_starts, right_edges]
            >= required
        )
        valid_tops = np.flatnonzero(clean.any(axis=1))
        if valid_tops.size:
            # Prefer retaining existing headroom; never pad to force a head ratio.
            index = int(valid_tops[0])
            top = int(tops[index])
            candidates = np.flatnonzero(clean[index]) + min_left
            nearest = np.argmin(np.abs(candidates + crop_width / 2 - center_x))
            left = int(candidates[nearest])
            return (crop_width, crop_height), (-left, -top)
    raise SubjectFramingError()
