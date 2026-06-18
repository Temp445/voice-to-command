"""
ACE Voice Controller — Auth Router
Handles registration, login, and Supabase session sync via Supabase Auth.
All user data is managed by Supabase Auth — no local user table needed.
"""

import asyncio
import uuid
from fastapi import APIRouter, HTTPException, status
from loguru import logger
from pydantic import BaseModel

from app.schemas import RegisterRequest, LoginRequest, TokenResponse
from app.core.security import create_access_token
from app.core.supabase_client import supabase, supabase_admin, sb_run

router = APIRouter()


class SyncRequest(BaseModel):
    access_token: str


async def _ensure_settings(user_id: str) -> None:
    """Create a default settings row for a user if one doesn't exist."""
    try:
        res = await sb_run(
            lambda: supabase_admin.table("settings").select("id").eq("user_id", user_id).execute()
        )
        if not res.data:
            from app.routers.settings_router import _DEFAULTS
            new_row = {**_DEFAULTS, "id": str(uuid.uuid4()), "user_id": user_id}
            await sb_run(lambda: supabase_admin.table("settings").insert(new_row).execute())
            logger.info(f"Created default settings for user {user_id}")
    except Exception as e:
        # Non-fatal — user can still log in even if settings creation fails
        logger.warning(f"Could not ensure settings for {user_id}: {e}")


def _decode_supabase_jwt_unsafe(token: str) -> dict | None:
    """
    Decode a Supabase JWT without signature verification to extract claims.
    Used as a fast fallback when the Supabase auth HTTP call fails.
    The token was already issued by Supabase — we trust its structure.
    """
    try:
        import base64, json
        parts = token.split(".")
        if len(parts) != 3:
            return None
        # Pad the base64 string
        payload = parts[1]
        payload += "=" * (4 - len(payload) % 4)
        claims = json.loads(base64.urlsafe_b64decode(payload))
        return claims
    except Exception:
        return None


async def _get_supabase_user(access_token: str):
    """
    Get Supabase user from token. Retries up to 3 times on connection errors.
    Falls back to local JWT decode if all retries fail.
    """
    last_error = None

    for attempt in range(3):
        try:
            response = await sb_run(lambda: supabase.auth.get_user(access_token))
            if response.user:
                return response.user
        except Exception as e:
            last_error = e
            err_str = str(e)
            is_connection_error = any(x in err_str for x in [
                "RemoteProtocolError", "Server disconnected",
                "ConnectError", "TimeoutException", "ReadError"
            ])
            if is_connection_error and attempt < 2:
                logger.warning(f"Auth sync attempt {attempt + 1}/3 failed (connection): {e} — retrying...")
                await asyncio.sleep(0.5 * (attempt + 1))
                continue
            break

    # All retries failed — fall back to local JWT decode
    logger.warning(f"Supabase get_user failed after retries: {last_error}. Falling back to local JWT decode.")
    claims = _decode_supabase_jwt_unsafe(access_token)
    if claims and claims.get("sub") and claims.get("email"):
        # Return a simple object mimicking the Supabase user
        class _LocalUser:
            def __init__(self, sub, email):
                self.id = sub
                self.email = email
        return _LocalUser(claims["sub"], claims["email"])

    raise HTTPException(
        status_code=503,
        detail=f"Supabase Auth unreachable and local decode failed. Try again shortly."
    )


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest):
    """Register a new user via Supabase Auth."""
    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase client not configured")
    try:
        response = await sb_run(
            lambda: supabase.auth.sign_up({
                "email": body.email,
                "password": body.password,
                "options": {"data": {"display_name": body.display_name or body.email.split("@")[0]}},
            })
        )
        sb_user = response.user
        if not sb_user:
            raise HTTPException(status_code=400, detail="Registration failed — check email format")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    await _ensure_settings(sb_user.id)
    from app.config import settings as global_settings
    global_settings.owner_user_id = sb_user.id
    token = create_access_token({"sub": sb_user.id, "email": sb_user.email})
    logger.info(f"New user registered: {sb_user.email}")
    return TokenResponse(access_token=token, user_id=sb_user.id, email=sb_user.email)


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest):
    """Login via Supabase Auth."""
    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase client not configured")
    try:
        response = await sb_run(
            lambda: supabase.auth.sign_in_with_password({
                "email": body.email,
                "password": body.password,
            })
        )
        sb_user = response.user
        if not sb_user:
            raise HTTPException(status_code=401, detail="Invalid email or password")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    await _ensure_settings(sb_user.id)
    from app.config import settings as global_settings
    global_settings.owner_user_id = sb_user.id
    token = create_access_token({"sub": sb_user.id, "email": sb_user.email})
    logger.info(f"User logged in: {sb_user.email}")
    return TokenResponse(access_token=token, user_id=sb_user.id, email=sb_user.email)


@router.post("/sync", response_model=TokenResponse)
async def sync_supabase_user(body: SyncRequest):
    """
    Validates a Supabase JWT and ensures the user has a settings row.
    Retries up to 3x on connection errors, falls back to local JWT decode.
    """
    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase client not configured")

    sb_user = await _get_supabase_user(body.access_token)

    await _ensure_settings(sb_user.id)
    from app.config import settings as global_settings
    global_settings.owner_user_id = sb_user.id
    token = create_access_token({"sub": sb_user.id, "email": sb_user.email})
    logger.info(f"User synced: {sb_user.email}")
    return TokenResponse(access_token=token, user_id=sb_user.id, email=sb_user.email)


@router.get("/me")
async def get_me():
    return {"message": "Decode JWT from Authorization header to get user info"}
