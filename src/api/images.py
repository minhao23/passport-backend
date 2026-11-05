import logging

from fastapi import APIRouter, UploadFile, File, Response
from fastapi.responses import JSONResponse
from services.image_processor import create_passport_photo
from utils.passport_sizes import passport_photo_sizes_mm
from errors import (
    InternalServerError,
    InvalidCountryError,
    InvalidImageTypeError,
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
def process_image(country: str, file: UploadFile = File(...)):
    """
    Endpoint to receive an uploaded image, process it into a passport photo
    based on the specific country's requirements, and return the image.
    """

    if not (file.content_type or "").startswith("image/"):
        return error_response(InvalidImageTypeError())

    if country not in passport_photo_sizes_mm:
        return error_response(InvalidCountryError())
        

    try:
        image_bytes = file.file.read()
        
        processed_image_bytes = create_passport_photo(image_bytes, country)

        return Response(content=processed_image_bytes, media_type="image/jpeg")

    except ProcessingError as exc:
        return error_response(exc)
    except Exception:
        logger.exception("Unexpected passport photo processing failure")
        return error_response(InternalServerError())
