"""Settings router — Read and update user settings."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import UserSettings
from app.schemas import SettingsUpdate, SettingsResponse
from app.core.security import encrypt_api_key, decrypt_api_key
from app.websocket.manager import ws_manager

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


@router.get("", response_model=SettingsResponse)
async def get_settings(db: AsyncSession = Depends(get_db)):
    s = await _get_settings(db)
    return SettingsResponse(
        wake_word=s.wake_word,
        whisper_model=s.whisper_model,
        tts_provider=s.tts_provider,
        piper_voice=s.piper_voice,
        theme=s.theme,
        browser_type=s.browser_type,
        startup_on_boot=s.startup_on_boot,
        minimize_to_tray=s.minimize_to_tray,
        gtts_configured=bool(s.gtts_api_key_encrypted),
    )


@router.patch("", response_model=SettingsResponse)
async def update_settings(body: SettingsUpdate, db: AsyncSession = Depends(get_db)):
    s = await _get_settings(db)

    for field, value in body.model_dump(exclude_none=True).items():
        if field == "gtts_api_key" and value:
            s.gtts_api_key_encrypted = encrypt_api_key(value)
        elif hasattr(s, field):
            setattr(s, field, value)

    # Broadcast settings change so voice pipeline hot-reloads
    await ws_manager.broadcast("settings_updated", {"tts_provider": s.tts_provider, "wake_word": s.wake_word})

    return SettingsResponse(
        wake_word=s.wake_word,
        whisper_model=s.whisper_model,
        tts_provider=s.tts_provider,
        piper_voice=s.piper_voice,
        theme=s.theme,
        browser_type=s.browser_type,
        startup_on_boot=s.startup_on_boot,
        minimize_to_tray=s.minimize_to_tray,
        gtts_configured=bool(s.gtts_api_key_encrypted),
    )
