import logging
from typing import Annotated

from fastapi import APIRouter, File, Request, Response, UploadFile

from api.responses import error_response
from services.image_processor import create_passport_photo
from services.photo_requests import process_uploaded_photo
from services.processing_jobs import processing_pool
from utils.limits import ACCEPTED_CONTENT_TYPES, MAX_FILE_BYTES
from utils.passport_sizes import passport_photo_sizes_mm
from errors import (
    InternalServerError,
    InvalidCountryError,
    InvalidImageTypeError,
    ProcessingCancelledError,
    ProcessingError,
    ServiceBusyError,
    UploadTooLargeError,
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/images/process")
async def process_image(
    request: Request, country: str, file: Annotated[UploadFile, File()]
) -> Response:
    """Validate a photo upload and return its processed passport JPEG."""
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

    try:
        processed_image_bytes = await process_uploaded_photo(
            request, file, country, permit, create_passport_photo
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
