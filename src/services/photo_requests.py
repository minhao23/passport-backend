"""Manage a queued photo's request lifetime independently of HTTP responses."""

import asyncio
from collections.abc import Callable
from contextlib import suppress
from threading import Event

from fastapi import Request, UploadFile

from errors import (
    ProcessingCancelledError,
    QueueWaitTimeoutError,
    UploadTooLargeError,
)
from services.processing_jobs import ProcessingPermit
from utils.limits import MAX_FILE_BYTES, MAX_QUEUE_WAIT_SECONDS

PhotoProcessor = Callable[[bytes, str, Event], bytes]


async def process_uploaded_photo(
    request: Request,
    file: UploadFile,
    country: str,
    permit: ProcessingPermit,
    processor: PhotoProcessor,
) -> bytes:
    cancelled = Event()
    queue_waiter: asyncio.Task[None] | None = None
    watcher: asyncio.Task[None] | None = None

    async def watch_disconnect() -> None:
        while not cancelled.is_set():
            if await request.is_disconnected():
                cancelled.set()
                if queue_waiter is not None:
                    queue_waiter.cancel()
                return
            await asyncio.sleep(0.1)

    try:
        if await request.is_disconnected():
            raise ProcessingCancelledError()
        queue_waiter = asyncio.create_task(permit.wait_for_turn())
        watcher = asyncio.create_task(watch_disconnect())
        try:
            async with asyncio.timeout(MAX_QUEUE_WAIT_SECONDS):
                await queue_waiter
        except TimeoutError as exc:
            raise QueueWaitTimeoutError() from exc
        except asyncio.CancelledError:
            current_task = asyncio.current_task()
            if (
                cancelled.is_set()
                and current_task is not None
                and not current_task.cancelling()
            ):
                raise ProcessingCancelledError() from None
            raise

        # Read into memory only after receiving a worker slot. Queued uploads
        # remain in Starlette's bounded, potentially disk-spooled UploadFile.
        image_bytes = await file.read(MAX_FILE_BYTES + 1)
        if len(image_bytes) > MAX_FILE_BYTES:
            raise UploadTooLargeError()
        if cancelled.is_set() or await request.is_disconnected():
            raise ProcessingCancelledError()
        return await asyncio.wrap_future(
            permit.submit(processor, image_bytes, country, cancelled)
        )
    finally:
        cancelled.set()
        # Submitted native work owns the permit until its future completes.
        permit.release_if_unused()
        for task in (watcher, queue_waiter):
            if task is not None:
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task
