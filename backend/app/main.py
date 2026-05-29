"""
ACE Voice Controller — FastAPI Main Application
Entry point: mounts all routers, middleware, WebSocket endpoint, and lifecycle events.
"""

import sys
sys.coinit_flags = 0  # Fix COM threading mode conflict for pywinauto
from pathlib import Path
_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.append(str(_ROOT))

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

    # Start the voice pipeline in the backend process
    from voice.pipeline import VoicePipeline, PipelineState
    from app.websocket.manager import ws_manager
    from app.routers.voice import _pipeline_state
    import asyncio

    loop = asyncio.get_running_loop()

    def on_state_change(state: PipelineState):
        _pipeline_state["pipeline_state"] = state.value
        _pipeline_state["listening"] = (state == PipelineState.LISTENING)
        # Wake word is active whenever pipeline is idle (always listening)
        _pipeline_state["wake_word_active"] = (state == PipelineState.IDLE)
        asyncio.run_coroutine_threadsafe(
            ws_manager.broadcast("pipeline_state", {"state": state.value}),
            loop
        )
        asyncio.run_coroutine_threadsafe(
            ws_manager.broadcast("wake_word_detected" if state == PipelineState.LISTENING else "pipeline_state",
                                  {"state": state.value, "wake_word_active": _pipeline_state["wake_word_active"]}),
            loop
        )

    def on_transcript(text: str, is_final: bool):
        asyncio.run_coroutine_threadsafe(
            ws_manager.broadcast("transcript", {"text": text, "is_final": is_final}),
            loop
        )

    def on_command_result(result: dict):
        asyncio.run_coroutine_threadsafe(
            ws_manager.broadcast("command_executed", result),
            loop
        )

    pipeline = VoicePipeline(
        on_state_change=on_state_change,
        on_transcript=on_transcript,
        on_command_result=on_command_result,
    )
    pipeline.start()
    app.state.pipeline = pipeline
    # Mark wake word as active from the moment the server starts
    _pipeline_state["wake_word_active"] = True
    asyncio.run_coroutine_threadsafe(
        ws_manager.broadcast("pipeline_state", {"state": "idle", "wake_word_active": True}),
        loop
    )
    logger.info("🎙️ Backend voice pipeline started successfully — wake word listening in background")

    yield

    logger.info("🛑 ACE Voice Controller shutting down")
    pipeline.stop()


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
    except (WebSocketDisconnect, RuntimeError) as e:
        # Client disconnected or socket closed
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
