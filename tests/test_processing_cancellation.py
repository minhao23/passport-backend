import asyncio
import io
import json
import unittest
import zlib
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event, Lock
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
from errors import ImageDimensionsError, InvalidPhotoError, PersonNotDetectedError, ProcessingCancelledError
from main import app
from services import image_processor
from services.processing_jobs import ProcessingPool, processing_pool
from utils.limits import MAX_ACTIVE_JOBS, MAX_FILE_BYTES, MAX_REQUEST_BYTES, MAX_WAITING_JOBS
from utils.image_headers import check_webp_header


def webp_chunk(kind, payload):
    return kind + len(payload).to_bytes(4, "little") + payload + b"\0" * (len(payload) & 1)


def webp_container(chunks):
    payload = b"WEBP" + chunks
    return b"RIFF" + len(payload).to_bytes(4, "little") + payload


class WebPHeaderTests(unittest.TestCase):
    def test_oversized_headers_rejected_before_any_decoder(self):
        for width, height in ((5000, 5000), (10001, 1)):
            headers = [
                webp_chunk(b"VP8X", b"\0" * 4 + (width - 1).to_bytes(3, "little")
                           + (height - 1).to_bytes(3, "little")),
                webp_chunk(b"VP8L", b"\x2f" + ((width - 1) | ((height - 1) << 14)).to_bytes(4, "little")),
                webp_chunk(b"VP8 ", b"\0" * 3 + b"\x9d\x01\x2a"
                           + width.to_bytes(2, "little") + height.to_bytes(2, "little")),
            ]
            for header in headers:
                with (
                    self.subTest(width=width, height=height, kind=header[:4]),
                    patch.object(image_processor.Image, "open") as pillow,
                    patch.object(image_processor.cv2, "imdecode") as opencv,
                ):
                    with self.assertRaises(ImageDimensionsError):
                        image_processor.create_passport_photo(webp_container(header), "United States")
                    pillow.assert_not_called()
                    opencv.assert_not_called()

    def test_small_canvas_cannot_hide_oversized_bitstream(self):
        canvas = webp_chunk(b"VP8X", b"\0" * 10)
        bits = (4999 | (4999 << 14)).to_bytes(4, "little")
        with self.assertRaises(ImageDimensionsError):
            check_webp_header(webp_container(canvas + webp_chunk(b"VP8L", b"\x2f" + bits)))

    def test_real_still_webp_variants_pass_preflight(self):
        for mode in ("RGB", "RGBA"):
            for lossless in (False, True):
                with self.subTest(mode=mode, lossless=lossless):
                    image = image_processor.Image.new(mode, (32, 48))
                    output = io.BytesIO()
                    image.save(output, format="WEBP", lossless=lossless)
                    data = output.getvalue()
                    check_webp_header(data)
                    self.assertEqual(cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR).shape[:2], (48, 32))

    def test_truncated_and_animated_webp_are_rejected(self):
        for data in (
            b"RIFF\0\0\0\0WEBP",
            webp_container(webp_chunk(b"VP8L", b"\x2f")),
            webp_container(webp_chunk(b"VP8X", b"\x02" + b"\0" * 9)),
            webp_container(webp_chunk(b"ANMF", b"\0" * 16)),
        ):
            with self.subTest(data=data), self.assertRaises(InvalidPhotoError):
                check_webp_header(data)


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

    def test_parallel_background_removal_serializes_shared_detector(self):
        backgrounds = Barrier(2)
        detector_started = Event()
        release_detector = Event()
        second_lock_attempt = Event()
        attempt_lock = Lock()
        detector_lock = image_processor.yolo_lock
        attempts = 0
        detections = []

        class ObservedLock:
            def __enter__(self):
                nonlocal attempts
                with attempt_lock:
                    attempts += 1
                    if attempts == 2:
                        second_lock_attempt.set()
                detector_lock.acquire()

            def __exit__(self, *args):
                detector_lock.release()

        def remove(image, **kwargs):
            # Both jobs must enter background removal before either can finish.
            backgrounds.wait(timeout=3)
            return image.convert("RGBA")

        def detect(*args, **kwargs):
            detections.append(True)
            if len(detections) == 1:
                detector_started.set()
                if not release_detector.wait(5):
                    raise AssertionError("Detector was not released")
            return [SimpleNamespace(boxes=[])]

        with (
            patch.object(image_processor, "remove", side_effect=remove),
            patch.object(image_processor, "rembg_session", object(), create=True),
            patch.object(image_processor, "yolo_model", SimpleNamespace(predict=detect), create=True),
            patch.object(image_processor, "yolo_lock", ObservedLock()),
            ThreadPoolExecutor(max_workers=2) as executor,
        ):
            futures = [
                executor.submit(image_processor.create_passport_photo, self.photo, "United States")
                for _ in range(2)
            ]
            try:
                self.assertTrue(detector_started.wait(2))
                self.assertTrue(second_lock_attempt.wait(2))
                self.assertEqual(len(detections), 1)
            finally:
                release_detector.set()
            for future in futures:
                with self.assertRaises(PersonNotDetectedError):
                    future.result(timeout=2)
        self.assertEqual(len(detections), 2)

    def test_cancel_while_waiting_for_detector_skips_prediction(self):
        gate = Mock()
        gate.__enter__ = Mock(side_effect=self.cancelled.set)
        gate.__exit__ = Mock(return_value=False)
        detector = Mock()
        with (
            patch.object(image_processor, "remove", side_effect=lambda image, **_: image.convert("RGBA")),
            patch.object(image_processor, "rembg_session", object(), create=True),
            patch.object(image_processor, "yolo_model", detector, create=True),
            patch.object(image_processor, "yolo_lock", gate),
        ):
            with self.assertRaises(ProcessingCancelledError):
                image_processor.create_passport_photo(self.photo, "United States", self.cancelled)
        gate.__enter__.assert_called_once()
        detector.predict.assert_not_called()

    def test_existing_invalid_photo_error_is_preserved_without_token(self):
        with self.assertRaises(InvalidPhotoError):
            image_processor.create_passport_photo(b"not an image", "United States")

    def test_large_dimensions_rejected_before_decode(self):
        header = Mock()
        header.format = "PNG"
        header.size = (5000, 5000)
        header_context = Mock()
        header_context.__enter__ = Mock(return_value=header)
        header_context.__exit__ = Mock(return_value=False)
        with (
            patch.object(image_processor.Image, "open", return_value=header_context),
            patch.object(image_processor.cv2, "imdecode") as decode,
        ):
            with self.assertRaises(ImageDimensionsError):
                image_processor.create_passport_photo(self.photo, "United States")
        decode.assert_not_called()

    def test_real_png_and_jpeg_dimensions_rejected_before_decode(self):
        png = bytearray(self.photo)
        png[16:24] = (5000).to_bytes(4, "big") * 2
        png[29:33] = zlib.crc32(png[12:29]).to_bytes(4, "big")
        jpeg_output = io.BytesIO()
        image_processor.Image.new("RGB", (32, 32)).save(jpeg_output, format="JPEG")
        jpeg = bytearray(jpeg_output.getvalue())
        frame = jpeg.index(b"\xff\xc0")
        jpeg[frame + 5:frame + 9] = (5000).to_bytes(2, "big") * 2
        for data in (png, jpeg):
            with (
                self.subTest(signature=data[:8]),
                patch.object(image_processor.cv2, "imdecode") as decode,
            ):
                with self.assertRaises(ImageDimensionsError):
                    image_processor.create_passport_photo(bytes(data), "United States")
                decode.assert_not_called()

    def test_working_resolution_is_bounded(self):
        _, encoded = cv2.imencode(".png", np.zeros((32, 4096, 3), dtype=np.uint8))
        sizes = []
        def remove(image, **kwargs):
            sizes.append(image.size)
            raise ProcessingCancelledError()
        with (
            patch.object(image_processor, "remove", side_effect=remove),
            patch.object(image_processor, "rembg_session", object(), create=True),
        ):
            with self.assertRaises(ProcessingCancelledError):
                image_processor.create_passport_photo(encoded.tobytes(), "United States")
        self.assertEqual(sizes, [(2048, 16)])

    def test_no_detected_subject_raises_expected_error(self):
        detector = Mock()
        detector.predict.return_value = [SimpleNamespace(boxes=[])]
        with (
            patch.object(image_processor, "remove", side_effect=lambda image, **_: image.convert("RGBA")),
            patch.object(image_processor, "rembg_session", object(), create=True),
            patch.object(image_processor, "yolo_model", detector, create=True),
        ):
            with self.assertRaises(PersonNotDetectedError):
                image_processor.create_passport_photo(self.photo, "United States")

    def test_actual_image_format_is_checked(self):
        image = image_processor.Image.new("RGB", (32, 32), "white")
        data = io.BytesIO()
        image.save(data, format="TIFF")
        with patch.object(image_processor.cv2, "imdecode") as decode:
            with self.assertRaises(InvalidPhotoError):
                image_processor.create_passport_photo(data.getvalue(), "United States")
        decode.assert_not_called()


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


class UploadBoundaryTests(unittest.IsolatedAsyncioTestCase):
    def multipart(self, data=b"photo", content_type="image/png"):
        return (
            b"--boundary\r\nContent-Disposition: form-data; name=\"file\"; "
            b"filename=\"photo.png\"\r\nContent-Type: " + content_type.encode()
            + b"\r\n\r\n" + data + b"\r\n--boundary--\r\n"
        )

    async def request(self, body, declared_length=None, receive_delay=0, disconnect=None):
        sent = []
        reads = []
        offset = 0
        headers = [(b"content-type", b"multipart/form-data; boundary=boundary")]
        if declared_length is not None:
            headers.append((b"content-length", str(declared_length).encode()))

        async def receive():
            nonlocal offset
            if receive_delay:
                await asyncio.sleep(receive_delay)
            if offset >= len(body):
                await (disconnect or asyncio.Event()).wait()
                return {"type": "http.disconnect"}
            chunk = body[offset:offset + 64 * 1024]
            offset += len(chunk)
            reads.append(len(chunk))
            return {"type": "http.request", "body": chunk, "more_body": offset < len(body)}

        async def send(message):
            sent.append(message)

        scope = {
            "type": "http", "http_version": "1.1", "method": "POST",
            "scheme": "http", "path": "/images/process", "raw_path": b"/images/process",
            "query_string": b"country=United%20States", "root_path": "",
            "headers": headers, "server": ("test", 80), "client": ("test", 123),
        }
        await app(scope, receive, send)
        start = next(message for message in sent if message["type"] == "http.response.start")
        payload = b"".join(message.get("body", b"") for message in sent if message["type"] == "http.response.body")
        return start["status"], payload, dict(start["headers"]), sum(reads)

    async def test_declared_oversize_rejected_without_reading(self):
        with patch("api.images.create_passport_photo") as process:
            status, body, _, read = await self.request(b"unused", MAX_REQUEST_BYTES + 1)
        self.assertEqual(status, 413)
        self.assertEqual(json.loads(body)["code"], "PHOTO_ISSUE")
        self.assertEqual(read, 0)
        process.assert_not_called()

    async def test_streamed_oversize_and_false_length_are_rejected(self):
        body = self.multipart(b"x" * (MAX_REQUEST_BYTES + 1))
        for declared in (None, 1):
            with patch("api.images.create_passport_photo") as process:
                status, payload, _, read = await self.request(body, declared)
            self.assertEqual(status, 413)
            self.assertEqual(json.loads(payload)["code"], "PHOTO_ISSUE")
            self.assertLessEqual(read, MAX_REQUEST_BYTES + 64 * 1024)
            process.assert_not_called()

    async def test_file_limit_below_aggregate_limit(self):
        with patch("api.images.create_passport_photo") as process:
            status, _, _, _ = await self.request(self.multipart(b"x" * (MAX_FILE_BYTES + 1)))
        self.assertEqual(status, 413)
        process.assert_not_called()

    async def test_busy_rejected_before_body_read(self):
        permits = [
            processing_pool.try_acquire()
            for _ in range(MAX_ACTIVE_JOBS + MAX_WAITING_JOBS)
        ]
        self.assertTrue(all(permits))
        try:
            status, payload, headers, read = await self.request(self.multipart())
        finally:
            for permit in permits:
                if permit is not None:
                    permit.release_if_unused()
        self.assertEqual(status, 503)
        self.assertEqual(json.loads(payload)["code"], "SERVICE_BUSY")
        self.assertEqual(headers[b"retry-after"], b"10")
        self.assertEqual(read, 0)

    async def test_allowed_type_and_exact_limit_pass(self):
        body = self.multipart(b"x" * MAX_FILE_BYTES)
        with patch("api.images.create_passport_photo", return_value=b"jpeg") as process:
            status, _, headers, _ = await self.request(body, len(body))
        self.assertEqual(status, 200)
        self.assertEqual(headers[b"cache-control"], b"no-store")
        self.assertEqual(len(process.call_args.args[0]), MAX_FILE_BYTES)

    async def test_mime_rejection_releases_admission(self):
        status, _, _, _ = await self.request(self.multipart(content_type="image/tiff"))
        self.assertEqual(status, 400)
        with patch("api.images.create_passport_photo", return_value=b"jpeg"):
            status, _, _, _ = await self.request(self.multipart())
        self.assertEqual(status, 200)

    async def test_no_detection_contract(self):
        with patch("api.images.create_passport_photo", side_effect=PersonNotDetectedError()):
            status, body, _, _ = await self.request(self.multipart())
        self.assertEqual(status, 422)
        self.assertEqual(json.loads(body)["code"], "PERSON_NOT_DETECTED")

    async def test_malformed_multipart_releases_admission(self):
        status, _, _, _ = await self.request(b"invalid multipart body")
        self.assertEqual(status, 400)
        permit = processing_pool.try_acquire()
        self.assertIsNotNone(permit)
        permit.release_if_unused()

    async def test_stalled_upload_times_out_and_releases_admission(self):
        with patch("request_limits.MAX_UPLOAD_SECONDS", 0.01):
            status, payload, _, _ = await self.request(self.multipart(), receive_delay=0.1)
        self.assertEqual(status, 408)
        self.assertEqual(json.loads(payload)["code"], "PHOTO_ISSUE")
        permit = processing_pool.try_acquire()
        self.assertIsNotNone(permit)
        permit.release_if_unused()

    async def test_upload_deadline_does_not_cut_off_inference(self):
        import time
        def process(*args):
            time.sleep(0.05)
            return b"jpeg"
        with (
            patch("request_limits.MAX_UPLOAD_SECONDS", 0.01),
            patch("api.images.create_passport_photo", side_effect=process),
        ):
            status, _, _, _ = await self.request(self.multipart())
        self.assertEqual(status, 200)

    async def test_two_photos_run_concurrently_and_two_wait_in_order(self):
        started = {name: Event() for name in (b"first", b"second")}
        releases = {name: Event() for name in started}
        queued = [asyncio.Event() for _ in range(MAX_WAITING_JOBS)]
        calls = []
        reads = []
        tasks = []
        start_waiters = processing_pool.start_waiters
        from starlette.datastructures import UploadFile as StarletteUploadFile
        read_file = StarletteUploadFile.read

        async def record_read(file, size=-1):
            data = await read_file(file, size)
            reads.append(data)
            return data

        def notify_waiting():
            start_waiters()
            count = len(processing_pool.waiting)
            if count:
                queued[count - 1].set()

        def process(photo, *args):
            calls.append(photo)
            if photo in started:
                started[photo].set()
                if not releases[photo].wait(5):
                    raise AssertionError("Active job was not released")
            return b"jpeg"

        with (
            patch("api.images.create_passport_photo", side_effect=process),
            patch.object(processing_pool, "start_waiters", side_effect=notify_waiting),
            patch.object(StarletteUploadFile, "read", record_read),
        ):
            try:
                for name, event in started.items():
                    tasks.append(asyncio.create_task(self.request(self.multipart(name))))
                    self.assertTrue(await asyncio.to_thread(event.wait, 2))
                self.assertEqual(processing_pool.active, 2)
                for index, name in enumerate((b"third", b"fourth")):
                    tasks.append(asyncio.create_task(self.request(self.multipart(name))))
                    await asyncio.wait_for(queued[index].wait(), 2)
                self.assertEqual(calls, [b"first", b"second"])
                self.assertEqual(reads, [b"first", b"second"])
                self.assertTrue(all(not task.done() for task in tasks))
                status, _, _, read = await self.request(self.multipart(b"fifth"))
                self.assertEqual((status, read), (503, 0))
                releases[b"first"].set()
                # The waiting jobs must progress using the freed worker even
                # while the second original job remains blocked.
                responses = await asyncio.wait_for(
                    asyncio.gather(tasks[0], tasks[2], tasks[3]), 3
                )
                self.assertEqual([response[0] for response in responses], [200] * 3)
                self.assertFalse(tasks[1].done())
                releases[b"second"].set()
                responses = await asyncio.wait_for(asyncio.gather(*tasks), 3)
                self.assertEqual([response[0] for response in responses], [200] * 4)
                self.assertEqual(calls, [b"first", b"second", b"third", b"fourth"])
            finally:
                for release in releases.values():
                    release.set()
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)

    async def occupy_workers(self):
        permits = []
        for _ in range(MAX_ACTIVE_JOBS):
            permit = processing_pool.try_acquire()
            self.assertIsNotNone(permit)
            self.addCleanup(permit.release_if_unused)
            await permit.wait_for_turn()
            permits.append(permit)
        return permits

    async def test_queued_disconnect_removes_photo_without_processing(self):
        active = await self.occupy_workers()
        disconnect = asyncio.Event()
        queued = asyncio.Event()
        start_waiters = processing_pool.start_waiters

        def notify_waiting():
            start_waiters()
            if processing_pool.waiting:
                queued.set()

        with (
            patch("api.images.create_passport_photo") as process,
            patch.object(processing_pool, "start_waiters", side_effect=notify_waiting),
        ):
            task = asyncio.create_task(self.request(self.multipart(), disconnect=disconnect))
            try:
                await asyncio.wait_for(queued.wait(), 2)
                disconnect.set()
                response = await asyncio.wait_for(task, 2)
                self.assertEqual(response[0], 499)
                self.assertEqual(len(processing_pool.waiting), 0)
                self.assertEqual(processing_pool.active, MAX_ACTIVE_JOBS)
                process.assert_not_called()
            finally:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
                for permit in active:
                    permit.release_if_unused()

    async def test_queue_timeout_releases_waiting_slot_without_processing(self):
        active = await self.occupy_workers()
        try:
            with (
                patch("api.images.MAX_QUEUE_WAIT_SECONDS", 0.01),
                patch("api.images.create_passport_photo") as process,
            ):
                status, payload, _, _ = await self.request(self.multipart())
            self.assertEqual(status, 503)
            self.assertIn("waited too long", json.loads(payload)["detail"])
            self.assertEqual(len(processing_pool.waiting), 0)
            process.assert_not_called()
            replacements = [processing_pool.try_acquire() for _ in range(MAX_WAITING_JOBS)]
            try:
                self.assertTrue(all(replacements))
            finally:
                for permit in replacements:
                    if permit is not None:
                        permit.release_if_unused()
        finally:
            for permit in active:
                permit.release_if_unused()


class ProcessingQueueTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # Also retain coverage for the supported single-worker configuration.
        self.pool = ProcessingPool(capacity=1)
        self.permits = []
        self.waiters = []
        self.release_native = Event()

    async def asyncTearDown(self):
        self.release_native.set()
        for task in self.waiters:
            task.cancel()
        await asyncio.gather(*self.waiters, return_exceptions=True)
        for permit in self.permits:
            permit.release_if_unused()
        await asyncio.to_thread(self.pool.executor.shutdown, wait=True, cancel_futures=True)

    def reserve(self):
        permit = self.pool.try_acquire()
        self.assertIsNotNone(permit)
        self.permits.append(permit)
        return permit

    async def enqueue(self, permit):
        task = asyncio.create_task(permit.wait_for_turn())
        self.waiters.append(task)
        # Let the task register its queue entry before inspecting ordering.
        await asyncio.sleep(0)
        return task

    async def test_cancelled_waiters_do_not_accumulate_executor_jobs(self):
        active = self.reserve()
        await active.wait_for_turn()
        with patch.object(self.pool.executor, "submit") as submit:
            for _ in range(50):
                permit = self.reserve()
                task = await self.enqueue(permit)
                self.assertEqual(len(self.pool.waiting), 1)
                task.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await task
                self.assertEqual(len(self.pool.waiting), 0)
                self.assertEqual(self.pool.active, 1)
            submit.assert_not_called()

    async def test_cancellation_after_turn_granted_advances_next_waiter(self):
        active = self.reserve()
        await active.wait_for_turn()
        first = self.reserve()
        first_task = await self.enqueue(first)
        second = self.reserve()
        second_task = await self.enqueue(second)
        active.release_if_unused()
        first_task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await first_task
        await asyncio.wait_for(second_task, 2)
        self.assertEqual(self.pool.active, 1)
        self.assertEqual(len(self.pool.waiting), 0)

    async def test_cancelling_running_request_does_not_start_next_native_job(self):
        active = self.reserve()
        await active.wait_for_turn()
        started = Event()

        def native_job():
            started.set()
            self.release_native.wait(3)

        future = active.submit(native_job)
        self.assertTrue(await asyncio.to_thread(started.wait, 2))
        successor = self.reserve()
        waiting = await self.enqueue(successor)
        result = asyncio.wrap_future(future)
        result.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await result
        active.release_if_unused()
        self.assertFalse(waiting.done())
        self.assertEqual(len(self.pool.waiting), 1)
        self.release_native.set()
        await asyncio.wait_for(waiting, 2)
        self.assertEqual(self.pool.active, 1)

    async def test_failed_native_job_advances_queue(self):
        active = self.reserve()
        await active.wait_for_turn()
        successor = self.reserve()
        waiting = await self.enqueue(successor)

        def fail():
            raise InvalidPhotoError()

        with self.assertRaises(InvalidPhotoError):
            await asyncio.wrap_future(active.submit(fail))
        await asyncio.wait_for(waiting, 2)
        self.assertEqual(self.pool.active, 1)

    async def test_submit_requires_a_worker_slot(self):
        active = self.reserve()
        await active.wait_for_turn()
        waiting = self.reserve()
        await self.enqueue(waiting)
        with self.assertRaises(RuntimeError):
            waiting.submit(lambda: b"must not run")


class NativeCapacityTests(unittest.IsolatedAsyncioTestCase):
    async def test_cancelled_job_keeps_its_slot_while_other_worker_progresses(self):
        pool = ProcessingPool(max_waiting=0)
        permits = [pool.try_acquire() for _ in range(2)]
        started = [Event(), Event()]
        releases = [Event(), Event()]
        completed = Event()

        def native_job(index):
            started[index].set()
            if not releases[index].wait(5):
                raise AssertionError("Native job was not released")
            return b"jpeg"

        try:
            for permit in permits:
                await permit.wait_for_turn()
            futures = [permit.submit(native_job, index) for index, permit in enumerate(permits)]
            futures[1].add_done_callback(lambda _: completed.set())
            for event in started:
                self.assertTrue(await asyncio.to_thread(event.wait, 2))
            waiter = asyncio.wrap_future(futures[0])
            waiter.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await waiter
            permits[0].release_if_unused()
            self.assertIsNone(pool.try_acquire())
            releases[1].set()
            self.assertTrue(await asyncio.to_thread(completed.wait, 2))
            replacement = pool.try_acquire()
            self.assertIsNotNone(replacement)
            permits.append(replacement)
            await replacement.wait_for_turn()
            result = await asyncio.wrap_future(replacement.submit(lambda: b"next photo"))
            self.assertEqual(result, b"next photo")
            self.assertFalse(futures[0].done())
        finally:
            for release in releases:
                release.set()
            for permit in permits:
                if permit is not None:
                    permit.release_if_unused()
            await asyncio.to_thread(pool.executor.shutdown, wait=True, cancel_futures=True)

    async def test_running_native_job_keeps_permit_after_await_is_cancelled(self):
        pool = ProcessingPool(capacity=1, max_waiting=0)
        permit = pool.try_acquire()
        await permit.wait_for_turn()
        started = Event()
        release = Event()

        def native_job():
            started.set()
            release.wait(timeout=3)
            return b"jpeg"

        try:
            future = permit.submit(native_job)
            completed = Event()
            future.add_done_callback(lambda _: completed.set())
            self.assertTrue(await asyncio.to_thread(started.wait, 2))
            waiter = asyncio.wrap_future(future)
            waiter.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await waiter
            permit.release_if_unused()
            self.assertIsNone(pool.try_acquire())
            release.set()
            await asyncio.to_thread(future.result, 2)
            self.assertTrue(await asyncio.to_thread(completed.wait, 2))
            replacement = pool.try_acquire()
            self.assertIsNotNone(replacement)
            replacement.release_if_unused()
        finally:
            release.set()
            pool.executor.shutdown(wait=True, cancel_futures=True)


if __name__ == "__main__":
    unittest.main()
