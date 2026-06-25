"""
ACE Voice Controller — FastAPI Middleware
CORS, request ID injection, timing, error handling.
"""

import time
import uuid
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger

from app.core.exceptions import ACEBaseException


def register_middleware(app: FastAPI) -> None:
    """Attach all middleware to the FastAPI app."""

    # CORS — allow Tauri webview origin
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "tauri://localhost", 
            "https://tauri.localhost", 
            "http://tauri.localhost",
            "http://localhost:3000",
            "https://localhost:3000"
        ],
        allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?.*",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Process-Time", "X-Request-ID"],
    )

    @app.middleware("http")
    async def request_id_and_timing(request: Request, call_next) -> Response:
        request_id = str(uuid.uuid4())[:8]
        request.state.request_id = request_id
        start = time.perf_counter()

        logger.debug(f"[{request_id}] → {request.method} {request.url.path}")

        try:
            response: Response = await call_next(request)
        except Exception as e:
            # Prevent anyio.EndOfStream from bubbling up and crashing the Uvicorn worker
            if "No response returned" in str(e) or "EndOfStream" in str(type(e)):
                logger.warning(f"[{request_id}] Client disconnected before response was generated.")
                return JSONResponse(status_code=499, content={"detail": "Client Closed Request"})
            raise

        elapsed = (time.perf_counter() - start) * 1000
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = f"{elapsed:.2f}ms"

        logger.debug(f"[{request_id}] ← {response.status_code} ({elapsed:.2f}ms)")
        return response


def register_exception_handlers(app: FastAPI) -> None:
    """Map custom exceptions to HTTP error responses."""

    @app.exception_handler(ACEBaseException)
    async def ace_exception_handler(request: Request, exc: ACEBaseException):
        logger.error(f"ACE error [{exc.code}]: {exc.message}")
        return JSONResponse(
            status_code=400,
            content={"error": exc.code, "message": exc.message},
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception):
        logger.exception(f"Unhandled exception: {exc}")
        return JSONResponse(
            status_code=500,
            content={"error": "INTERNAL_ERROR", "message": "An unexpected error occurred."},
        )
