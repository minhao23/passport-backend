"""FastAPI application setup; routes and processing live in their own modules."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api import router as api_router
from request_limits import UploadLimitsMiddleware
from services.model_runtime import load_models

logger = logging.getLogger(__name__)

LOCAL_ORIGINS = [
    "http://localhost",
    "http://localhost:8000",
    "http://localhost:3000",
]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info("Starting photo service")
    load_models()
    try:
        yield
    finally:
        logger.info("Shutting down photo service")


def create_app() -> FastAPI:
    application = FastAPI(lifespan=lifespan)
    application.add_middleware(UploadLimitsMiddleware)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=LOCAL_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(api_router)
    return application


app = create_app()
