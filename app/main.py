"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.core.config import get_settings
from app.core.logging import get_logger, setup_logging
from app.routers import health, translate

logger = get_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    settings = get_settings()
    logger.info(
        "SRT Translation Service started | version=%s | model=%s | deployment=%s",
        __version__,
        settings.gemini_model,
        settings.deployment,
    )

    yield

    logger.info("SRT Translation Service shutting down")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""

    application = FastAPI(
        title="SRT Translation Service",
        description=(
            "Servis za obradu, spajanje i prijevod SRT titlova pomoću "
            "Gemini Batch API-ja."
        ),
        version=__version__,
        lifespan=lifespan,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(health.router, tags=["Health"])
    application.include_router(translate.router)

    return application


app = create_app()
