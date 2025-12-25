"""Health and status endpoints."""

import time

from fastapi import APIRouter

from app.core.config import TARGET_LANGUAGES, get_settings

router = APIRouter()


@router.get("/")
async def root():
    """Root endpoint with service information."""
    settings = get_settings()
    
    return {
        "message": "🚀 SRT Translation Service",
        "status": "active",
        "version": "2.0",
        "endpoints": {
            "translate": "/translate-srt/",
            "health": "/health",
        },
        "supported_languages": len(TARGET_LANGUAGES),
        "api_keys_configured": 3,
    }


@router.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": time.time(),
    }
