"""ASGI entrypoint so `uvicorn main:app` works from repo root."""

from app.main import app

__all__ = ("app",)
