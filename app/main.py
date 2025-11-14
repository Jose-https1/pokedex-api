from fastapi import FastAPI

from .config import settings
from .database import create_db_and_tables


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
)


@app.on_event("startup")
def on_startup() -> None:
    create_db_and_tables()


@app.get("/health")
def health_check():
    return {"status": "ok"}
