import asyncio
import logging
from contextlib import suppress
from threading import Event

from fastapi import APIRouter, UploadFile, File, Request, Response
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from services.image_processor import create_passport_photo
from utils.passport_sizes import passport_photo_sizes_mm
from errors import (
    InternalServerError,
    InvalidCountryError,
    InvalidImageTypeError,
    ProcessingCancelledError,
    ProcessingError,
)

router = APIRouter()
logger = logging.getLogger(__name__)


def error_response(error: ProcessingError) -> JSONResponse:
    return JSONResponse(
        status_code=error.status_code,
        content={"code": error.code, "detail": error.message},
        headers={"Cache-Control": "no-store"},
    )

@router.post("/images/process")
async def process_image(request: Request, country: str, file: UploadFile = File(...)):
    """
    Endpoint to receive an uploaded image, process it into a passport photo
    based on the specific country's requirements, and return the image.
    """

    if not (file.content_type or "").startswith("image/"):
        return error_response(InvalidImageTypeError())

    if country not in passport_photo_sizes_mm:
        return error_response(InvalidCountryError())
        

    cancelled = Event()

    async def watch_disconnect():
        while not cancelled.is_set():
            if await request.is_disconnected():
                cancelled.set()
                return
            await asyncio.sleep(0.1)

    watcher = None
    try:
        image_bytes = await file.read()
        if await request.is_disconnected():
            return Response(status_code=499)
        watcher = asyncio.create_task(watch_disconnect())
        processed_image_bytes = await run_in_threadpool(
            create_passport_photo, image_bytes, country, cancelled
        )
        return Response(content=processed_image_bytes, media_type="image/jpeg")

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
        if watcher is not None:
            watcher.cancel()
            with suppress(asyncio.CancelledError):
                await watcher
