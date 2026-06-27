"""Settings router — Read and update user settings via Supabase client."""

import uuid
from fastapi import APIRouter, Depends, Request, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from loguru import logger

from app.schemas import SettingsUpdate, SettingsResponse
from app.core.security import encrypt_api_key, decrypt_api_key, decode_access_token
from app.core.supabase_client import supabase_admin, sb_run
from app.websocket.manager import ws_manager

router = APIRouter()

_bearer = HTTPBearer(auto_error=False)
_FALLBACK_USER_ID = "00000000-0000-0000-0000-000000000001"

# Default values for a new settings row
_DEFAULTS = {
    "wake_word": "alexa",
    "stt_provider": "whisper",
    "stt_noise_cancellation": True,
    "whisper_model": "base",
    "active_mode_timeout": 120,
    "require_wake_word_always": True,
    "tts_provider": "piper",

    "piper_voice": "en_US-lessac-medium",
    "theme": "dark",
    "sidebar_collapsed": False,
    "browser_type": "chromium",
    "startup_on_boot": True,
    "minimize_to_tray": True,
    "browser_animations_enabled": True,
    "enable_desktop_overlay": True,
    "restrict_browser_automation": False,
    "overlay_shortcut": "Alt+A",
    "listen_shortcut": "Alt+S",
    "crm_url": "",
    "crm_keywords": "",
    "crm_sites": "[]",
    "llm_enabled": False,
    "llm_provider": "groq",
    "llm_model": "llama-3.3-70b-versatile",
    "llm_api_key_encrypted": None,
    "llm_temperature": 0.7,
    "llm_mode": "fallback",
    "scan_mode": "manual",
    "elevenlabs_api_key_encrypted": None,
    "deepgram_api_key_encrypted": None,
    "reply_sound": True,
    "speech_rate": 1.0,
    "screen_settings_visible_to_users": True,
}


# ── Auth Dependency ───────────────────────────────────────────────────────────

async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        payload = decode_access_token(credentials.credentials)
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        return user_id
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")


# ── Internal Helpers ──────────────────────────────────────────────────────────

async def _get_or_create_settings(user_id: str) -> dict:
    """Fetch settings for user_id; create with defaults if not found."""
    res = await sb_run(lambda: supabase_admin.table("settings").select("*").eq("user_id", user_id).execute())
    if res.data:
        return res.data[0]

    # Row not found — attempt insert with defaults
    new_row = {**_DEFAULTS, "id": str(uuid.uuid4()), "user_id": user_id}
    try:
        await sb_run(lambda: supabase_admin.table("settings").insert(new_row).execute())
        logger.info(f"Created default settings for user {user_id}")
        return new_row
    except Exception as e:
        if "23505" in str(e):
            # Duplicate key — row already exists but SELECT couldn't see it (RLS).
            # Use upsert to fetch + return the existing row.
            logger.info(f"Settings row exists for {user_id} — fetching via upsert.")
            try:
                res2 = await sb_run(
                    lambda: supabase_admin.table("settings")
                    .upsert(new_row, on_conflict="user_id")
                    .execute()
                )
                if res2.data:
                    return res2.data[0]
            except Exception as e2:
                logger.warning(f"Upsert fallback also failed: {e2}")
        else:
            logger.warning(f"Could not persist settings for user {user_id}: {e}")
        return new_row  # Return in-memory defaults as safe fallback


def _build_response(s: dict, role: str = "user", permissions: dict = None) -> SettingsResponse:
    return SettingsResponse(
        wake_word=s.get("wake_word", "alexa"),
        whisper_model=s.get("whisper_model", "base"),
        stt_provider=s.get("stt_provider", "whisper"),
        stt_noise_cancellation=s.get("stt_noise_cancellation", True),
        active_mode_timeout=s.get("active_mode_timeout", 120),
        require_wake_word_always=s.get("require_wake_word_always", True),
        tts_provider=s.get("tts_provider", "piper"),
        piper_voice=s.get("piper_voice", "en_US-lessac-medium"),
        theme=s.get("theme", "dark"),
        browser_type=s.get("browser_type", "chromium"),
        startup_on_boot=s.get("startup_on_boot", True),
        minimize_to_tray=s.get("minimize_to_tray", True),
        browser_animations_enabled=s.get("browser_animations_enabled", True),
        enable_desktop_overlay=s.get("enable_desktop_overlay", True),
        overlay_shortcut=s.get("overlay_shortcut", "Alt+A"),
        listen_shortcut=s.get("listen_shortcut", "Alt+S"),

        crm_url=s.get("crm_url", ""),
        crm_keywords=s.get("crm_keywords", ""),
        crm_sites=s.get("crm_sites", "[]"),
        restrict_browser_automation=s.get("restrict_browser_automation", False),
        llm_enabled=s.get("llm_enabled", False),
        llm_provider=s.get("llm_provider", "groq"),
        llm_model=s.get("llm_model", "llama-3.3-70b-versatile"),
        llm_configured=bool(s.get("llm_api_key_encrypted")),
        llm_temperature=s.get("llm_temperature", 0.7),
        llm_mode=s.get("llm_mode", "fallback"),
        scan_mode=s.get("scan_mode", "manual"),
        elevenlabs_configured=bool(s.get("elevenlabs_api_key_encrypted")),
        deepgram_configured=bool(s.get("deepgram_api_key_encrypted")),
        reply_sound=s.get("reply_sound", True),
        speech_rate=s.get("speech_rate", 1.0),
        screen_settings_visible_to_users=s.get("screen_settings_visible_to_users", True),
        role=role,
        permissions=permissions or {},
    )


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("", response_model=SettingsResponse)
async def get_settings(request: Request, user_id: str = Depends(get_current_user_id)):
    s = await _get_or_create_settings(user_id)
    _apply_elevenlabs_settings(s)
    _apply_deepgram_settings(s)
    
    from app.config import settings as global_settings
    global_settings.owner_user_id = user_id
    for field, value in s.items():
        if value is not None and hasattr(global_settings, field):
            setattr(global_settings, field, value)
    
    pipeline = getattr(request.app.state, "pipeline", None)
    if pipeline and not pipeline._running:
        logger.info("🎙️ Starting Voice Pipeline on first authenticated settings load...")
        pipeline.start()
        from app.routers.voice import _pipeline_state
        _pipeline_state["wake_word_active"] = True
        
    if s.get("enable_desktop_overlay", False) and not getattr(request.app.state, "overlay_process", None):
        import subprocess, os, sys
        from pathlib import Path
        _ROOT = Path(__file__).resolve().parent.parent.parent
        python_exe = os.path.join(str(_ROOT), ".venv", "Scripts", "python.exe")
        if not os.path.exists(python_exe):
            python_exe = sys.executable
        overlay_path = os.path.join(str(_ROOT), "automation", "desktop", "overlay", "__main__.py")
        if os.path.exists(overlay_path):
            request.app.state.overlay_process = subprocess.Popen(
                [python_exe, "-m", "automation.desktop.overlay"],
                cwd=str(_ROOT),
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            )
            logger.info("🖥️ Desktop Overlay started dynamically after login")
            
    # --- RBAC and Policies Logic ---
    user_res = await sb_run(lambda: supabase_admin.table("users").select("role").eq("id", user_id).execute())
    role = user_res.data[0].get("role") if user_res.data else "user"
    
    policy_res = await sb_run(lambda: supabase_admin.table("user_policies").select("permissions").eq("user_id", user_id).execute())
    permissions = policy_res.data[0].get("permissions") if policy_res.data else {}
    
    restricted_keys = {
        "enable_desktop_overlay",
        "browser_animations_enabled",
        "overlay_shortcut",
        "listen_shortcut"
    }
    
    final_permissions = {}
    for key in _DEFAULTS.keys():
        final_permissions[key] = {"visible": True, "mutable": True}
        
    for key, val in permissions.items():
        if isinstance(val, dict) and key in final_permissions:
            final_permissions[key]["visible"] = val.get("visible", True)
            final_permissions[key]["mutable"] = val.get("mutable", True)
            
    if role != "admin" and not s.get("screen_settings_visible_to_users", True):
        for rk in restricted_keys:
            final_permissions[rk] = {"visible": False, "mutable": False}
            
    s_filtered = {**s}
    if role != "admin":
        for key, val in final_permissions.items():
            if not val.get("visible", True) and key in s_filtered:
                s_filtered[key] = _DEFAULTS.get(key)
        if s_filtered.get("stt_provider") == "deepgram" and not final_permissions.get("deepgram_api_key", {}).get("visible", True):
            s_filtered["stt_provider"] = "whisper"
        elif s_filtered.get("stt_provider") == "elevenlabs" and not final_permissions.get("elevenlabs_api_key", {}).get("visible", True):
            s_filtered["stt_provider"] = "whisper"
                
    return _build_response(s_filtered, role=role, permissions=final_permissions)


@router.patch("", response_model=SettingsResponse)
async def update_settings(
    body: SettingsUpdate,
    request: Request,
    user_id: str = Depends(get_current_user_id),
):
    s = await _get_or_create_settings(user_id)
    
    # --- RBAC and Policies Logic ---
    user_res = await sb_run(lambda: supabase_admin.table("users").select("role").eq("id", user_id).execute())
    role = user_res.data[0].get("role") if user_res.data else "user"
    
    policy_res = await sb_run(lambda: supabase_admin.table("user_policies").select("permissions").eq("user_id", user_id).execute())
    permissions = policy_res.data[0].get("permissions") if policy_res.data else {}
    
    restricted_keys = {
        "enable_desktop_overlay",
        "browser_animations_enabled",
        "overlay_shortcut",
        "listen_shortcut"
    }
    
    final_permissions = {}
    for key in _DEFAULTS.keys():
        final_permissions[key] = {"visible": True, "mutable": True}
        
    for key, val in permissions.items():
        if isinstance(val, dict) and key in final_permissions:
            final_permissions[key]["visible"] = val.get("visible", True)
            final_permissions[key]["mutable"] = val.get("mutable", True)
            
    if role != "admin" and not s.get("screen_settings_visible_to_users", True):
        for rk in restricted_keys:
            final_permissions[rk] = {"visible": False, "mutable": False}
            
    # Perform mutable checks on fields being updated
    patch_dict = body.model_dump(exclude_none=True)
    if role != "admin":
        if "screen_settings_visible_to_users" in patch_dict:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Modification forbidden: Only administrators can toggle settings visibility."
            )
        for field in patch_dict.keys():
            if field in final_permissions and not final_permissions[field].get("mutable", True):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Modification forbidden: Settings key '{field}' is read-only or restricted."
                )
    from app.config import settings as global_settings
    global_settings.owner_user_id = user_id
    updates: dict = {}

    for field, value in body.model_dump(exclude_none=True).items():
        if field == "llm_api_key" and value:
            updates["llm_api_key_encrypted"] = encrypt_api_key(value)
        elif field == "elevenlabs_api_key" and value:
            updates["elevenlabs_api_key_encrypted"] = encrypt_api_key(value)
            global_settings.elevenlabs_api_key = value
        elif field == "deepgram_api_key" and value:
            updates["deepgram_api_key_encrypted"] = encrypt_api_key(value)
            global_settings.deepgram_api_key = value
        else:
            updates[field] = value
            # Sync to in-memory config
            if hasattr(global_settings, field):
                setattr(global_settings, field, value)

    # When crm_sites is updated, also sync crm_url + crm_keywords from the first site
    # so all existing backend logic (browser_controller, intent_registry) keeps working.
    if "crm_sites" in updates:
        import json as _json
        try:
            _sites = _json.loads(updates["crm_sites"])
            if _sites and isinstance(_sites, list):
                _first = _sites[0]
                updates["crm_url"] = _first.get("url", "")
                updates["crm_keywords"] = _first.get("keywords", "")
                from app.config import settings as global_settings
                global_settings.crm_url = updates["crm_url"]
                global_settings.crm_keywords = updates["crm_keywords"]
        except Exception as e:
            logger.error(f"[{__name__}] {type(e).__name__}: {e}")
            pass

    if updates:
        try:
            await sb_run(
                lambda: supabase_admin.table("settings").update(updates).eq("user_id", user_id).execute()
            )
        except Exception as e:
            # PGRST204 = column not found in schema cache (migration not yet applied).
            # Strip the unknown field and retry so existing settings still save.
            if "PGRST204" in str(e) or "schema cache" in str(e):
                import re as _re
                # Extract which column is missing from the error message
                _missing = _re.search(r"'(\w+)' column", str(e))
                _bad_col = _missing.group(1) if _missing else None
                if _bad_col and _bad_col in updates:
                    logger.warning(
                        f"Column '{_bad_col}' not yet in DB schema — skipping it in update. "
                        f"Run the migration: ALTER TABLE public.settings ADD COLUMN IF NOT EXISTS "
                        f"{_bad_col} TEXT DEFAULT 'auto';"
                    )
                    _safe_updates = {k: v for k, v in updates.items() if k != _bad_col}
                    if _safe_updates:
                        await sb_run(
                            lambda: supabase_admin.table("settings").update(_safe_updates).eq("user_id", user_id).execute()
                        )
                else:
                    raise
            else:
                raise
        s = {**s, **updates}

    # When website shortcuts (crm_sites) change, bust the in-process cache so the
    # next voice command picks up the new sites without restarting.
    if "crm_sites" in updates:
        try:
            from app.services.command_service import command_service
            command_service._ws_cache_loaded = False
            logger.info("Website shortcut cache invalidated — will reload on next command")
        except Exception as e:
            logger.error(f"[{__name__}] {type(e).__name__}: {e}")
            pass

    # Hot-swap LLM provider if LLM settings changed
    llm_fields = {"llm_provider", "llm_model", "llm_api_key", "llm_enabled", "llm_mode", "llm_temperature"}
    if any(f in body.model_dump(exclude_none=True) for f in llm_fields):
        _apply_llm_settings(s)

    # Hot-swap ElevenLabs settings if ElevenLabs settings changed
    if "elevenlabs_api_key" in body.model_dump(exclude_none=True):
        _apply_elevenlabs_settings(s)

    # Hot-reload STT model if it changed
    if "whisper_model" in body.model_dump(exclude_none=True):
        try:
            from voice.stt.transcriber import Transcriber
            Transcriber.reload_model()
        except ImportError:
            pass

    # Hot-reload Wake Word model if it changed
    if "wake_word" in body.model_dump(exclude_none=True):
        pipeline = getattr(request.app.state, "pipeline", None)
        if pipeline:
            try:
                from voice.wake_word.detector import WakeWordDetector
                from voice.pipeline import PipelineState
                logger.info(f"Hot-reloading Wake Word model to '{s['wake_word']}'...")
                
                pipeline._wake_word.stop()
                
                pipeline._wake_word = WakeWordDetector(
                    wake_word=s["wake_word"],
                    on_detected=pipeline._on_wake_word
                )
                
                if pipeline._state == PipelineState.IDLE:
                    pipeline._wake_word.start()
            except Exception as e:
                logger.error(f"Failed to hot-reload Wake Word model: {e}")

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
                overlay_path = os.path.join(str(_ROOT), "automation", "desktop", "overlay", "__main__.py")
                if os.path.exists(overlay_path):
                    request.app.state.overlay_process = subprocess.Popen(
                        [python_exe, "-m", "automation.desktop.overlay"],
                        cwd=str(_ROOT),
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

    await ws_manager.broadcast("settings_updated", {
        "tts_provider": s.get("tts_provider"),
        "wake_word": s.get("wake_word"),
        "enable_desktop_overlay": s.get("enable_desktop_overlay"),
    })

    s_filtered = {**s}
    if role != "admin":
        for key, val in final_permissions.items():
            if not val.get("visible", True) and key in s_filtered:
                s_filtered[key] = _DEFAULTS.get(key)
        if s_filtered.get("stt_provider") == "deepgram" and not final_permissions.get("deepgram_api_key", {}).get("visible", True):
            s_filtered["stt_provider"] = "whisper"
        elif s_filtered.get("stt_provider") == "elevenlabs" and not final_permissions.get("elevenlabs_api_key", {}).get("visible", True):
            s_filtered["stt_provider"] = "whisper"

    return _build_response(s_filtered, role=role, permissions=final_permissions)


def _apply_llm_settings(s: dict) -> None:
    """Hot-swap the LLM provider based on current settings."""
    from app.services.llm.llm_service import llm_service
    if not s.get("llm_enabled") or not s.get("llm_api_key_encrypted"):
        llm_service.disable("LLM provider not enabled or missing API key. Go to Settings → AI Assistant.")
        return
    try:
        api_key = decrypt_api_key(s["llm_api_key_encrypted"])
        llm_service.set_provider(
            provider_name=s.get("llm_provider", "groq"),
            api_key=api_key,
            model=s.get("llm_model", "llama-3.3-70b-versatile"),
            temperature=s.get("llm_temperature", 0.7),
            mode=s.get("llm_mode", "fallback"),
            enabled=True,
        )
    except Exception as e:
        from cryptography.fernet import InvalidToken
        if isinstance(e, InvalidToken):
            msg = "API key decryption failed — the SECRET_KEY may have changed. Re-enter your API key in Settings → AI Assistant."
        else:
            msg = str(e) or repr(e)
        logger.error(f"Failed to apply LLM settings: {msg}")
        llm_service.disable(f"Initialization Failed: {msg}")


def _apply_elevenlabs_settings(s: dict) -> None:
    """Decrypt the ElevenLabs API key and apply it to global settings."""
    from app.config import settings as global_settings
    if s.get("elevenlabs_api_key_encrypted"):
        try:
            api_key = decrypt_api_key(s["elevenlabs_api_key_encrypted"])
            global_settings.elevenlabs_api_key = api_key
            logger.info("✅ ElevenLabs STT API key loaded and decrypted")
        except Exception as e:
            logger.error(f"Failed to decrypt ElevenLabs STT API key: {e}")


def _apply_deepgram_settings(s: dict) -> None:
    """Decrypt the Deepgram API key and apply it to global settings."""
    from app.config import settings as global_settings
    if s.get("deepgram_api_key_encrypted"):
        try:
            api_key = decrypt_api_key(s["deepgram_api_key_encrypted"])
            global_settings.deepgram_api_key = api_key
            logger.info("✅ Deepgram STT API key loaded and decrypted")
        except Exception as e:
            logger.error(f"Failed to decrypt Deepgram STT API key: {e}")



# ── On-Demand Scan Endpoint ────────────────────────────────────────────────────

@router.post("/scan")
async def trigger_scan(request: Request, user_id: str = Depends(get_current_user_id)):
    """
    Manually trigger an app discovery + file index scan.
    Works regardless of whether scan_mode is 'auto' or 'manual'.
    """
    import asyncio
    from datetime import datetime, timezone

    scanner = getattr(request.app.state, "app_scanner", None)
    file_indexer = getattr(request.app.state, "file_indexer", None)

    if not scanner and not file_indexer:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="Scanner not initialised yet. Try again in a moment.")

    async def _do_scan():
        if scanner:
            await scanner.scan_and_cache()
        if file_indexer:
            file_indexer.start_background_indexing()
        app_count = len(scanner.apps) if scanner else 0
        await ws_manager.broadcast("scan_complete", {
            "app_count": app_count,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        logger.info(f"✅ Manual scan complete — {app_count} apps")

    asyncio.create_task(_do_scan())
    return {"status": "scanning", "message": "Scan started in background"}

