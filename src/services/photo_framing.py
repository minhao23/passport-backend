"""Choose a country-aspect frame without padding cropped shoulders."""

from math import ceil, floor

import numpy as np

from errors import SubjectFramingError, SubjectTooSmallError
from services.head_framing import FaceBox, find_head_bounds

FALLBACK_HEADROOM = 0.10
MIN_HEADROOM = 0.05
MIN_BELOW_CHIN = 0.10
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
    min_width = max(
        head_right - head_left + 1 + side_margin * 2,
        ceil(head_height * aspect),
    )
    # Cumulative counts keep the position search from repeatedly scanning pixels.
    foreground = alpha >= 128
    row_counts = np.empty((alpha.shape[0] + 1, alpha.shape[1]), dtype=np.uint32)
    row_counts[0] = 0
    np.cumsum(foreground, axis=0, dtype=np.uint32, out=row_counts[1:])
    row_present = foreground.any(axis=1)
    row_left = foreground.argmax(axis=1)
    row_right = source_width - 1 - foreground[:, ::-1].argmax(axis=1)
    max_step = max(2, ceil(source_width * 0.005))
    left_breaks = np.concatenate(([0], np.cumsum(np.abs(np.diff(row_left)) > max_step)))
    right_breaks = np.concatenate(
        ([0], np.cumsum(np.abs(np.diff(row_right)) > max_step))
    )
    del foreground

    # Each smaller source crop means more zoom at export. Stop at the first fit
    # so head size never forces extra cropping, and the search stays bounded.
    for crop_width in range(source_width, min_width - 1, -1):
        crop_height = floor(crop_width / aspect)
        top_margin = min(head_top, ceil(crop_height * MIN_HEADROOM))
        below_chin = ceil(head_height * MIN_BELOW_CHIN)
        min_top = max(0, head_bottom + below_chin - crop_height + 1)
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
        clean_left = (
            row_counts[bottoms, left_edges] - row_counts[band_starts, left_edges]
            >= required
        )
        clean_right = (
            row_counts[bottoms, right_edges] - row_counts[band_starts, right_edges]
            >= required
        )
        strict = clean_left & clean_right
        # A naturally sloping shoulder can leave a small white corner. A flat,
        # inset mask cutoff cannot: do not confuse it with harmless background.
        starts, ends = band_starts, bottoms - 1
        slope = max(2, ceil(crop_width * 0.01))
        gap = ceil(crop_width * 0.10)
        candidates = np.arange(min_left, max_left + 1)
        shoulders_present = row_present[starts] & row_present[ends]
        natural_left = (
            shoulders_present
            & (row_left[starts] - row_left[ends] >= slope)
            & (left_breaks[ends] == left_breaks[starts])
        )
        natural_right = (
            shoulders_present
            & (row_right[ends] - row_right[starts] >= slope)
            & (right_breaks[ends] == right_breaks[starts])
        )
        clean_left |= natural_left[:, None] & (
            row_left[ends, None] <= candidates[None, :] + gap
        )
        clean_right |= natural_right[:, None] & (
            row_right[ends, None] >= candidates[None, :] + crop_width - 1 - gap
        )
        # Use sloping corners only when no strictly supported position fits.
        clean = strict if strict.any() else clean_left & clean_right
        rows, columns = np.nonzero(clean)
        if rows.size:
            candidates = columns + min_left
            last_rows = ends[rows]
            left_gaps = np.maximum(row_left[last_rows] - candidates, 0)
            right_gaps = np.maximum(
                candidates + crop_width - 1 - row_right[last_rows], 0
            )
            # An empty row's argmax boundaries otherwise look like filled edges.
            left_gaps[~row_present[last_rows]] = crop_width
            right_gaps[~row_present[last_rows]] = crop_width
            order = np.lexsort(
                (
                    np.abs(candidates + crop_width / 2 - center_x),
                    tops[rows],
                    left_gaps + right_gaps,
                    np.maximum(left_gaps, right_gaps),
                )
            )
            chosen = int(order[0])
            top = int(tops[rows[chosen]])
            left = int(candidates[chosen])
            return (crop_width, crop_height), (-left, -top)
    raise SubjectFramingError()
