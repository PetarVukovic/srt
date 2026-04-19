"""Health and status endpoints."""

import time

from fastapi import APIRouter

from app import __version__
from app.core.config import TARGET_LANGUAGES, get_settings

router = APIRouter()


@router.get("/")
async def root():
    """Root endpoint with service information."""
    settings = get_settings()
    
    return {
        "service": "SRT Translation Service",
        "status": "active",
        "version": __version__,
        "endpoints": {
            "health": "/health",
            "translate_single_or_batch": "/batch/translate/srt",
            "translate_multiple": "/batch/translate/multiple",
        },
        "gemini": {
            "model": settings.gemini_model,
            "thinking_level": settings.gemini_thinking_level,
            "temperature": settings.gemini_temperature,
        },
        "supported_languages": len(TARGET_LANGUAGES),
        "max_batch_files": settings.max_batch_files,
        "max_concurrent_files": settings.max_concurrent_files,
        "gemini_api_key_configured": bool(settings.gemini_api_key),
        "reports_folder": settings.reports_folder,
    }


@router.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": time.time(),
    }
