"""Settings router — Read and update user settings."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import UserSettings
from app.schemas import SettingsUpdate, SettingsResponse
from app.core.security import encrypt_api_key, decrypt_api_key
from app.websocket.manager import ws_manager
from loguru import logger

router = APIRouter()

_DEFAULT_USER_ID = "00000000-0000-0000-0000-000000000001"  # TODO: real user from JWT


async def _get_settings(db: AsyncSession) -> UserSettings:
    result = await db.execute(select(UserSettings).where(UserSettings.user_id == _DEFAULT_USER_ID))
    s = result.scalar_one_or_none()
    if not s:
        s = UserSettings(user_id=_DEFAULT_USER_ID)
        db.add(s)
        await db.flush()
    return s


def _build_response(s: UserSettings) -> SettingsResponse:
    return SettingsResponse(
        wake_word=s.wake_word,
        whisper_model=s.whisper_model,
        stt_provider=s.stt_provider,
        stt_noise_cancellation=s.stt_noise_cancellation,
        active_mode_timeout=s.active_mode_timeout,
        tts_provider=s.tts_provider,
        piper_voice=s.piper_voice,
        theme=s.theme,
        browser_type=s.browser_type,
        startup_on_boot=s.startup_on_boot,
        minimize_to_tray=s.minimize_to_tray,
        browser_animations_enabled=s.browser_animations_enabled,
        enable_desktop_overlay=s.enable_desktop_overlay,
        gtts_configured=bool(s.gtts_api_key_encrypted),
        crm_url=s.crm_url,
        crm_keywords=s.crm_keywords,
        # LLM
        llm_enabled=s.llm_enabled,
        llm_provider=s.llm_provider,
        llm_model=s.llm_model,
        llm_configured=bool(s.llm_api_key_encrypted),
        llm_temperature=s.llm_temperature,
        llm_mode=s.llm_mode,
    )


@router.get("", response_model=SettingsResponse)
async def get_settings(db: AsyncSession = Depends(get_db)):
    s = await _get_settings(db)
    return _build_response(s)


@router.patch("", response_model=SettingsResponse)
async def update_settings(body: SettingsUpdate, request: Request, db: AsyncSession = Depends(get_db)):
    s = await _get_settings(db)

    for field, value in body.model_dump(exclude_none=True).items():
        if field == "gtts_api_key" and value:
            s.gtts_api_key_encrypted = encrypt_api_key(value)
        elif field == "llm_api_key" and value:
            s.llm_api_key_encrypted = encrypt_api_key(value)
        elif hasattr(s, field):
            setattr(s, field, value)
            # Sync to in-memory config so that TTS and STT factories see the update immediately
            from app.config import settings as global_settings
            if hasattr(global_settings, field):
                setattr(global_settings, field, value)

    await db.commit()

    # Hot-swap LLM provider if LLM settings changed
    if any(f in body.model_dump(exclude_none=True) for f in ("llm_provider", "llm_model", "llm_api_key", "llm_enabled", "llm_mode", "llm_temperature")):
        _apply_llm_settings(s)

    # Hot-reload STT model if it changed
    if "whisper_model" in body.model_dump(exclude_none=True):
        try:
            from voice.stt.transcriber import Transcriber
            Transcriber.reload_model()
        except ImportError:
            pass

    # Hot-swap Desktop Overlay if it changed
    if "enable_desktop_overlay" in body.model_dump(exclude_none=True):
        overlay_enabled = body.enable_desktop_overlay
        if overlay_enabled:
            if not getattr(request.app.state, "overlay_process", None):
                import subprocess, os, sys
                from pathlib import Path
                _ROOT = Path(__file__).resolve().parent.parent.parent
                python_exe = os.path.join(str(_ROOT), ".venv", "Scripts", "python.exe")
                if not os.path.exists(python_exe):
                    python_exe = sys.executable
                overlay_path = os.path.join(str(_ROOT), "automation", "desktop", "overlay.py")
                if os.path.exists(overlay_path):
                    request.app.state.overlay_process = subprocess.Popen(
                        [python_exe, overlay_path],
                        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
                    )
                    logger.info("🖥️ Desktop Overlay dynamically started.")
        else:
            proc = getattr(request.app.state, "overlay_process", None)
            if proc:
                try:
                    proc.terminate()
                    proc.wait(timeout=2)
                    logger.info("🛑 Desktop Overlay dynamically stopped.")
                except Exception as e:
                    logger.warning(f"Failed to stop Desktop Overlay: {e}")
                request.app.state.overlay_process = None

    # Broadcast voice pipeline hot-reload signal
    await ws_manager.broadcast("settings_updated", {"tts_provider": s.tts_provider, "wake_word": s.wake_word})

    return _build_response(s)


def _apply_llm_settings(s: UserSettings) -> None:
    """Hot-swap the LLM provider based on current settings."""
    from app.services.llm.llm_service import llm_service
    if not s.llm_enabled or not s.llm_api_key_encrypted:
        llm_service.disable("LLM provider not enabled or missing API key. Go to Settings → AI Assistant.")
        return
    try:
        api_key = decrypt_api_key(s.llm_api_key_encrypted)
        llm_service.set_provider(
            provider_name=s.llm_provider,
            api_key=api_key,
            model=s.llm_model,
            temperature=s.llm_temperature,
            mode=s.llm_mode,
            enabled=True,
        )
    except Exception as e:
        logger.error(f"Failed to apply LLM settings: {e}")
        llm_service.disable(f"Initialization Failed: {e}")
