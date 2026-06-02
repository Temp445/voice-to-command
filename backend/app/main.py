"""
ACE Voice Controller — FastAPI Main Application
Entry point: mounts all routers, middleware, WebSocket endpoint, and lifecycle events.
"""

import asyncio
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

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


# ─── LLM .env Bootstrap ──────────────────────────────────────────────────────

def _init_llm_from_env() -> None:
    """
    Initialize the LLM service from environment variables / .env file.
    This allows testing without the Settings UI.
    Priority: DB settings (set later in lifespan) > .env values.
    """
    from app.services.llm.llm_service import llm_service

    # Map provider name → its API key field in settings
    key_map = {
        "groq":     settings.groq_api_key,
        "openai":   settings.openai_api_key,
        "gemini":   settings.google_api_key,
        "claude":   settings.anthropic_api_key,
        "deepseek": settings.deepseek_api_key,
    }

    # Auto-detect provider if not explicitly set
    provider = settings.llm_provider.lower().strip()
    if not provider:
        for name, key in key_map.items():
            if key.strip():
                provider = name
                break

    if not provider:
        logger.info("ℹ️  No LLM provider configured in .env — AI features disabled until set in Settings.")
        return

    api_key = key_map.get(provider, "").strip()
    if not api_key:
        logger.warning(f"⚠️  LLM provider '{provider}' set but no API key found in .env")
        return

    # Use default model if not specified
    default_models = {
        "groq":     "llama-3.3-70b-versatile",
        "openai":   "gpt-4o-mini",
        "gemini":   "gemini-2.0-flash",
        "claude":   "claude-haiku-3-5",
        "deepseek": "deepseek-chat",
    }
    model = settings.llm_model.strip() or default_models.get(provider, "")

    try:
        llm_service.set_provider(
            provider_name=provider,
            api_key=api_key,
            model=model,
            temperature=settings.llm_temperature,
            mode=settings.llm_mode,
            enabled=True,
        )
        logger.info(f"✅ LLM initialized from .env: {provider} / {model} (mode={settings.llm_mode})")
    except Exception as e:
        logger.warning(f"⚠️  Failed to initialize LLM from .env: {e}")


# ─── Lifespan ────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown logic."""
    setup_logging()
    logger.info(f"🚀 Starting {settings.app_name} v{settings.app_version}")

    await init_db()
    logger.info("✅ Database initialised")

    # ── Dynamic App Discovery ────────────────────────────────────────────────
    from automation.desktop.app_scanner import AppScanner, get_scanner
    scanner = get_scanner()
    # Try loading from cache first for a fast start
    if not scanner.load_cache():
        logger.info("📡 No app cache found — running full discovery scan...")
        await scanner.scan_and_cache()
    else:
        # Refresh cache in the background without blocking startup
        async def _refresh_scan():
            await scanner.scan_and_cache()
        asyncio.create_task(_refresh_scan())
    app.state.app_scanner = scanner
    logger.info(f"✅ App discovery ready — {len(scanner.apps)} apps available")

    # ── Background File Indexer ──────────────────────────────────────────────
    from automation.desktop.file_indexer import get_indexer
    file_indexer = get_indexer()
    file_indexer.start_background_indexing()
    app.state.file_indexer = file_indexer
    logger.info("✅ File indexer running in background")

    register_all_intents()
    logger.info("✅ Command intents registered")

    # ── Initialize ACE Browser Controller ────────────────────────────────────
    try:
        from automation.ace_browser.ace_browser_controller import ACEBrowserLauncher, ACEBrowserController
        logger.info("🌐 Preparing default Chrome profile (force injecting CDP port)...")
        if ACEBrowserLauncher.launch(port=9222):
            logger.info("✅ ACE Browser Launcher started successfully")
            # Connect singleton in background to prepare it
            ctrl = ACEBrowserController()
            asyncio.create_task(ctrl.connect(port=9222))
        else:
            logger.warning("⚠️ Failed to launch ACE Browser")
    except Exception as e:
        logger.warning(f"⚠️ ACE Browser integration failed: {e}")

    # ── Initialize LLM from .env (quick-start without UI) ────────────────────
    _init_llm_from_env()

    # ── Restore LLM Settings from DB (overrides .env if DB has a key set) ────
    try:
        from sqlalchemy import select
        from app.models import UserSettings
        from app.database import AsyncSessionLocal
        from app.routers.settings_router import _apply_llm_settings
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(UserSettings).limit(1))
            s = result.scalar_one_or_none()
            if s:
                from app.config import settings as global_settings
                # Sync all fields from DB to in-memory config
                for field in s.__dict__:
                    if not field.startswith('_') and hasattr(global_settings, field):
                        setattr(global_settings, field, getattr(s, field))
                
                # Apply LLM specific initializations
                if s.llm_api_key_encrypted:
                    _apply_llm_settings(s)
                logger.info("✅ All settings restored from database")
    except Exception as e:
        logger.warning(f"⚠️  Could not restore LLM settings from DB: {e}")


    # Start the voice pipeline in the backend process
    try:
        from voice.pipeline import VoicePipeline, PipelineState
        from app.websocket.manager import ws_manager
        from app.routers.voice import _pipeline_state

        loop = asyncio.get_running_loop()

        def on_state_change(state: PipelineState):
            _pipeline_state["pipeline_state"] = state.value
            _pipeline_state["listening"] = (state == PipelineState.LISTENING)
            _pipeline_state["wake_word_active"] = (state == PipelineState.IDLE)
            asyncio.run_coroutine_threadsafe(
                ws_manager.broadcast("pipeline_state", {"state": state.value}), loop
            )
            asyncio.run_coroutine_threadsafe(
                ws_manager.broadcast(
                    "wake_word_detected" if state == PipelineState.LISTENING else "pipeline_state",
                    {"state": state.value, "wake_word_active": _pipeline_state["wake_word_active"]}
                ), loop
            )

        def on_transcript(text: str, is_final: bool):
            asyncio.run_coroutine_threadsafe(
                ws_manager.broadcast("transcript", {"text": text, "is_final": is_final}), loop
            )

        def on_command_result(result: dict):
            asyncio.run_coroutine_threadsafe(
                ws_manager.broadcast("command_executed", result), loop
            )

        pipeline = VoicePipeline(
            on_state_change=on_state_change,
            on_transcript=on_transcript,
            on_command_result=on_command_result,
        )
        pipeline.start()
        app.state.pipeline = pipeline
        _pipeline_state["wake_word_active"] = True
        asyncio.run_coroutine_threadsafe(
            ws_manager.broadcast("pipeline_state", {"state": "idle", "wake_word_active": True}), loop
        )
        logger.info("🎙️ Voice pipeline started — wake word listening in background")

    except Exception as e:
        logger.warning(f"⚠️  Voice pipeline failed to start (API will still work): {e}")
        app.state.pipeline = None

    yield

    logger.info("🛑 ACE Voice Controller shutting down")
    if getattr(app.state, "pipeline", None):
        app.state.pipeline.stop()
    if getattr(app.state, "file_indexer", None):
        app.state.file_indexer.stop()


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
from app.routers import llm_router  # noqa: E402

app.include_router(auth.router,          prefix="/api/auth",       tags=["Auth"])
app.include_router(voice.router,         prefix="/api/voice",      tags=["Voice"])
app.include_router(commands.router,      prefix="/api/commands",   tags=["Commands"])
app.include_router(workflows.router,     prefix="/api/workflows",  tags=["Workflows"])
app.include_router(automation.router,    prefix="/api/automation", tags=["Automation"])
app.include_router(settings_router.router, prefix="/api/settings", tags=["Settings"])
app.include_router(llm_router.router,    prefix="/api/llm",        tags=["AI Assistant"])


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
            message = await websocket.receive()
            if message.get("bytes") is not None:
                from voice.remote_mic import put_chunk
                put_chunk(message["bytes"])
            elif message.get("text") is not None:
                import json
                try:
                    data = json.loads(message["text"])
                    if data.get("type") == "ping":
                        await ws_manager.send_to(websocket, "pong", {})
                except json.JSONDecodeError:
                    pass
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
