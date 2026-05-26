from fastapi import APIRouter, UploadFile, File, HTTPException, Response
from services.image_processor import create_passport_photo
from utils.passport_sizes import passport_photo_sizes_mm

router = APIRouter()

@router.post("/images/process")
def process_image(country: str, file: UploadFile = File(...)):
    """
    Endpoint to receive an uploaded image, process it into a passport photo
    based on the specific country's requirements, and return the image.
    """

    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File provided is not an image.")

    if country not in passport_photo_sizes_mm:
        raise HTTPException(status_code=404, detail=f"Country '{country}' not found in our database.")
        

    try:
        image_bytes = file.file.read()
        
        processed_image_bytes = create_passport_photo(image_bytes, country)

        return Response(content=processed_image_bytes, media_type="image/jpeg")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))