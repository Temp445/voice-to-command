"""
ACE Voice Controller — FastAPI Main Application
Entry point: mounts all routers, middleware, WebSocket endpoint, and lifecycle events.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from loguru import logger

from app.config import settings
from app.core.logging import setup_logging
from app.core.middleware import register_middleware, register_exception_handlers
from app.database import init_db
from app.websocket.manager import ws_manager
from app.services.intent_registry import register_all_intents


# ─── Lifespan ────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown logic."""
    setup_logging()
    logger.info(f"🚀 Starting {settings.app_name} v{settings.app_version}")

    await init_db()
    logger.info("✅ Database initialised")

    register_all_intents()
    logger.info("✅ Command intents registered")

    yield

    logger.info("🛑 ACE Voice Controller shutting down")


# ─── App ─────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="ACE Voice Controller API",
    version=settings.app_version,
    description="AI-powered desktop voice control and automation system",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

register_middleware(app)
register_exception_handlers(app)


# ─── Routers ─────────────────────────────────────────────────────────────────

from app.routers import auth, voice, commands, workflows, automation, settings_router  # noqa: E402

app.include_router(auth.router,          prefix="/api/auth",       tags=["Auth"])
app.include_router(voice.router,         prefix="/api/voice",      tags=["Voice"])
app.include_router(commands.router,      prefix="/api/commands",   tags=["Commands"])
app.include_router(workflows.router,     prefix="/api/workflows",  tags=["Workflows"])
app.include_router(automation.router,    prefix="/api/automation", tags=["Automation"])
app.include_router(settings_router.router, prefix="/api/settings", tags=["Settings"])


# ─── WebSocket ───────────────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        await ws_manager.send_to(websocket, "connected", {
            "message": "ACE WebSocket connected",
            "version": settings.app_version,
        })
        while True:
            data = await websocket.receive_json()
            # Handle ping-pong
            if data.get("type") == "ping":
                await ws_manager.send_to(websocket, "pong", {})
    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await ws_manager.disconnect(websocket)


# ─── Health ──────────────────────────────────────────────────────────────────

@app.get("/api/health", tags=["Health"])
async def health_check():
    return JSONResponse({
        "status": "ok",
        "app": settings.app_name,
        "version": settings.app_version,
        "ws_connections": ws_manager.connection_count,
    })


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.backend_host,
        port=settings.backend_port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )
