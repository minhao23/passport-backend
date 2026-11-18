import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np
from PIL import Image

with patch.dict(
    sys.modules, {"rembg.sessions.base": SimpleNamespace(BaseSession=object)}
):
    from services.modnet_session import (
        MODEL_SHA256,
        MODEL_URL,
        ModnetPortraitSession,
    )

from services.photo_composition import _edge_foreground


class PortraitMattingTests(unittest.TestCase):
    def test_matte_inputs_preserve_aspect_and_bounded_rgb_normalization(self):
        for size in ((800, 1200), (1200, 800), (1024, 1024), (64, 32)):
            with (
                self.subTest(size=size),
                Image.new("RGB", size, (0, 127, 255)) as photo,
            ):
                session = object.__new__(ModnetPortraitSession)

                def infer(_, inputs, size=size):
                    tensor = inputs["portrait"]
                    self.assertEqual(tensor.dtype, np.float32)
                    self.assertTrue(tensor.flags.c_contiguous)
                    height, width = tensor.shape[2:]
                    self.assertLessEqual(max(width, height), 512)
                    self.assertEqual(width % 32, 0)
                    self.assertEqual(height % 32, 0)
                    self.assertAlmostEqual(width / height, size[0] / size[1], delta=0.1)
                    np.testing.assert_allclose(
                        tensor[0, :, 0, 0], (-1, -1 / 255, 1), atol=1e-7
                    )
                    return [np.full((1, 1, height, width), 0.5, dtype=np.float32)]

                session.inner_session = Mock(
                    get_inputs=Mock(return_value=[SimpleNamespace(name="portrait")]),
                    run=Mock(side_effect=infer),
                )
                with session.predict(photo)[0] as mask:
                    self.assertEqual(mask.size, photo.size)
                    self.assertEqual(mask.mode, "L")
                    self.assertEqual(mask.getpixel((0, 0)), 127)
                self.assertEqual(photo.getpixel((0, 0)), (0, 127, 255))

    def test_weight_cache_is_revision_pinned_and_checksum_verified(self):
        with (
            patch.object(
                ModnetPortraitSession,
                "model_dir",
                return_value="/tmp/models/modnet",
                create=True,
            ),
            patch(
                "services.modnet_session.pooch.retrieve", return_value="/tmp/model.onnx"
            ) as retrieve,
        ):
            self.assertEqual(ModnetPortraitSession.download_models(), "/tmp/model.onnx")
        retrieve.assert_called_once_with(
            MODEL_URL,
            known_hash=f"sha256:{MODEL_SHA256}",
            fname="modnet-portrait.onnx",
            path="/tmp/models/modnet",
        )
        self.assertIn("fa2fa546052fba4c08921230a26cc69a333fca12", MODEL_URL)

    def test_colour_recovery_changes_only_partially_transparent_pixels(self):
        alpha = np.array([[128, 250, 255]], dtype=np.uint8)
        cutout = Image.new("RGBA", (3, 1), (90, 100, 110, 128))
        with (
            Image.new("RGB", (3, 1), (25, 35, 45)) as photo,
            patch.dict(
                sys.modules,
                {
                    "rembg.bg": SimpleNamespace(
                        decontaminate_cutout=Mock(return_value=cutout)
                    )
                },
            ),
        ):
            with _edge_foreground(photo, alpha) as recovered:
                self.assertEqual(recovered.getpixel((0, 0)), (90, 100, 110))
                self.assertEqual(recovered.getpixel((1, 0)), (25, 35, 45))
                self.assertEqual(recovered.getpixel((2, 0)), (25, 35, 45))
            self.assertEqual(photo.getpixel((0, 0)), (25, 35, 45))
        with self.assertRaises(ValueError):
            cutout.getpixel((0, 0))
