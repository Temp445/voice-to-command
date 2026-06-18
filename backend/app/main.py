"""
ACE Voice Controller — FastAPI Main Application
Entry point: mounts all routers, middleware, WebSocket endpoint, and lifecycle events.
"""

import asyncio
import sys
import warnings

warnings.filterwarnings("ignore", category=UserWarning, message="Apply externally defined coinit_flags: 0")

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
        logger.info(f"ℹ️  LLM provider '{provider}' has no API key configured — AI features disabled. Set a key in Settings to enable.")
        return

    # Use default model if not specified
    default_models = {
        "groq":     "llama-3.3-70b-versatile",
        "openai":   "gpt-4o-mini",
        "gemini":   "gemini-2.0-flash",
        "claude":   "claude-haiku-3-5",
        "deepseek": "deepseek-v4-flash",
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

    logger.info("✅ Database initialised (Supabase client ready)")

    # ── Dynamic App Discovery ────────────────────────────────────────────────
    from automation.desktop.app_scanner import AppScanner, get_scanner
    scanner = get_scanner()
    # Always load whatever exists in cache immediately (fast),
    # then refresh in the background only if scan_mode is 'auto'
    scanner.load_cache()

    # Fetch scan_mode from Supabase before deciding whether to auto-scan
    _scan_mode = "auto"  # safe default
    try:
        from app.core.supabase_client import supabase_admin, sb_run
        _sm_res = await sb_run(
            lambda: supabase_admin.table("settings").select("scan_mode").order("updated_at", desc=True).limit(1).execute()
        )
        if _sm_res.data and _sm_res.data[0].get("scan_mode"):
            _scan_mode = _sm_res.data[0]["scan_mode"]
    except Exception as _e:
        logger.warning(f"Could not fetch scan_mode from Supabase, defaulting to 'auto': {_e}")

    if _scan_mode == "auto":
        async def _refresh_scan():
            await scanner.scan_and_cache()
            logger.info(f"✅ Background app scan complete — {len(scanner.apps)} apps")
        asyncio.create_task(_refresh_scan())
        logger.info(f"✅ App discovery ready ({len(scanner.apps)} cached apps, auto-refresh running in background)")
    else:
        logger.info(f"✅ App discovery ready ({len(scanner.apps)} cached apps, manual scan mode — no auto-refresh)")
    app.state.app_scanner = scanner

    # ── Background File Indexer ──────────────────────────────────────────────
    from automation.desktop.file_indexer import get_indexer
    file_indexer = get_indexer()
    if _scan_mode == "auto":
        file_indexer.start_background_indexing()
        logger.info("✅ File indexer running in background")
    else:
        logger.info("✅ File indexer ready (manual scan mode — skipping auto-indexing)")
    app.state.file_indexer = file_indexer

    register_all_intents()
    logger.info("✅ Command intents registered")

    # ── Initialize Browser Engine ─────────────────────────────────────────
    try:
        # Engine is lazy-initialized when actions are performed,
        # but we can import it here to ensure it's ready.
        from automation.browser.browser_engine import BrowserEngine
        engine = BrowserEngine()
        logger.info("🌐 Browser Engine ready for lazy initialization.")
    except Exception as e:
        logger.warning(f"⚠️ Browser integration failed: {e}")

    # ── Background Initialization ───────────────────────────────────────────
    # Pushing heavy tasks to the background allows Uvicorn to bind the port instantly
    async def _background_init(app_state, running_loop):
        # 1. Restore Settings from Supabase (overrides .env if DB has values set)
        try:
            from app.core.supabase_client import supabase_admin, sb_run
            from app.routers.settings_router import _apply_llm_settings
            res = await sb_run(
                lambda: supabase_admin.table("settings").select("*").order("updated_at", desc=True).limit(1).execute()
            )
            if res.data:
                s = res.data[0]
                from app.config import settings as global_settings
                for field in ("wake_word", "whisper_model", "tts_provider", "piper_voice",
                              "active_mode_timeout", "browser_type", "enable_desktop_overlay",
                              "crm_url", "crm_keywords", "crm_sites",
                              "llm_provider", "llm_model",
                              "llm_mode", "llm_temperature"):
                    if field in s and s[field] is not None and hasattr(global_settings, field):
                        setattr(global_settings, field, s[field])
                if s.get("llm_api_key_encrypted"):
                    _apply_llm_settings(s)
                logger.info("✅ All settings restored from Supabase")
        except Exception as e:
            logger.warning(f"⚠️  Could not restore settings from Supabase: {e}")

        # 2. Initialize LLM from .env (fallback if DB has no LLM set)
        from app.services.llm.llm_service import llm_service
        if not llm_service.is_ready:
            _init_llm_from_env()

        # 3. Pre-load workflow macros into in-memory cache (eliminates per-command DB query)
        from app.services.command_service import command_service
        await command_service.refresh_workflows_cache()

        # 4. Start the voice pipeline in the background process
        try:
            from voice.pipeline import VoicePipeline, PipelineState
            from app.websocket.manager import ws_manager
            from app.routers.voice import _pipeline_state

            def on_state_change(state: PipelineState):
                _pipeline_state["pipeline_state"] = state.value
                _pipeline_state["listening"] = (state == PipelineState.LISTENING)
                _pipeline_state["wake_word_active"] = (state == PipelineState.IDLE)
                asyncio.run_coroutine_threadsafe(
                    ws_manager.broadcast("pipeline_state", {"state": state.value}), running_loop
                )
                asyncio.run_coroutine_threadsafe(
                    ws_manager.broadcast(
                        "wake_word_detected" if state == PipelineState.LISTENING else "pipeline_state",
                        {"state": state.value, "wake_word_active": _pipeline_state["wake_word_active"]}
                    ), running_loop
                )

            def on_transcript(text: str, is_final: bool):
                asyncio.run_coroutine_threadsafe(
                    ws_manager.broadcast("transcript", {"text": text, "is_final": is_final}), running_loop
                )

            def on_command_result(result: dict):
                asyncio.run_coroutine_threadsafe(
                    ws_manager.broadcast("command_executed", result), running_loop
                )

            # Move VoicePipeline init to a thread to prevent blocking the async loop
            pipeline = await asyncio.to_thread(
                VoicePipeline,
                on_state_change=on_state_change,
                on_transcript=on_transcript,
                on_command_result=on_command_result,
            )
            pipeline.start()
            app_state.pipeline = pipeline
            _pipeline_state["wake_word_active"] = True
            asyncio.run_coroutine_threadsafe(
                ws_manager.broadcast("pipeline_state", {"state": "idle", "wake_word_active": True}), running_loop
            )
            logger.info("🎙️ Voice pipeline started — wake word listening in background")

            # 5. Pre-warm Whisper model — loads it into RAM before the first voice command
            # Eliminates the cold-start delay on the very first transcription
            try:
                from voice.stt.transcriber import Transcriber
                await asyncio.to_thread(Transcriber()._load_model)
                logger.info("🎙️ Whisper model pre-warmed and ready")
            except Exception as warm_err:
                logger.warning(f"⚠️ Could not pre-warm Whisper: {warm_err}")

            # 6. Pre-warm Semantic Router (FastEmbed)
            try:
                from app.services.semantic_router import semantic_router
                from app.services.command_service import command_service
                await asyncio.to_thread(semantic_router.initialize, command_service._intents)
                logger.info("🧠 Semantic Router pre-warmed and ready")
            except Exception as warm_err:
                logger.warning(f"⚠️ Could not pre-warm Semantic Router: {warm_err}")

            # 7. Start Desktop Overlay if enabled
            from app.config import settings as global_settings
            if getattr(global_settings, "enable_desktop_overlay", False):
                import subprocess, os, sys
                from pathlib import Path
                _BACKEND = Path(__file__).resolve().parent.parent
                python_exe = os.path.join(str(_BACKEND), ".venv", "Scripts", "python.exe")
                if not os.path.exists(python_exe):
                    python_exe = sys.executable
                overlay_path = os.path.join(str(_BACKEND), "automation", "desktop", "overlay.py")
                if os.path.exists(overlay_path):
                    app_state.overlay_process = subprocess.Popen(
                        [python_exe, overlay_path],
                        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
                    )
                    logger.info("🖥️ Desktop Overlay started automatically on startup")

        except Exception as e:
            logger.warning(f"⚠️  Voice pipeline failed to start (API will still work): {e}")
            app_state.pipeline = None

    # Spawn the background initialization task so lifespan yields immediately
    loop = asyncio.get_running_loop()
    asyncio.create_task(_background_init(app.state, loop))

    yield

    logger.info("🛑 ACE Voice Controller shutting down")
    if getattr(app.state, "pipeline", None):
        app.state.pipeline.stop()
    if getattr(app.state, "file_indexer", None):
        app.state.file_indexer.stop()
    if getattr(app.state, "overlay_process", None):
        try:
            app.state.overlay_process.terminate()
            app.state.overlay_process.wait(timeout=3)
        except:
            pass


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


# ─── Test Endpoints (Dev only) ───────────────────────────────────────────────


@app.get("/api/test/replay", tags=["Dev"])
async def test_replay_broadcast():
    """Broadcast a mock replay to all connected websocket clients (including overlay)."""
    text = "The CRM has been opened successfully. You can now navigate to the login page."
    await ws_manager.broadcast("transcript", {
        "text": f"__replay__{text}",
        "is_final": True
    })
    return {"status": "broadcast_sent", "replay": text}


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
                    elif data.get("type") == "trigger_listen":
                        logger.info("🔘 Overlay Command Received: Trigger Listen")
                        if getattr(app.state, "pipeline", None):
                            app.state.pipeline.trigger_listening()
                    elif data.get("type") == "stop_listen":
                        logger.info("🔘 Overlay Command Received: Stop Listen")
                        if getattr(app.state, "pipeline", None):
                            app.state.pipeline.stop_listening()
                    elif data.get("type") == "replay":
                        logger.info("🔘 Overlay Command Received: Replay")
                        if getattr(app.state, "pipeline", None):
                            app.state.pipeline.replay()
                    elif data.get("type") == "suggestion":
                        logger.info("🔘 Overlay Command Received: Suggestion")
                        if getattr(app.state, "pipeline", None):
                            app.state.pipeline.speak_suggestion()
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
# Reload
