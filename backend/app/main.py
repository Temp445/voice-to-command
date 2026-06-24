"""
ACE Voice Controller — FastAPI Main Application
Entry point: mounts all routers, middleware, WebSocket endpoint, and lifecycle events.

Startup optimized for <15s Phase 1 (server ready to accept commands).
Heavy models (Piper TTS, Whisper, Semantic Router, Wake Word) load lazily in background.
"""

import asyncio
import sys
import warnings

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from pathlib import Path
_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.append(str(_ROOT))

from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
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
    Priority: DB settings (set later in lifespan) > .env values.
    """
    from app.services.llm.llm_service import llm_service

    key_map = {
        "groq":     settings.groq_api_key,
        "openai":   settings.openai_api_key,
        "gemini":   settings.google_api_key,
        "claude":   settings.anthropic_api_key,
        "deepseek": settings.deepseek_api_key,
    }

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
        logger.info(f"ℹ️  LLM provider '{provider}' has no API key — AI features disabled.")
        return

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
    """
    Startup strategy — 3 phases, designed so Phase 1 finishes in <15s:

    SYNC (blocking, must finish before yield):
      • Logging setup
      • App cache load from disk  ← JSON read, near-instant
      • Intent registration       ← pure Python, <100ms

    BACKGROUND TASK (non-blocking, fires after yield):
      Phase 1 — fast I/O  (parallel, ~2–5s total):
        • Restore settings from Supabase
        • Init LLM from .env
        • Warm website shortcut cache
        • Fetch scan_mode from Supabase

      Phase 2 — voice pipeline (~3–5s):
        • Build VoicePipeline (in thread to avoid blocking event loop)
        • Start wake word detector

      Phase 3 — heavy model pre-warm (delayed 15s, parallel):
        • Piper TTS model into RAM
        • Whisper STT model into RAM
        • Semantic Router ONNX embeddings

      Phase 4 — optional background tasks:
        • Auto app scan (if scan_mode == "auto")
        • File indexer
        • Desktop overlay process
    """
    setup_logging()
    logger.info(f"🚀 Starting {settings.app_name} v{settings.app_version}")

    # ── Sync: instant tasks only ──────────────────────────────────────────────
    from automation.desktop.app_scanner import get_scanner
    scanner = get_scanner()
    scanner.load_cache()   # pure JSON disk read — <50ms
    app.state.app_scanner = scanner

    register_all_intents()  # pure Python regex compile — <100ms
    logger.info("✅ Intent registry ready")

    # Server is now fully ready to accept requests
    loop = asyncio.get_running_loop()
    asyncio.create_task(_background_init(app.state, loop))

    yield

    # ── Shutdown ──────────────────────────────────────────────────────────────
    logger.info("🛑 ACE Voice Controller shutting down")
    if getattr(app.state, "pipeline", None):
        app.state.pipeline.stop()
    if getattr(app.state, "file_indexer", None):
        app.state.file_indexer.stop()
    if getattr(app.state, "overlay_process", None):
        try:
            app.state.overlay_process.terminate()
            app.state.overlay_process.wait(timeout=3)
        except Exception as e:
            logger.warning(f"Overlay shutdown error: {e}")


async def _background_init(app_state, running_loop: asyncio.AbstractEventLoop):
    """
    All heavy initialization runs here, after the server has already yielded
    and is accepting requests. Phases run in order; within each phase tasks
    are concurrent via asyncio.gather().
    """

    # ── Phase 1: Fast I/O — run all in parallel ───────────────────────────────
    logger.info("⚡ Phase 1: Settings + LLM + caches (parallel)...")
    t0 = asyncio.get_event_loop().time()

    async def _restore_settings():
        try:
            from app.core.supabase_client import supabase_admin, sb_run
            from app.routers.settings_router import _apply_llm_settings, _apply_elevenlabs_settings, _apply_deepgram_settings
            # Hard 5s timeout — never let a slow/cold Supabase hang Phase 1
            res = await asyncio.wait_for(
                sb_run(lambda: supabase_admin.table("settings").select("*").order("updated_at", desc=True).limit(1).execute()),
                timeout=5.0,
            )
            if res.data:
                s = res.data[0]
                from app.config import settings as gs
                if s.get("user_id"):
                    gs.owner_user_id = s["user_id"]
                for field in (
                    "wake_word", "whisper_model", "tts_provider", "piper_voice",
                    "active_mode_timeout", "require_wake_word_always", "browser_type",
                    "enable_desktop_overlay", "crm_url", "crm_keywords", "crm_sites",
                    "llm_provider", "llm_model", "llm_mode", "llm_temperature",
                    "scan_mode", "stt_provider",
                ):
                    if field in s and s[field] is not None and hasattr(gs, field):
                        setattr(gs, field, s[field])
                if s.get("llm_api_key_encrypted"):
                    _apply_llm_settings(s)
                if s.get("elevenlabs_api_key_encrypted"):
                    _apply_elevenlabs_settings(s)
                if s.get("deepgram_api_key_encrypted"):
                    _apply_deepgram_settings(s)
                logger.info(f"✅ Settings restored (user={gs.owner_user_id})")
        except asyncio.TimeoutError:
            logger.warning("⚠️  Settings restore timed out after 5s — using defaults. Will retry on next restart.")
        except Exception as e:
            logger.warning(f"⚠️  Could not restore settings: {e}")

    async def _init_llm():
        from app.services.llm.llm_service import llm_service
        if not llm_service.is_ready:
            _init_llm_from_env()

    async def _warm_shortcuts():
        from app.services.command_service import command_service
        await command_service.warm_website_shortcuts()

    async def _prewarm_browser():
        """Launch the Playwright browser in background during Phase 1.
        
        Without this, the FIRST voice command that opens a website triggers a
        cold browser launch: Playwright init (~2s) + Chrome persistent context
        launch (~10–15s) + stealth patch (~3s) + CDP maximize (~0.5s) = 15–30s
        (measured at 106s on slow HDD + cold Chrome profile).
        
        Pre-warming absorbs all of that cost at startup so the first command
        navigates to its URL immediately.
        """
        try:
            # Small delay so Phase 1 settings (browser_type etc.) are applied first
            await asyncio.sleep(1.0)
            from automation.browser.browser_engine import BrowserEngine
            engine = BrowserEngine()
            await engine.prewarm_profile()
            logger.info("✅ Browser pre-warmed invisibly — next navigation will be fast")
        except Exception as e:
            logger.warning(f"⚠️  Browser pre-warm failed (non-fatal, will cold-start on first use): {e}")

    await asyncio.gather(
        _restore_settings(),
        _init_llm(),
        _warm_shortcuts(),
        _prewarm_browser(),
        return_exceptions=True,
    )
    logger.info(f"✅ Phase 1 done in {asyncio.get_event_loop().time() - t0:.1f}s — server fully operational")

    # Resolve scan_mode from restored settings
    from app.config import settings as gs
    _scan_mode = getattr(gs, "scan_mode", "manual")

    # ── Phase 2: Voice pipeline ───────────────────────────────────────────────
    # Must run after Phase 1 so wake_word / whisper_model settings are applied.
    logger.info("⚡ Phase 2: Voice pipeline...")
    t1 = asyncio.get_event_loop().time()

    try:
        from voice.pipeline import VoicePipeline, PipelineState
        from app.routers.voice import _pipeline_state

        def on_state_change(state: PipelineState):
            _pipeline_state["pipeline_state"] = state.value
            _pipeline_state["listening"] = (state == PipelineState.LISTENING)
            _pipeline_state["wake_word_active"] = (state == PipelineState.IDLE)
            asyncio.run_coroutine_threadsafe(
                ws_manager.broadcast("pipeline_state", {"state": state.value}), running_loop
            )

        def on_transcript(text: str, is_final: bool):
            asyncio.run_coroutine_threadsafe(
                ws_manager.broadcast("transcript", {"text": text, "is_final": is_final}), running_loop
            )

        def on_command_result(result: dict):
            asyncio.run_coroutine_threadsafe(
                ws_manager.broadcast("command_executed", result), running_loop
            )

        # Build VoicePipeline in a thread — its __init__ touches pygame mixer
        # which can briefly block the event loop on Windows audio device probing.
        pipeline = await asyncio.to_thread(
            VoicePipeline,
            on_state_change=on_state_change,
            on_transcript=on_transcript,
            on_command_result=on_command_result,
        )
        app_state.pipeline = pipeline

        if getattr(gs, "owner_user_id", None):
            pipeline.start()
            _pipeline_state["wake_word_active"] = True
            asyncio.run_coroutine_threadsafe(
                ws_manager.broadcast("pipeline_state", {"state": "idle", "wake_word_active": True}),
                running_loop,
            )
            logger.info(f"🎙️ Voice pipeline started in {asyncio.get_event_loop().time() - t1:.1f}s")
        else:
            logger.info("ℹ️  No active user — voice pipeline paused until auth")

    except Exception as e:
        logger.warning(f"⚠️  Voice pipeline failed (API still works): {e}")
        app_state.pipeline = None

    # ── Phase 3: Heavy model pre-warm (parallel, delayed 15s) ────────────────
    # Delayed so Phase 2's wake word detector has time to claim the ONNX runtime
    # before Piper / Whisper / FastEmbed also try to load ONNX sessions.
    # Concurrent ONNX session creation on Windows can deadlock.
    async def _prewarm_all():
        await asyncio.sleep(15)
        logger.info("⚡ Phase 3: Pre-warming Piper TTS + Whisper STT + Semantic Router (parallel)...")

        async def _warm_tts():
            try:
                from voice.tts.provider_factory import get_tts_provider
                provider = await get_tts_provider()
                await provider.synthesize("Ready.")  # forces model into RAM
                logger.info("✅ Piper TTS pre-warmed")
            except Exception as e:
                logger.warning(f"TTS pre-warm failed: {e}")

        async def _warm_stt():
            try:
                import numpy as np
                from voice.stt.provider_factory import get_stt_provider
                stt = get_stt_provider()
                silent = np.zeros(16000, dtype=np.int16).tobytes()
                await asyncio.to_thread(stt.transcribe, silent)
                logger.info("✅ Whisper STT pre-warmed")
            except Exception as e:
                logger.warning(f"STT pre-warm failed: {e}")

        async def _warm_semantic():
            try:
                from app.services.semantic_router import semantic_router
                from app.services.command_service import command_service
                await asyncio.to_thread(semantic_router.initialize, command_service._intents)
                logger.info("✅ Semantic Router pre-warmed")
            except Exception as e:
                logger.warning(f"Semantic Router pre-warm failed: {e}")

        # TTS and STT share the ONNX runtime — run sequentially to avoid deadlock.
        # Semantic Router uses FastEmbed (separate runtime) — safe to run in parallel with either.
        await asyncio.gather(_warm_tts(), _warm_semantic(), return_exceptions=True)
        await _warm_stt()   # after TTS to avoid ONNX contention
        logger.info("✅ Phase 3 complete — all models warm and ready")

    asyncio.create_task(_prewarm_all())

    # ── Phase 4: Background housekeeping ─────────────────────────────────────
    if _scan_mode == "auto":
        async def _refresh_scan():
            await asyncio.to_thread(app_state.app_scanner._scan_all_parallel)
            app_state.app_scanner.save_cache()
            logger.info(f"✅ App scan complete — {len(app_state.app_scanner.apps)} apps")
        asyncio.create_task(_refresh_scan())

        from automation.desktop.file_indexer import get_indexer
        file_indexer = get_indexer()
        file_indexer.start_background_indexing()
        app_state.file_indexer = file_indexer
        logger.info("✅ File indexer running in background")
    else:
        logger.info("✅ Manual scan mode — skipping auto app scan and file indexer")

    # Desktop Overlay (only after pipeline is confirmed running)
    if getattr(gs, "enable_desktop_overlay", False) and getattr(gs, "owner_user_id", None):
        import subprocess, os
        from pathlib import Path as _Path
        _BACKEND = _Path(__file__).resolve().parent.parent
        python_exe = os.path.join(str(_BACKEND), ".venv", "Scripts", "python.exe")
        if not os.path.exists(python_exe):
            python_exe = sys.executable
        overlay_path = os.path.join(str(_BACKEND), "automation", "desktop", "overlay", "__main__.py")
        if os.path.exists(overlay_path):
            if sys.platform == "win32":
                try:
                    import psutil
                    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
                        try:
                            if proc.info["name"] in ("python.exe", "pythonw.exe"):
                                if any("overlay" in str(c) for c in (proc.info.get("cmdline") or [])):
                                    if proc.pid != os.getpid():
                                        proc.terminate()
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            pass
                except ImportError:
                    pass
            app_state.overlay_process = subprocess.Popen(
                [python_exe, "-m", "automation.desktop.overlay"],
                cwd=str(_BACKEND),
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
            logger.info("🖥️ Desktop Overlay started")

    logger.info("🎉 ACE fully initialized — all background tasks running")


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

from app.routers import auth, voice, commands, automation, settings_router  # noqa: E402
from app.routers import llm_router  # noqa: E402

app.include_router(auth.router,            prefix="/api/auth",       tags=["Auth"])
app.include_router(voice.router,           prefix="/api/voice",      tags=["Voice"])
app.include_router(commands.router,        prefix="/api/commands",   tags=["Commands"])
app.include_router(automation.router,      prefix="/api/automation", tags=["Automation"])
app.include_router(settings_router.router, prefix="/api/settings",   tags=["Settings"])
app.include_router(llm_router.router,      prefix="/api/llm",        tags=["AI Assistant"])


# ─── Test Endpoints (Dev only) ───────────────────────────────────────────────

@app.get("/api/test/replay", tags=["Dev"])
async def test_replay_broadcast():
    if not settings.debug:
        raise HTTPException(status_code=403, detail="Dev endpoints are disabled in production.")
    text = "The CRM has been opened successfully. You can now navigate to the login page."
    await ws_manager.broadcast("transcript", {"text": f"__replay__{text}", "is_final": True})
    return {"status": "broadcast_sent", "replay": text}


# ─── WebSocket ───────────────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        await ws_manager.send_to(websocket, "connected", {
            "message": "ACE WebSocket connected",
            "version": settings.app_version,
            "wake_word": settings.wake_word,
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
                    msg_type = data.get("type")
                    if msg_type == "ping":
                        await ws_manager.send_to(websocket, "pong", {})
                    elif msg_type == "trigger_listen":
                        if getattr(app.state, "pipeline", None):
                            app.state.pipeline.trigger_listening()
                    elif msg_type == "stop_listen":
                        if getattr(app.state, "pipeline", None):
                            app.state.pipeline.stop_listening()
                    elif msg_type == "stop":
                        if getattr(app.state, "pipeline", None):
                            app.state.pipeline.deactivate()
                    elif msg_type == "replay":
                        if getattr(app.state, "pipeline", None):
                            app.state.pipeline.replay()
                    elif msg_type == "suggestion":
                        if getattr(app.state, "pipeline", None):
                            app.state.pipeline.speak_suggestion()
                except json.JSONDecodeError:
                    pass
    except (WebSocketDisconnect, RuntimeError):
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


@app.get("/api/health/ready", tags=["Health"])
async def readiness_check():
    """Returns 200 as soon as Phase 1 is done (pipeline may still be loading)."""
    pipeline = getattr(app.state, "pipeline", None)
    return JSONResponse({
        "status": "ok",
        "pipeline_ready": pipeline is not None,
        "wake_word_active": getattr(pipeline, "_running", False) if pipeline else False,
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