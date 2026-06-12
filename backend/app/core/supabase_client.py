"""
ACE Voice Controller — Supabase Clients
Forces HTTP/1.1 to avoid HTTP/2 stream termination errors when running
supabase calls from multiple asyncio threads.
"""

import asyncio
from typing import Any
import httpx
from supabase import create_client, Client
from loguru import logger
from app.config import settings


def _make_client(key: str, label: str) -> Client | None:
    if not settings.supabase_url or not key:
        logger.warning(f"Supabase {label} client not configured.")
        return None
    try:
        client = create_client(settings.supabase_url, key)
        _force_http1(client, label)
        return client
    except Exception as e:
        logger.error(f"Failed to create Supabase {label} client: {e}")
        return None


def _force_http1(client: Client, label: str) -> None:
    """
    Patch the PostgREST httpx session to use HTTP/1.1 only.
    HTTP/2 causes ConnectionTerminated errors when the session is shared
    across multiple asyncio.to_thread() calls.
    """
    try:
        # 1. Patch PostgREST
        pg = (
            getattr(client, "postgrest", None)
            or getattr(client, "_rest", None)
            or getattr(client, "rest", None)
        )
        if pg is not None:
            session = getattr(pg, "session", None)
            if isinstance(session, httpx.Client):
                # Rebuild with http2=False
                pg.session = httpx.Client(
                    headers=dict(session.headers),
                    timeout=session.timeout,
                    http2=False,
                )
                logger.debug(f"[{label}] PostgREST httpx forced to HTTP/1.1")

        # 2. Patch GoTrue (Auth)
        auth = getattr(client, "auth", None)
        if auth is not None:
            auth_session = getattr(auth, "_http_client", None)
            if isinstance(auth_session, httpx.Client):
                auth._http_client = httpx.Client(
                    headers=dict(auth_session.headers),
                    timeout=auth_session.timeout,
                    http2=False,
                )
                logger.debug(f"[{label}] Auth httpx forced to HTTP/1.1")

    except Exception as e:
        logger.debug(f"[{label}] HTTP/1.1 patch skipped (non-fatal): {e}")


# ── Clients ───────────────────────────────────────────────────────────────────

# Auth client (anon/publishable key) — login / logout only
supabase: Client | None = _make_client(settings.supabase_publishable_key, "anon")

# Admin client (service/secret key) — all DB table operations (bypasses RLS)
supabase_admin: Client | None = _make_client(settings.supabase_service_key, "admin")


# ── Async helper ──────────────────────────────────────────────────────────────

async def sb_run(fn, _retries: int = 3) -> Any:
    """
    Run a synchronous Supabase call in a thread pool (non-blocking).
    Retries up to 3x on connection errors with exponential backoff.
    """
    last_exc: Exception | None = None
    for attempt in range(_retries):
        try:
            return await asyncio.to_thread(fn)
        except Exception as e:
            last_exc = e
            err = str(e)
            is_conn = any(x in err for x in [
                "RemoteProtocolError", "Server disconnected",
                "ConnectionTerminated", "ConnectError", "ReadError",
            ])
            if is_conn and attempt < _retries - 1:
                wait = 0.5 * (attempt + 1)
                logger.warning(
                    f"Supabase connection error (attempt {attempt + 1}/{_retries}): {e} "
                    f"— retrying in {wait}s"
                )
                await asyncio.sleep(wait)
                continue
            raise
    raise last_exc  # Should never reach here
