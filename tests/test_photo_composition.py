import io
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image, ImageDraw

from errors import ProcessingCancelledError, SubjectFramingError
from services.head_framing import find_head_bounds
from services.photo_composition import compose_photo
from services.photo_framing import _lower_edge_coverage, plan_framing
from utils.passport_sizes import passport_photo_sizes_mm


def portrait():
    photo = Image.new("RGB", (240, 320), (35, 55, 75))
    mask = Image.new("L", photo.size, 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((60, 60, 180, 190), fill=255)
    draw.rectangle((95, 175, 145, 215), fill=255)
    draw.polygon(
        [(0, 210), (70, 190), (170, 190), (239, 210), (239, 319), (0, 319)],
        fill=255,
    )
    alpha = np.array(mask)
    mask.close()
    return photo, alpha, (0, 239, 60, 319)


def long_portrait(height=900):
    original, original_alpha, _ = portrait()
    original.close()
    photo = Image.new("RGB", (240, height), (35, 55, 75))
    alpha = np.full((height, 240), 255, dtype=np.uint8)
    alpha[:320] = original_alpha
    return photo, alpha, (0, 239, 60, height - 1)


class PhotoCompositionTests(unittest.TestCase):
    def test_clean_crops_keep_full_width_regardless_of_head_size(self):
        photo, alpha, bounds = portrait()
        with photo:
            self.assertEqual(
                plan_framing(photo.size, alpha, bounds, (51, 51)),
                ((240, 240), (0, 0)),
            )

        for name, head_bottom, face in (
            ("small head", 180, (170, 60, 70, 100)),
            ("tall head", 330, (145, 60, 110, 260)),
        ):
            with self.subTest(head=name):
                alpha = np.zeros((400, 400), dtype=np.uint8)
                if name == "small head":
                    alpha[20:head_bottom, 100:260] = 255
                    alpha[head_bottom:] = 255
                else:
                    alpha[20:head_bottom, 90:310] = 255
                    alpha[330:350, 175:225] = 255
                    alpha[350:] = 255
                self.assertEqual(
                    plan_framing((400, 400), alpha, (0, 399, 20, 399), (51, 51), face),
                    ((400, 400), (0, 0)),
                )

    def test_repositioning_is_tried_before_zooming_into_a_tapered_torso(self):
        alpha = np.zeros((500, 400), dtype=np.uint8)
        alpha[80:240, 100:300] = 255
        alpha[240:250, 175:225] = 255
        alpha[250:420] = 255
        alpha[420:, 150:250] = 255
        self.assertEqual(
            plan_framing(
                (400, 500), alpha, (0, 399, 80, 499), (51, 51), (150, 110, 100, 110)
            ),
            ((400, 400), (0, 0)),
        )

    def test_extra_headroom_prefers_cleaner_same_width_positions(self):
        original_alpha = np.zeros((560, 400), dtype=np.uint8)
        original_alpha[140:300, 100:300] = 255
        original_alpha[300:320, 175:225] = 255
        for row in range(320, 560):
            margin = max(0, 100 - (row - 320))
            original_alpha[row, margin : 400 - margin] = 255
        before = original_alpha.copy()
        for removed_top, expected_top in ((0, 38), (100, 0)):
            alpha = original_alpha[removed_top:]
            face = (150, 175 - removed_top, 100, 110)
            bounds = (0, 399, 140 - removed_top, 559 - removed_top)
            with (
                self.subTest(removed_top=removed_top),
                Image.new("RGB", (400, alpha.shape[0]), (35, 55, 75)) as photo,
            ):
                size, position = plan_framing(photo.size, alpha, bounds, (51, 51), face)
                self.assertEqual(size, (400, 400))
                self.assertEqual(position, (0, -expected_top))
                coverage = _lower_edge_coverage(alpha, expected_top + 400, 400)
                self.assertTrue(np.all(coverage[[0, 399]] >= 0.90))
                output = compose_photo(
                    photo, alpha, bounds, (51, 51), lambda: None, face
                )
                with Image.open(io.BytesIO(output)) as result:
                    self.assertEqual(result.size, (602, 602))
                    self.assertLess(int(np.array(result)[-1, [0, -1]].max()), 110)
        np.testing.assert_array_equal(original_alpha, before)

    def test_slope_fallback_minimizes_gaps_without_additional_zoom(self):
        alpha = np.zeros((450, 400), dtype=np.uint8)
        alpha[80:240, 100:300] = 255
        alpha[240:280, 175:225] = 255
        for row in range(260, 450):
            margin = min(175, max(0, 200 - (row - 260)))
            alpha[row, margin : 400 - margin] = 255
        size, position = plan_framing(
            (400, 450), alpha, (11, 388, 80, 449), (51, 51), (150, 110, 100, 110)
        )
        self.assertEqual(size, (400, 400))
        self.assertEqual(position, (0, -50))
        self.assertFalse(np.any(_lower_edge_coverage(alpha, 450, 400)[[0, 399]]))
        self.assertEqual(np.flatnonzero(alpha[449] >= 128)[[0, -1]].tolist(), [11, 388])

    def test_strict_positions_minimize_bottom_gaps_before_retaining_headroom(self):
        for support in ("narrow", "empty"):
            alpha = np.zeros((500, 400), dtype=np.uint8)
            alpha[80:240, 100:300] = 255
            alpha[240:250, 175:225] = 255
            alpha[250:] = 255
            alpha[399] = 0
            if support == "narrow":
                alpha[399, 150:250] = 255
            with self.subTest(support=support):
                self.assertTrue(
                    np.all(_lower_edge_coverage(alpha, 400, 400)[[0, 399]] >= 0.90)
                )
                self.assertEqual(
                    plan_framing(
                        (400, 500),
                        alpha,
                        (0, 399, 80, 499),
                        (51, 51),
                        (150, 110, 100, 110),
                    ),
                    ((400, 400), (0, -1)),
                )

    def test_headroom_and_sloping_shoulders_do_not_force_extra_zoom(self):
        for outline, expected_width in (("sloping", 400), ("flat cutoff", 390)):
            alpha = np.zeros((400, 400), dtype=np.uint8)
            alpha[20:200, 100:300] = 255
            for row in range(200, 400):
                right = 300 + (row - 200) // 2 if outline == "sloping" else 389
                alpha[row, : right + 1] = 255
            with self.subTest(outline=outline):
                (width, height), (dx, dy) = plan_framing(
                    (400, 400), alpha, (0, 399, 20, 399), (51, 51), (160, 60, 80, 100)
                )
                self.assertEqual(width, expected_width)
                self.assertGreaterEqual(20 + dy, np.ceil(height * 0.05))
                self.assertGreaterEqual(100 + dx, 1)

        alpha = np.zeros((1024, 768), dtype=np.uint8)
        alpha[137:650, 106:658] = 255
        for row in range(650, 1024):
            right = min(767, 600 + int((row - 650) * 0.9))
            alpha[row, : right + 1] = 255
        face = (215, 321, 326, 438)
        (width, height), (_, dy) = plan_framing(
            (768, 1024), alpha, (0, 767, 137, 1023), (51, 51), face
        )
        _, _, top, chin = find_head_bounds(alpha, face)
        self.assertEqual(width, 768)
        self.assertGreaterEqual(top + dy, np.ceil(height * 0.05))
        self.assertGreaterEqual(height - chin - dy - 1, np.ceil((chin - top + 1) * 0.1))

    def test_extra_torso_is_kept_when_the_largest_crop_can_include_it(self):
        original, alpha, bounds = portrait()
        tall, tall_alpha, tall_bounds = long_portrait()
        with original, tall:
            for country, size_mm in passport_photo_sizes_mm.items():
                with self.subTest(country=country):
                    short_size, _ = plan_framing(original.size, alpha, bounds, size_mm)
                    tall_size, (_, y) = plan_framing(
                        tall.size, tall_alpha, tall_bounds, size_mm
                    )
                    self.assertEqual(tall_size[0], tall.width)
                    self.assertGreaterEqual(
                        tall_size[0] * tall_size[1], short_size[0] * short_size[1]
                    )
                    self.assertEqual(y, 0, "Keep the original headroom when it fits")
            output = compose_photo(
                tall, tall_alpha, tall_bounds, (51, 51), lambda: None
            )
        with Image.open(io.BytesIO(output)) as result:
            pixels = np.array(result)
            self.assertEqual(result.size, (602, 602))
        self.assertLess(int(pixels[-30:, [0, -1]].max()), 110)
        self.assertGreater(int(pixels[0].min()), 245)

    def test_face_guide_centers_face_not_asymmetric_hair(self):
        alpha = np.zeros((400, 400), dtype=np.uint8)
        alpha[20:180, 100:260] = 255
        alpha[180:] = 255
        face = (170, 60, 70, 100)
        (width, _), (x, _) = plan_framing(
            (400, 400), alpha, (0, 399, 20, 399), (50, 70), face
        )
        self.assertAlmostEqual(face[0] + face[2] / 2 + x, width / 2, delta=0.5)

    def test_removed_face_is_rejected_even_when_torso_fills_the_frame(self):
        alpha = np.zeros((400, 400), dtype=np.uint8)
        alpha[200:] = 255
        with self.assertRaises(SubjectFramingError):
            plan_framing(
                (400, 400), alpha, (0, 399, 200, 399), (51, 51), (160, 60, 80, 100)
            )

    def test_wide_source_with_inset_mask_has_no_shoulder_strips(self):
        photo, narrow_alpha, _ = portrait()
        photo.close()
        alpha = np.zeros((320, 400), dtype=np.uint8)
        alpha[:, 80:320] = narrow_alpha
        with Image.new("RGB", (400, 320), (35, 55, 75)) as source:
            self.assertEqual(
                plan_framing(source.size, alpha, (80, 319, 60, 319), (51, 51)),
                ((240, 240), (-80, 0)),
            )
            for size_mm in set(passport_photo_sizes_mm.values()):
                with self.subTest(size=size_mm):
                    output = compose_photo(
                        source, alpha, (80, 319, 60, 319), size_mm, lambda: None
                    )
                    with Image.open(io.BytesIO(output)) as result:
                        pixels = np.array(result)
                        self.assertEqual(
                            result.size, tuple(int(mm * 11.81) for mm in size_mm)
                        )
                        self.assertEqual(result.mode, "RGB")
                        np.testing.assert_allclose(
                            result.getpixel((0, 0)), (255, 255, 255), atol=3
                        )
                    band_height = int(np.ceil(pixels.shape[0] * 0.05))
                    for side in (
                        pixels[-band_height:, :3],
                        pixels[-band_height:, -3:],
                    ):
                        self.assertLess(
                            int(side.max()), 110, "Mask must cover both lower edges"
                        )

    def test_source_coverage_does_not_allow_an_unframeable_narrow_mask(self):
        alpha = np.zeros((400, 600), dtype=np.uint8)
        alpha[80:, 210:390] = 255
        with (
            Image.new("RGB", (600, 400)) as photo,
            patch.object(Image, "new") as allocate,
        ):
            with self.assertRaises(SubjectFramingError):
                compose_photo(photo, alpha, (210, 389, 80, 399), (51, 51), lambda: None)
            allocate.assert_not_called()

    def test_faint_bounds_do_not_shift_a_crop_away_from_the_subject(self):
        photo, narrow_alpha, _ = portrait()
        photo.close()
        alpha = np.zeros((320, 400), dtype=np.uint8)
        alpha[:, 80:320] = narrow_alpha
        alpha[60:, 0] = 1
        before = alpha.copy()
        size, position = plan_framing(
            (240, 320), narrow_alpha, (0, 239, 60, 319), (51, 51)
        )
        self.assertEqual(
            plan_framing((400, 320), alpha, (0, 319, 60, 319), (51, 51)),
            (size, (position[0] - 80, position[1])),
        )
        np.testing.assert_array_equal(alpha, before)

    def test_crop_can_shift_to_real_shoulders_without_clipping_upper_subject(self):
        alpha = np.zeros((320, 400), dtype=np.uint8)
        alpha[60:190, 150:240] = 255
        alpha[180:220, 180:210] = 255
        alpha[210:, 60:300] = 255
        (width, _), (x, _) = plan_framing(
            (400, 320), alpha, (60, 299, 60, 319), (51, 51)
        )
        self.assertGreaterEqual(-x, 60)
        self.assertLessEqual(-x + width, 300)
        self.assertLessEqual(-x, 150)
        self.assertGreaterEqual(-x + width, 240)
        self.assertNotEqual(-x + width / 2, 195, "Shift away from missing shoulders")

    def test_removing_strips_cannot_clip_wide_upper_subject(self):
        alpha = np.zeros((320, 400), dtype=np.uint8)
        alpha[60:160, 20:380] = 255
        alpha[160:210, 170:230] = 255
        alpha[190:, 80:320] = 255
        with self.assertRaises(SubjectFramingError):
            plan_framing((400, 320), alpha, (20, 379, 60, 319), (51, 51))

    def test_crop_keeps_head_and_headroom_without_changing_source_pixels(self):
        photo, alpha, bounds = portrait()
        before = alpha.copy()
        with photo:
            size, position = plan_framing(photo.size, alpha, bounds, (51, 51))
            head = find_head_bounds(alpha)
            self.assertIsNotNone(head)
            left, right, top, bottom = head
            self.assertGreaterEqual(left + position[0], 1)
            self.assertLess(right + position[0], size[0] - 1)
            self.assertLess(bottom + position[1], size[1])
            self.assertEqual(top + position[1], top, "Retain existing headroom")
            self.assertGreater(-position[1] + size[1], 215)
            self.assertEqual(photo.getpixel((120, 120)), (35, 55, 75))
        np.testing.assert_array_equal(alpha, before)

    def test_export_preserves_proportions_and_jpeg_settings(self):
        photo, alpha, bounds = portrait()
        with photo:
            size, position = plan_framing(photo.size, alpha, bounds, (50, 70))
            with (
                Image.new("RGB", size, "white") as canvas,
                Image.fromarray(alpha) as mask,
                io.BytesIO() as expected,
            ):
                canvas.paste(photo, position, mask)
                with canvas.resize((590, 826), Image.Resampling.LANCZOS) as resized:
                    resized.save(expected, format="JPEG", quality=95)
                self.assertEqual(
                    compose_photo(photo, alpha, bounds, (50, 70), lambda: None),
                    expected.getvalue(),
                )

    def test_off_center_subjects_do_not_get_one_sided_padding(self):
        original, original_alpha, original_bounds = portrait()
        with original:
            expected_size, expected_position = plan_framing(
                original.size, original_alpha, original_bounds, (51, 51)
            )
        for left in (0, 360):
            alpha = np.zeros((320, 600), dtype=np.uint8)
            alpha[:, left : left + 240] = original_alpha
            bounds = (left, left + 239, 60, 319)
            with (
                self.subTest(left=left),
                Image.new("RGB", (600, 320), (35, 55, 75)) as photo,
            ):
                size, position = plan_framing(photo.size, alpha, bounds, (51, 51))
                self.assertEqual(size, expected_size)
                self.assertEqual(
                    position,
                    (expected_position[0] - left, expected_position[1]),
                )
                output = compose_photo(photo, alpha, bounds, (51, 51), lambda: None)
                with Image.open(io.BytesIO(output)) as result:
                    self.assertLess(int(np.array(result)[-60:, [0, -1]].max()), 110)

    def test_unknown_head_is_not_blindly_zoomed_before_canvas_allocation(self):
        alpha = np.full((1000, 100), 255, dtype=np.uint8)
        with (
            Image.new("RGB", (100, 1000)) as photo,
            patch.object(Image, "new") as allocate,
        ):
            with self.assertRaises(SubjectFramingError):
                compose_photo(photo, alpha, (0, 99, 0, 999), (51, 51), lambda: None)
            allocate.assert_not_called()

    def test_head_or_neck_only_crop_is_not_used_to_remove_side_strips(self):
        photo, alpha, bounds = portrait()
        alpha[190:290] = 0
        alpha[190:290, 95:145] = 255
        with photo, self.assertRaises(SubjectFramingError):
            plan_framing(photo.size, alpha, bounds, (51, 51))

    def test_soft_mask_fringes_are_not_treated_as_filled_shoulders(self):
        for side in (0, -1):
            photo, alpha, bounds = portrait()
            alpha[:, side] = 127
            with self.subTest(side=side), photo, self.assertRaises(SubjectFramingError):
                plan_framing(photo.size, alpha, bounds, (51, 51))

    def test_edge_coverage_threshold_matches_position_search(self):
        for missing_rows, expected_width in ((2, 400), (3, 399)):
            alpha = np.zeros((400, 400), dtype=np.uint8)
            alpha[20:180, 100:260] = 255
            alpha[180:] = 255
            alpha[-missing_rows:, 0] = 0
            with self.subTest(missing_rows=missing_rows):
                original_coverage = _lower_edge_coverage(alpha, 400, 400)
                self.assertEqual(
                    bool(np.all(original_coverage[[0, 399]] >= 0.90)),
                    expected_width == 400,
                )
                (width, height), (x, y) = plan_framing(
                    (400, 400), alpha, (0, 399, 20, 399), (51, 51), (170, 60, 70, 100)
                )
                self.assertEqual(width, expected_width)
                coverage = _lower_edge_coverage(alpha, -y + height, height)
                self.assertTrue(np.all(coverage[[-x, -x + width - 1]] >= 0.90))

    def test_cancellation_prevents_framing_and_canvas_allocation(self):
        def cancelled():
            raise ProcessingCancelledError()

        photo, alpha, bounds = portrait()
        with photo, patch.object(Image, "new") as allocate:
            with self.assertRaises(ProcessingCancelledError):
                compose_photo(photo, alpha, bounds, (51, 51), cancelled)
            allocate.assert_not_called()


if __name__ == "__main__":
    unittest.main()
