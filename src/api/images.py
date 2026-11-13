import asyncio
import logging
from contextlib import suppress
from threading import Event

from fastapi import APIRouter, UploadFile, File, Request, Response
from fastapi.responses import JSONResponse
from services.image_processor import create_passport_photo
from services.processing_jobs import processing_pool
from request_limits import limit_response
from utils.limits import ACCEPTED_CONTENT_TYPES, MAX_FILE_BYTES, MAX_QUEUE_WAIT_SECONDS
from utils.passport_sizes import passport_photo_sizes_mm
from errors import (
    InternalServerError,
    InvalidCountryError,
    InvalidImageTypeError,
    ProcessingCancelledError,
    ProcessingError,
    QueueWaitTimeoutError,
    ServiceBusyError,
    UploadTooLargeError,
)

router = APIRouter()
logger = logging.getLogger(__name__)


def error_response(error: ProcessingError) -> JSONResponse:
    return limit_response(error)

@router.post("/images/process")
async def process_image(request: Request, country: str, file: UploadFile = File(...)):
    """
    Endpoint to receive an uploaded image, process it into a passport photo
    based on the specific country's requirements, and return the image.
    """

    if file.content_type not in ACCEPTED_CONTENT_TYPES:
        return error_response(InvalidImageTypeError())

    if country not in passport_photo_sizes_mm:
        return error_response(InvalidCountryError())
        

    if file.size is not None and file.size > MAX_FILE_BYTES:
        return error_response(UploadTooLargeError())
    permit = getattr(getattr(request, "state", None), "processing_permit", None)
    if permit is None:
        permit = processing_pool.try_acquire()
    if permit is None:
        return error_response(ServiceBusyError())
    cancelled = Event()
    queue_waiter = None

    async def watch_disconnect():
        while not cancelled.is_set():
            if await request.is_disconnected():
                cancelled.set()
                if queue_waiter is not None:
                    queue_waiter.cancel()
                return
            await asyncio.sleep(0.1)

    watcher = None
    try:
        if await request.is_disconnected():
            return Response(status_code=499)
        queue_waiter = asyncio.create_task(permit.wait_for_turn())
        watcher = asyncio.create_task(watch_disconnect())
        try:
            async with asyncio.timeout(MAX_QUEUE_WAIT_SECONDS):
                await queue_waiter
        except TimeoutError:
            return error_response(QueueWaitTimeoutError())
        except asyncio.CancelledError:
            if cancelled.is_set() and not asyncio.current_task().cancelling():
                raise ProcessingCancelledError() from None
            raise

        # Queued requests keep their bounded UploadFile rather than a second
        # bytes buffer. Only the request with a worker slot reads it into memory.
        image_bytes = await file.read(MAX_FILE_BYTES + 1)
        if len(image_bytes) > MAX_FILE_BYTES:
            return error_response(UploadTooLargeError())
        if cancelled.is_set() or await request.is_disconnected():
            return Response(status_code=499)
        processed_image_bytes = await asyncio.wrap_future(
            permit.submit(create_passport_photo, image_bytes, country, cancelled)
        )
        return Response(
            content=processed_image_bytes, media_type="image/jpeg",
            headers={"Cache-Control": "no-store"},
        )

    except ProcessingCancelledError:
        logger.info("Photo processing cancelled after client disconnect")
        return Response(status_code=499)
    except ProcessingError as exc:
        return error_response(exc)
    except Exception:
        logger.exception("Unexpected passport photo processing failure")
        return error_response(InternalServerError())
    finally:
        cancelled.set()
        permit.release_if_unused()
        if watcher is not None:
            watcher.cancel()
            with suppress(asyncio.CancelledError):
                await watcher
