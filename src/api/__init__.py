from fastapi import APIRouter

from .health import router as health_router
from .images import router as images_router

router = APIRouter()
router.include_router(health_router)
router.include_router(images_router)
