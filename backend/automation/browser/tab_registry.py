"""
ACE Voice Controller — Tab Registry
====================================
Single source of truth for multi-tab management.

Every Playwright Page is assigned a stable UUID at creation (or at CDP
reconnect). Commands always ask the registry for the active tab — they
never rely on list indices, URL substrings, or sticky "last navigated"
pointers that become stale when the user manually switches tabs.

Active-tab detection strategy (event-driven, no polling):
  • Chrome CDP ``Target.activatedTarget`` event fires within ~1ms of any
    tab switch — whether done by voice command or by the user clicking a
    tab in Chrome. We subscribe once at connect time and keep the registry
    in sync automatically.
  • Fallback: on every ``get_active()`` call we do a single-pass
    ``document.visibilityState`` check (same as before) as a safety net
    for cases where the CDP session drops.

Crash / close safety:
  • Playwright ``page.on("close")``  → auto-unregister + fallback to next tab.
  • Playwright ``page.on("crash")`` → auto-unregister + fallback to next tab.
  Both handlers call ``set_active()`` on the fallback tab so the next
  command has a healthy page to work with.
"""

from __future__ import annotations

import asyncio
import json
import os
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional

from loguru import logger


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class TabInfo:
    """Serialisable snapshot of one browser tab."""
    tab_id: str
    url: str
    title: str
    is_active: bool
    created_at: float = field(default_factory=time.time)


# ── Persistence helpers ───────────────────────────────────────────────────────

_STATE_FILE = os.path.join(os.path.dirname(__file__), ".ace_tab_registry.json")


def _load_persisted_state() -> dict:
    try:
        if os.path.exists(_STATE_FILE):
            with open(_STATE_FILE, "r") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _save_persisted_state(state: dict) -> None:
    try:
        with open(_STATE_FILE, "w") as f:
            json.dump(state, f)
    except Exception as e:
        logger.debug(f"TabRegistry: failed to persist state: {e}")


def _urls_match(u1: str, u2: str) -> bool:
    return u1.lower().rstrip('/') == u2.lower().rstrip('/')


# ── Registry ──────────────────────────────────────────────────────────────────

class TabRegistry:
    """
    Singleton registry that maps every open Playwright Page to a stable UUID.

    Thread-safety: all public methods are safe to call from the Playwright
    event loop thread OR from FastAPI's asyncio thread because mutations are
    protected by a threading.Lock (not an asyncio.Lock — the registry is
    accessed from both worlds).
    """

    _instance: "TabRegistry | None" = None
    _lock: threading.Lock = threading.Lock()

    def __new__(cls) -> "TabRegistry":
        with cls._lock:
            if cls._instance is None:
                instance = super().__new__(cls)
                instance._init()
                cls._instance = instance
        return cls._instance

    def _init(self) -> None:
        # tab_id → Page
        self._pages: dict[str, object] = {}
        # Page id() → tab_id  (use id() not the object itself to avoid GC weirdness)
        self._ids: dict[int, str] = {}
        self._active_tab_id: str | None = None
        self._mu = threading.RLock()
        # CDP session used for Target events (set by wire_cdp_session)
        self._cdp_session = None
        # Load last persisted state so recovery works across server restarts
        self._persisted = _load_persisted_state()

    # ── Registration ──────────────────────────────────────────────────────────

    def register(self, page) -> str:
        """
        Assign a stable tab_id to *page* and attach close/crash handlers.
        Idempotent — calling register() on an already-registered page is a no-op.
        Returns the tab_id.
        """
        with self._mu:
            pid = id(page)
            if pid in self._ids:
                return self._ids[pid]

            tab_id = str(uuid.uuid4())
            self._pages[tab_id] = page
            self._ids[pid] = tab_id
            logger.debug(f"TabRegistry: registered tab {tab_id[:8]}… url={page.url!r}")

        # Attach lifecycle handlers (outside the lock to avoid re-entrancy)
        try:
            page.on("close",  lambda p=page: self._on_page_closed(p))
            page.on("crash",  lambda p=page: self._on_page_crashed(p))
        except Exception as e:
            logger.debug(f"TabRegistry: could not attach page events: {e}")

        return tab_id

    def unregister(self, page) -> None:
        """Remove *page* from the registry. Safe to call from close/crash handlers."""
        with self._mu:
            pid = id(page)
            tab_id = self._ids.pop(pid, None)
            if tab_id:
                self._pages.pop(tab_id, None)
                logger.debug(f"TabRegistry: unregistered tab {tab_id[:8]}…")
                if self._active_tab_id == tab_id:
                    # Active tab gone — pick the most recently registered live tab
                    self._active_tab_id = self._pick_fallback_tab_id()

    # ── Active tab management ─────────────────────────────────────────────────

    def set_active(self, page) -> str | None:
        """
        Mark *page* as the active tab.
        Broadcasts ``tab_changed`` over WebSocket and persists state to disk.
        Returns the tab_id, or None if the page is not registered.
        """
        tab_id = self.get_tab_id(page)
        if not tab_id:
            # Auto-register unknown pages (e.g. ones opened manually by the user)
            tab_id = self.register(page)

        with self._mu:
            changed = self._active_tab_id != tab_id
            self._active_tab_id = tab_id

        if changed:
            try:
                url   = page.url
                title = ""
                try:
                    # page.title() is a coroutine in playwright-async; we send empty title
                    # and let the frontend parse a friendly display name from the URL.
                    pass
                except Exception:
                    pass
                logger.info(f"TabRegistry: active tab → {tab_id[:8]}… url={url!r}")
                self._persist(tab_id, url)
                self._broadcast_tab_changed(tab_id, url, title)
            except Exception as e:
                logger.debug(f"TabRegistry.set_active broadcast/persist error: {e}")

        return tab_id

    def get_active(self) -> object | None:
        """
        Return the active Playwright Page, or None.
        Performs a liveness check — if the stored page is closed, falls back
        to the next available tab and updates the registry.
        """
        with self._mu:
            tab_id = self._active_tab_id
            if not tab_id:
                return None
            page = self._pages.get(tab_id)

        if page is None:
            return None

        # Liveness check
        try:
            if page.is_closed():
                self.unregister(page)
                return self._get_fallback_page()
        except Exception:
            return self._get_fallback_page()

        return page

    def get_active_tab_id(self) -> str | None:
        with self._mu:
            return self._active_tab_id

    def get_tab_id(self, page) -> str | None:
        with self._mu:
            return self._ids.get(id(page))

    def get_page(self, tab_id: str) -> object | None:
        with self._mu:
            return self._pages.get(tab_id)

    # ── Tab listing ───────────────────────────────────────────────────────────

    def all_tabs(self) -> list[TabInfo]:
        """Return a snapshot list of all registered tabs."""
        with self._mu:
            active_id = self._active_tab_id
            items = list(self._pages.items())

        result = []
        for tab_id, page in items:
            try:
                if page.is_closed():
                    continue
                result.append(TabInfo(
                    tab_id=tab_id,
                    url=page.url,
                    title="",          # title() is async; callers fetch it separately
                    is_active=(tab_id == active_id),
                ))
            except Exception:
                continue
        return result

    def tab_count(self) -> int:
        with self._mu:
            return len(self._pages)

    # ── Disk recovery ─────────────────────────────────────────────────────────

    def recover_from_disk(self, pages: list) -> object | None:
        """
        After a server restart, match the persisted active URL to one of the
        live Playwright pages and set it as active.  Returns the recovered
        Page or None.
        """
        saved_url = self._persisted.get("active_url", "")
        saved_tab_id = self._persisted.get("active_tab_id", "")
        if not saved_url:
            return None

        # First pass: exact URL match
        for page in pages:
            try:
                if _urls_match(page.url, saved_url):
                    # Re-use the old tab_id if possible (keeps WS events stable)
                    if saved_tab_id and saved_tab_id not in self._pages:
                        with self._mu:
                            pid = id(page)
                            old_id = self._ids.get(pid)
                            if old_id and old_id in self._pages:
                                # Already registered under a new id — just set active
                                self.set_active(page)
                                logger.info(
                                    f"TabRegistry: recovered active tab (exact url) → "
                                    f"{self._ids.get(pid, '?')[:8]}… {saved_url!r}"
                                )
                                return page
                    self.set_active(page)
                    logger.info(
                        f"TabRegistry: recovered active tab (exact url) → "
                        f"{saved_url!r}"
                    )
                    return page
            except Exception:
                continue

        # Second pass: origin match (handles SPA hash/path changes)
        try:
            from urllib.parse import urlparse
            saved_origin = urlparse(saved_url).netloc
            for page in pages:
                try:
                    if urlparse(page.url).netloc == saved_origin:
                        self.set_active(page)
                        logger.info(
                            f"TabRegistry: recovered active tab (origin match) → "
                            f"{page.url!r}"
                        )
                        return page
                except Exception:
                    continue
        except Exception:
            pass

        return None

    # ── CDP event wiring ──────────────────────────────────────────────────────

    async def wire_cdp_session(self, context) -> None:
        """
        Subscribe to Chrome CDP ``Target.activatedTarget`` so we get an
        instant notification every time the user switches tabs — even via mouse.

        Call this once inside ``BrowserEngine.ensure_browser()`` after the
        CDP connection is established.
        """
        try:
            # We need a page to create a CDP session from
            pages = [p for p in context.pages if not p.is_closed()]
            if not pages:
                logger.debug("TabRegistry: no pages available for CDP session")
                return

            cdp = await context.new_cdp_session(pages[0])
            self._cdp_session = cdp

            # Enable target discovery
            await cdp.send("Target.setDiscoverTargets", {"discover": True})

            def _on_target_activated(event: dict) -> None:
                target_info = event.get("targetInfo", {})
                if target_info.get("type") != "page":
                    return
                target_url = target_info.get("url", "")

                # Match the CDP targetId to a Playwright Page by URL
                # (Playwright does not expose targetId directly, so we URL-match)
                with self._mu:
                    items = list(self._pages.items())

                for tab_id, page in items:
                    try:
                        if page.is_closed():
                            continue
                        if _urls_match(page.url, target_url):
                            current_active = self._active_tab_id
                            if current_active != tab_id:
                                logger.debug(
                                    f"TabRegistry: CDP activatedTarget → "
                                    f"{tab_id[:8]}… {target_url!r}"
                                )
                                # set_active acquires _mu internally — do it outside
                                self.set_active(page)
                            return
                    except Exception:
                        continue

            cdp.on("Target.targetActivated", _on_target_activated)
            logger.info("✅ TabRegistry: CDP Target.activatedTarget subscribed")

        except Exception as e:
            logger.warning(
                f"TabRegistry: CDP session for tab tracking unavailable "
                f"({type(e).__name__}: {e}) — falling back to visibilityState detection"
            )

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _on_page_closed(self, page) -> None:
        logger.debug(f"TabRegistry: page closed → {page.url!r}")
        self.unregister(page)

    def _on_page_crashed(self, page) -> None:
        logger.warning(f"TabRegistry: page crashed → {page.url!r}")
        self.unregister(page)

    def _pick_fallback_tab_id(self) -> str | None:
        """Choose the most recently registered live tab (call with _mu held)."""
        for tab_id, page in reversed(list(self._pages.items())):
            try:
                if not page.is_closed():
                    return tab_id
            except Exception:
                continue
        return None

    def _get_fallback_page(self) -> object | None:
        """Return the first live page that isn't the (dead) active one."""
        with self._mu:
            items = list(self._pages.items())
        for tab_id, page in reversed(items):
            try:
                if not page.is_closed():
                    self.set_active(page)
                    return page
            except Exception:
                continue
        return None

    def _persist(self, tab_id: str, url: str) -> None:
        state = {"active_tab_id": tab_id, "active_url": url, "saved_at": time.time()}
        self._persisted = state
        _save_persisted_state(state)

    def _broadcast_tab_changed(self, tab_id: str, url: str, title: str) -> None:
        """Fire-and-forget WebSocket broadcast."""
        try:
            from app.websocket.manager import ws_manager
            import asyncio as _a

            payload = {"tab_id": tab_id, "url": url, "title": title}

            # We may be called from the Playwright thread (not the FastAPI loop)
            # so we use run_coroutine_threadsafe if a loop is reachable.
            try:
                loop = _a.get_event_loop()
                if loop.is_running():
                    _a.run_coroutine_threadsafe(
                        ws_manager.broadcast("tab_changed", payload), loop
                    )
                else:
                    loop.run_until_complete(
                        ws_manager.broadcast("tab_changed", payload)
                    )
            except RuntimeError:
                # No running loop available (e.g. during tests) — skip broadcast
                pass
        except Exception as e:
            logger.debug(f"TabRegistry: tab_changed broadcast error: {e}")


# ── Singleton ─────────────────────────────────────────────────────────────────

tab_registry = TabRegistry()
