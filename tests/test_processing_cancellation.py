import asyncio
import io
import unittest
from threading import Event
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import cv2
import numpy as np
from fastapi import UploadFile
from starlette.datastructures import Headers

# Unit tests exercise orchestration without importing native inference runtimes.
inference_stubs = patch.dict("sys.modules", {
    "rembg": SimpleNamespace(remove=Mock(), new_session=Mock()),
    "ultralytics": SimpleNamespace(YOLO=Mock()),
})
inference_stubs.start()
unittest.addModuleCleanup(inference_stubs.stop)

from api.images import process_image
from errors import InvalidPhotoError, ProcessingCancelledError
from services import image_processor


class ProcessingCheckpointTests(unittest.TestCase):
    def setUp(self):
        self.cancelled = Event()
        _, encoded = cv2.imencode(".png", np.zeros((32, 32, 3), dtype=np.uint8))
        self.photo = encoded.tobytes()

    def test_cancel_before_decode(self):
        self.cancelled.set()
        with patch.object(image_processor.cv2, "imdecode") as decode:
            with self.assertRaises(ProcessingCancelledError):
                image_processor.create_passport_photo(
                    self.photo, "United States", self.cancelled
                )
        decode.assert_not_called()

    def test_cancel_after_background_removal_skips_detection(self):
        def remove(image, **kwargs):
            self.cancelled.set()
            return image.convert("RGBA")

        detector = Mock()
        with (
            patch.object(image_processor, "remove", side_effect=remove),
            patch.object(image_processor, "rembg_session", object(), create=True),
            patch.object(image_processor, "yolo_model", detector, create=True),
        ):
            with self.assertRaises(ProcessingCancelledError):
                image_processor.create_passport_photo(
                    self.photo, "United States", self.cancelled
                )
        detector.predict.assert_not_called()

    def test_cancel_after_detection_skips_compositing(self):
        def detect(*args, **kwargs):
            self.cancelled.set()
            return []

        with (
            patch.object(image_processor, "remove", side_effect=lambda image, **_: image.convert("RGBA")),
            patch.object(image_processor, "rembg_session", object(), create=True),
            patch.object(image_processor, "yolo_model", SimpleNamespace(predict=detect), create=True),
            patch.object(image_processor.cv2, "getStructuringElement") as composite,
        ):
            with self.assertRaises(ProcessingCancelledError):
                image_processor.create_passport_photo(
                    self.photo, "United States", self.cancelled
                )
        composite.assert_not_called()

    def test_existing_invalid_photo_error_is_preserved_without_token(self):
        with self.assertRaises(InvalidPhotoError):
            image_processor.create_passport_photo(b"not an image", "United States")


class DisconnectTests(unittest.IsolatedAsyncioTestCase):
    def upload(self):
        return UploadFile(
            io.BytesIO(b"test photo"),
            filename="photo.png",
            headers=Headers({"content-type": "image/png"}),
        )

    async def test_already_disconnected_does_not_start_worker(self):
        request = SimpleNamespace(is_disconnected=AsyncMock(return_value=True))
        with patch("api.images.create_passport_photo") as process:
            response = await process_image(request, "United States", self.upload())
        self.assertEqual(response.status_code, 499)
        process.assert_not_called()

    async def test_disconnect_reaches_running_worker(self):
        started = Event()
        observed = Event()

        def process(photo, country, cancelled):
            started.set()
            if cancelled.wait(timeout=2):
                observed.set()
                raise ProcessingCancelledError()
            raise AssertionError("Disconnect was not propagated to the worker")

        async def disconnected():
            return started.is_set()

        request = SimpleNamespace(is_disconnected=disconnected)
        with patch("api.images.create_passport_photo", side_effect=process):
            response = await process_image(request, "United States", self.upload())
        self.assertEqual(response.status_code, 499)
        self.assertTrue(observed.is_set())

    async def test_success_and_photo_errors_keep_existing_contract(self):
        request = SimpleNamespace(is_disconnected=AsyncMock(return_value=False))
        with patch("api.images.create_passport_photo", return_value=b"jpeg"):
            response = await process_image(request, "United States", self.upload())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.media_type, "image/jpeg")
        self.assertEqual(response.body, b"jpeg")

        with patch("api.images.create_passport_photo", side_effect=InvalidPhotoError()):
            response = await process_image(request, "United States", self.upload())
        self.assertEqual(response.status_code, 422)
        self.assertIn(b"PHOTO_ISSUE", response.body)

    async def test_invalid_country_does_not_start_worker(self):
        request = SimpleNamespace(is_disconnected=AsyncMock(return_value=False))
        with patch("api.images.create_passport_photo") as process:
            response = await process_image(request, "invalid", self.upload())
        self.assertEqual(response.status_code, 400)
        process.assert_not_called()

    async def test_worker_finishes_without_leaking_disconnect_watcher(self):
        request = SimpleNamespace(is_disconnected=AsyncMock(return_value=False))
        before = set(asyncio.all_tasks())
        with patch("api.images.create_passport_photo", return_value=b"jpeg"):
            await process_image(request, "United States", self.upload())
        self.assertEqual(set(asyncio.all_tasks()), before)

    async def test_handler_cancellation_signals_worker(self):
        started = Event()
        stopped = Event()
        request = SimpleNamespace(is_disconnected=AsyncMock(return_value=False))

        def process(photo, country, cancelled):
            started.set()
            if cancelled.wait(timeout=2):
                stopped.set()
            return b"discarded"

        with patch("api.images.create_passport_photo", side_effect=process):
            task = asyncio.create_task(
                process_image(request, "United States", self.upload())
            )
            self.assertTrue(await asyncio.to_thread(started.wait, 2))
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
            self.assertTrue(await asyncio.to_thread(stopped.wait, 2))


if __name__ == "__main__":
    unittest.main()
