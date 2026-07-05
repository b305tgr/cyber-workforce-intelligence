from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routers.professionals import (
    router as professional_router,
)

from src.api.routers.dashboard import (
    router as dashboard_router,
)

from src.api.routers.imports import (
    router as imports_router,
)

app = FastAPI(
    title="Cyber Workforce Intelligence API",
    version="0.6.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(
    professional_router,
)

app.include_router(
    dashboard_router,
)

app.include_router(
    imports_router,
)


@app.get("/")
def root():

    return {
        "message": "Cyber Workforce Intelligence API"
    }