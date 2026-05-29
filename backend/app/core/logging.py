"""
ACE Voice Controller — Logging Configuration
Uses loguru for structured, colourised logging.
"""

import sys
from pathlib import Path
from loguru import logger
from app.config import settings


import io

def setup_logging() -> None:
    """Configure loguru logger for file + console output."""
    log_path = Path(settings.log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Remove default handler
    logger.remove()

    # Force UTF-8 on Windows terminals that default to cp1252
    stdout_utf8 = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    # Console — colourised
    logger.add(
        stdout_utf8,
        level=settings.log_level,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> — "
            "<level>{message}</level>"
        ),
        colorize=True,
    )

    # File — JSON-structured for parsing
    logger.add(
        log_path,
        level=settings.log_level,
        rotation="10 MB",
        retention="30 days",
        compression="zip",
        serialize=True,  # JSON format
        enqueue=True,    # Non-blocking
    )

    logger.info("ACE Voice Controller — logging initialised")
