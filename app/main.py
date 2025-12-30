"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.routers import health, translate
from app.core.config import get_settings


#TODO
#1. Prebaciti txt filove da se spremaju u bazu podataka u postgres na render.com

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    settings = get_settings()
    print(f"🚀 SRT Translation Service v{__version__} started")

    yield

    # Shutdown (ako ikad zatreba)
    print("🛑 SRT Translation Service shutting down")


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""

    application = FastAPI(
        title="SRT Translation Service",
        description="Translate SRT subtitle files to multiple languages using Gemini AI",
        version=__version__,
        lifespan=lifespan,
    )

    # CORS middleware
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    application.include_router(health.router, tags=["Health"])
    application.include_router(translate.router, tags=["Translation"])

    return application


app = create_app()