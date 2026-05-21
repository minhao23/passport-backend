from fastapi import APIRouter, UploadFile, File, HTTPException, Response
from src.services.image_processor import create_passport_photo

router = APIRouter()

@router.post("/images/process")
async def process_image(file: UploadFile = File(...)):
    """
    Endpoint to receive an uploaded image, process it into a passport photo,
    and return the resulting image.
    """

    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File provided is not an image.")

    try:
        image_bytes = await file.read()
        processed_image_bytes = create_passport_photo(image_bytes)

        return Response(content=processed_image_bytes, media_type="image/jpeg")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))