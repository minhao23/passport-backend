from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api import router as api_router
from services.image_processor import load_models
from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Server is starting up...")
    load_models() 
    print("Models loaded successfully!")
    yield
    print("Server is shutting down...")

app = FastAPI(lifespan=lifespan)

origins = [
    "http://localhost",
    "http://localhost:8000",
    "http://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)





app.include_router(api_router)