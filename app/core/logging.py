"""Central logging setup for the application."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


LOG_DIR = Path("logs")
LOG_FILE = LOG_DIR / "srt-service.log.txt"
LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"


def setup_logging() -> None:
    """Configure root logging once for console and file output."""
    root_logger = logging.getLogger()
    if getattr(root_logger, "_srt_logging_configured", False):
        return

    LOG_DIR.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(LOG_FORMAT)

    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=2_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    root_logger.setLevel(logging.INFO)
    root_logger.handlers.clear()
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    root_logger._srt_logging_configured = True


def get_logger(name: str) -> logging.Logger:
    """Return a configured logger instance."""
    setup_logging()
    return logging.getLogger(name)
