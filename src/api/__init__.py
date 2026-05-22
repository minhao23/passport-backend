from fastapi import APIRouter
from .images import router as images_router

router = APIRouter()
router.include_router(images_router)