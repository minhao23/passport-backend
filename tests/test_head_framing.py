import hashlib
import unittest
from threading import Event
from unittest.mock import Mock, patch

import numpy as np

from errors import ProcessingCancelledError
from services import head_framing
from services.photo_framing import _lower_edge_coverage, plan_framing


class HeadFramingTests(unittest.TestCase):
    def test_shipped_face_model_matches_upstream_weights(self):
        self.assertEqual(head_framing.FACE_MODEL_PATH.stat().st_size, 232589)
        self.assertEqual(
            hashlib.sha256(head_framing.FACE_MODEL_PATH.read_bytes()).hexdigest(),
            "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4",
        )

    def test_face_model_is_loaded_once_without_changing_cpu_defaults(self):
        head_framing._face_detector.cache_clear()
        try:
            with patch.object(head_framing.cv2.FaceDetectorYN, "create") as create:
                self.assertIs(
                    head_framing._face_detector(), head_framing._face_detector()
                )
                create.assert_called_once_with(
                    str(head_framing.FACE_MODEL_PATH), "", (320, 320), 0.9, 0.3, 50
                )
        finally:
            head_framing._face_detector.cache_clear()

    def test_face_inference_is_bounded_and_coordinates_map_to_source(self):
        photo = np.zeros((1024, 512, 3), dtype=np.uint8)
        person = np.ones((1024, 512), dtype=np.float32)
        detector = Mock(detect=Mock(return_value=(1, np.array([[20, 30, 80, 100]]))))
        with patch.object(head_framing, "_face_detector", return_value=detector):
            face = head_framing.detect_face(photo, person, lambda: None)
        self.assertEqual(face, (32, 48, 128, 160))
        detector.setInputSize.assert_called_once_with((320, 640))
        self.assertEqual(detector.detect.call_args.args[0].shape, (640, 320, 3))
        self.assertFalse(photo.any())
        self.assertTrue(person.all())

    def test_face_outside_selected_person_is_ignored(self):
        photo = np.zeros((320, 400, 3), dtype=np.uint8)
        person = np.zeros((320, 400), dtype=np.float32)
        person[:, 200:] = 1
        faces = np.array([[0, 0, 180, 180], [220, 60, 80, 100]])
        detector = Mock(detect=Mock(return_value=(1, faces)))
        with patch.object(head_framing, "_face_detector", return_value=detector):
            self.assertEqual(
                head_framing.detect_face(photo, person, lambda: None),
                (220, 60, 80, 100),
            )

    def test_missing_face_keeps_silhouette_fallback_available(self):
        detector = Mock(detect=Mock(return_value=(0, None)))
        with patch.object(head_framing, "_face_detector", return_value=detector):
            self.assertIsNone(
                head_framing.detect_face(
                    np.zeros((320, 240, 3), dtype=np.uint8),
                    np.ones((320, 240), dtype=np.float32),
                    lambda: None,
                )
            )

    def test_cancellation_after_face_inference_discards_detection(self):
        cancelled = Event()

        def detect(photo):
            cancelled.set()
            return 0, None

        def check_cancelled():
            if cancelled.is_set():
                raise ProcessingCancelledError()

        with patch.object(
            head_framing, "_face_detector", return_value=Mock(detect=detect)
        ):
            with self.assertRaises(ProcessingCancelledError):
                head_framing.detect_face(
                    np.zeros((320, 240, 3), dtype=np.uint8),
                    np.ones((320, 240), dtype=np.float32),
                    check_cancelled,
                )

    def test_face_guide_keeps_high_hair_and_does_not_measure_lower_torso(self):
        alpha = np.zeros((900, 400), dtype=np.uint8)
        alpha[20:180, 110:250] = 255
        alpha[180:230, 150:210] = 255
        alpha[230:, 60:300] = 255
        face = (140, 100, 80, 80)
        head = head_framing.find_head_bounds(alpha, face)
        self.assertEqual(head, (110, 249, 20, 187))
        self.assertEqual(head, head_framing.find_head_bounds(alpha[:400], face))

    def test_shoulder_support_below_the_face_does_not_widen_the_head(self):
        alpha = np.zeros((1024, 768), dtype=np.uint8)
        alpha[154, 382:425] = 255
        alpha[155:650, 125:646] = 255
        alpha[650:795, 2:710] = 255
        alpha[795:992, 2:] = 255
        face = (215, 321, 326, 438)

        self.assertEqual(
            head_framing.find_head_bounds(alpha, face),
            (125, 645, 154, 795),
        )
        (width, height), (dx, dy) = plan_framing(
            (768, 1024), alpha, (2, 767, 154, 991), (51, 51), face
        )
        coverage = _lower_edge_coverage(alpha, -dy + height, height)
        self.assertIsNotNone(coverage)
        self.assertTrue(np.all(coverage[[-dx, -dx + width - 1]] >= 0.9))
        self.assertGreaterEqual(-dy + height, 795)

    def test_plain_body_masks_are_not_mistaken_for_a_head(self):
        alpha = np.zeros((900, 400), dtype=np.uint8)
        alpha[80:, 100:300] = 255
        self.assertIsNone(head_framing.find_head_bounds(alpha))


if __name__ == "__main__":
    unittest.main()
