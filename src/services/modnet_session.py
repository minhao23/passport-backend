"""Bounded portrait matting through rembg's existing CPU ONNX session API."""

from contextlib import closing

import numpy as np
import pooch
from PIL import Image
from rembg.sessions.base import BaseSession

MODEL_URL = (
    "https://huggingface.co/Xenova/modnet/resolve/"
    "fa2fa546052fba4c08921230a26cc69a333fca12/onnx/model.onnx"
)
MODEL_SHA256 = "07c308cf0fc7e6e8b2065a12ed7fc07e1de8febb7dc7839d7b7f15dd66584df9"
MAX_MATTING_SIDE = 512


class ModnetPortraitSession(BaseSession):
    @classmethod
    def name(cls, *args, **kwargs):
        return "modnet-portrait"

    @classmethod
    def download_models(cls, *args, **kwargs):
        # Pinned revision and hash also validate an existing cached download.
        return pooch.retrieve(
            MODEL_URL,
            known_hash=f"sha256:{MODEL_SHA256}",
            fname="modnet-portrait.onnx",
            path=cls.model_dir(*args, **kwargs),
        )

    def predict(self, img: Image.Image, *args, **kwargs) -> list[Image.Image]:
        scale = min(1.0, MAX_MATTING_SIDE / max(img.size))
        size = tuple(max(32, round(side * scale / 32) * 32) for side in img.size)
        with closing(img.convert("RGB")) as rgb:
            with closing(rgb.resize(size, Image.Resampling.BILINEAR)) as preview:
                pixels = np.array(preview, dtype=np.float32)
        # MODNet expects RGB / 127.5 - 1, not rembg's image-max normalization.
        pixels /= 127.5
        pixels -= 1.0
        tensor = np.ascontiguousarray(pixels.transpose(2, 0, 1)[None])
        input_name = self.inner_session.get_inputs()[0].name
        alpha = self.inner_session.run(None, {input_name: tensor})[0][0, 0]
        mask = np.clip(alpha * 255.0, 0, 255).astype(np.uint8)
        with closing(Image.fromarray(mask)) as matte:
            return [matte.resize(img.size, Image.Resampling.BILINEAR)]
