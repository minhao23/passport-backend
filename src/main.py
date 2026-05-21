from fastapi import FastAPI
from api import images


app = FastAPI()


app.include_router(images)