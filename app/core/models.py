"""Pydantic models for request/response schemas."""

from typing import List, Optional
from pydantic import BaseModel


class TranslationResult(BaseModel):
    """Result of a single translation."""
    language: str
    status: str
    duration: Optional[int] = None
    output_path: Optional[str] = None
    error: Optional[str] = None
    code: Optional[int] = None


class TranslationRequest(BaseModel):
    """Translation request response."""
    message: str
    filename: str
    folder_id: str
    languages_count: int
    keys_used: int


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    timestamp: float


class RootResponse(BaseModel):
    """Root endpoint response."""
    message: str
    status: str
    version: str
    endpoints: dict
    supported_languages: int
    api_keys_configured: int


class TranslationSummary(BaseModel):
    """Summary of all translations."""
    total: int
    successful: int
    failed: int
    results: List[TranslationResult]
