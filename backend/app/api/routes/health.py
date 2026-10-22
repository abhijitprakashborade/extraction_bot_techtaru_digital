"""Health check endpoint — used by Docker/k8s liveness probes and the UI badge."""
from fastapi import APIRouter

from app.config import settings
from app.services.extractor import engine_name

router = APIRouter()

@router.get("/health", tags=["Health"])
async def health():
    engine = engine_name()
    return {
        "status": "ok",
        "app": settings.app_name,
        "version": settings.app_version,
        "engine": engine,
        "model": settings.openai_model if engine == "openai-structured" else "deterministic-rules",
        "rate_limit_per_minute": settings.rate_limit_per_minute,
    }

@router.get("/", tags=["Health"])
async def root():
    return {
        "message": f"Welcome to {settings.app_name} API",
        "docs": "/docs",
        "version": settings.app_version,
    }
