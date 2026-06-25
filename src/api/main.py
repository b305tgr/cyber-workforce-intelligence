from fastapi import FastAPI

from src.api.routers.professionals import (
    router as professional_router,
)

app = FastAPI(
    title="Cyber Workforce Intelligence Platform",
    version="0.4.0",
)

app.include_router(professional_router)


@app.get("/")
def root():

    return {
        "status": "running"
    }