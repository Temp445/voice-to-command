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
    if sys.stdout is not None and hasattr(sys.stdout, "buffer"):
        try:
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
        except Exception:
            pass

    # File — JSON-structured for parsing.
    #
    # WHY {time} IN FILENAME:
    # ─────────────────────────────────────────────────────────────────────
    # When the path contains {time}, loguru creates a NEW dated file on
    # rotation (e.g. ace_2026-06-17.log → ace_2026-06-18.log) and simply
    # closes the old handle — no os.rename() call is made.
    #
    # Without {time}, loguru renames ace.log → ace.<timestamp>.log.
    # On Windows, if Tauri/uvicorn still holds a handle to ace.log, that
    # rename raises PermissionError: [WinError 32].
    # ─────────────────────────────────────────────────────────────────────
    dated_log_path = log_path.parent / "ace_{time:YYYY-MM-DD}.log"

    # Remove any stale unlocked ace.log left from a crashed previous session
    # so it doesn't keep blocking new workers via WinError 32.
    try:
        if log_path.exists():
            log_path.unlink(missing_ok=True)
    except PermissionError:
        pass  # Still locked by another process — leave it, dated file is used instead

    logger.add(
        str(dated_log_path),   # e.g.  ace_2026-06-17.log  — no rename on rotation
        level=settings.log_level,
        rotation="00:00",      # New file each day; old handle just closed, never renamed
        retention="30 days",
        serialize=True,        # JSON format
        enqueue=True,          # Non-blocking background writer
        catch=True,            # Belt-and-suspenders: swallow any residual OS errors
    )

    logger.info("ACE Voice Controller — logging initialised")

