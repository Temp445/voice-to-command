"""
ACE Voice Controller — Tab Registry  (v2 — targetId-based tracking)
=====================================================================
Single source of truth for multi-tab management.

Active-tab detection strategy (event-driven, no polling):
  • Chrome CDP ``Target.targetActivated`` fires within ~1ms of any tab switch.
    We now match by **targetId** (stable, Chrome-assigned) rather than by URL
    so SPA navigations, hash changes, and query-string changes never cause a
    missed match.
  • targetId ↔ Playwright Page mapping is maintained via a parallel
    ``_target_ids: dict[str, str]`` table (tab_id → targetId) that is
    populated at registration time by calling Target.getTargets.
  • Fallback: visibilityState + hasFocus scans remain in browser_engine.py
    as safety nets when CDP events are unavailable.

URL-matching is still used for:
  • Disk-recovery after server restart (no targetId available then)
  • The ``_on_target_activated`` callback when no targetId mapping exists yet
    (handles manually-opened tabs that weren't registered via ACE)
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
from urllib.parse import urlparse

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


def _urls_same_origin(u1: str, u2: str) -> bool:
    """True when u1 and u2 share the same scheme+host (SPA-safe)."""
    try:
        p1, p2 = urlparse(u1.lower()), urlparse(u2.lower())
        return p1.netloc == p2.netloc and bool(p1.netloc)
    except Exception:
        return False


def _urls_match_exact(u1: str, u2: str) -> bool:
    return u1.lower().rstrip('/') == u2.lower().rstrip('/')


def _urls_match(u1: str, u2: str) -> bool:
    """
    Two-tier URL matching:
      1. Exact match (after stripping trailing slash)
      2. Same-origin match — handles SPA navigation where path/query changes
         but the tab is still the same site.
    Used only as a fallback when targetId mapping is unavailable.
    """
    if _urls_match_exact(u1, u2):
        return True
    return _urls_same_origin(u1, u2)


# ── Registry ──────────────────────────────────────────────────────────────────

class TabRegistry:
    """
    Singleton registry mapping every open Playwright Page to a stable UUID,
    with a parallel targetId table for reliable CDP event routing.

    Thread-safety: mutations protected by threading.RLock so the registry is
    safe to call from the Playwright event loop AND from FastAPI's asyncio thread.
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
        self._pages: dict[str, object] = {}          # tab_id → Page
        self._ids: dict[int, str] = {}               # id(page) → tab_id
        self._target_ids: dict[str, str] = {}        # tab_id → CDP targetId
        self._target_to_tab: dict[str, str] = {}     # CDP targetId → tab_id
        self._active_tab_id: str | None = None
        self._mu = threading.RLock()
        self._cdp_session = None
        self._persisted = _load_persisted_state()

    # ── Registration ──────────────────────────────────────────────────────────

    def register(self, page, target_id: str | None = None) -> str:
        """
        Assign a stable tab_id to *page*.  Idempotent.
        *target_id* — Chrome CDP targetId — when provided, enables reliable
        event-driven tab tracking even after SPA navigations.
        """
        with self._mu:
            pid = id(page)
            if pid in self._ids:
                existing_tab_id = self._ids[pid]
                # Update targetId mapping even if already registered
                if target_id and target_id not in self._target_to_tab:
                    self._target_ids[existing_tab_id] = target_id
                    self._target_to_tab[target_id] = existing_tab_id
                return existing_tab_id

            tab_id = str(uuid.uuid4())
            self._pages[tab_id] = page
            self._ids[pid] = tab_id
            if target_id:
                self._target_ids[tab_id] = target_id
                self._target_to_tab[target_id] = tab_id

            logger.debug(
                f"TabRegistry: registered tab {tab_id[:8]}… "
                f"url={page.url!r} targetId={target_id or 'unknown'}"
            )

        try:
            page.on("close",  lambda p=page: self._on_page_closed(p))
            page.on("crash",  lambda p=page: self._on_page_crashed(p))
        except Exception as e:
            logger.debug(f"TabRegistry: could not attach page events: {e}")

        # Async seed target ID if not provided and loop is running
        if not target_id:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.ensure_future(self._seed_single_target_id_from_page(page), loop=loop)
            except Exception:
                pass

        return tab_id

    async def _seed_single_target_id_from_page(self, page) -> None:
        try:
            if page.is_closed() or not page.context:
                return
            # We wait a brief moment for the page to be ready
            await asyncio.sleep(0.1)
            page_cdp = await page.context.new_cdp_session(page)
            t_id = None
            if hasattr(page_cdp, "_impl_obj") and hasattr(page_cdp._impl_obj, "_guid"):
                guid = page_cdp._impl_obj._guid
                if "@" in guid:
                    t_id = guid.split("@")[-1]
            try:
                await page_cdp.detach()
            except Exception:
                pass
            if t_id:
                with self._mu:
                    tab_id = self._ids.get(id(page))
                    if tab_id:
                        self._target_ids[tab_id] = t_id
                        self._target_to_tab[t_id] = tab_id
                        logger.debug(f"TabRegistry: direct-seeded targetId for page {tab_id[:8]}… ↔ {t_id[:8]}…")
        except Exception as e:
            logger.debug(f"TabRegistry: direct targetId seeding failed: {e}")


    def unregister(self, page) -> None:
        with self._mu:
            pid = id(page)
            tab_id = self._ids.pop(pid, None)
            if tab_id:
                self._pages.pop(tab_id, None)
                t_id = self._target_ids.pop(tab_id, None)
                if t_id:
                    self._target_to_tab.pop(t_id, None)
                logger.debug(f"TabRegistry: unregistered tab {tab_id[:8]}…")
                if self._active_tab_id == tab_id:
                    fallback_id = self._pick_fallback_tab_id()
                    if fallback_id:
                        fallback_page = self._pages.get(fallback_id)
                        if fallback_page:
                            self.set_active(fallback_page, source="unregister_fallback")
                    else:
                        self._active_tab_id = None

    # ── Active tab management ─────────────────────────────────────────────────

    def set_active(self, page, source="unknown") -> str | None:
        tab_id = self.get_tab_id(page)
        if not tab_id:
            tab_id = self.register(page)

        with self._mu:
            changed_id = self._active_tab_id != tab_id
            self._active_tab_id = tab_id
            last_url = self._persisted.get("active_url") if self._persisted else None

        try:
            url = page.url
        except Exception:
            url = ""

        changed_url = (url != last_url)

        if (changed_id or changed_url) and url:
            try:
                logger.info(f"TabRegistry: active tab update (source={source}) → {tab_id[:8]}… url={url!r}")
                self._persist(tab_id, url)

                # Resolve title and broadcast asynchronously to avoid coroutine bugs
                async def _fetch_title_and_broadcast():
                    try:
                        title = await page.title()
                    except Exception:
                        title = ""
                    if not title:
                        from urllib.parse import urlparse
                        try:
                            title = urlparse(url).netloc or url
                        except Exception:
                            title = url

                    from app.websocket.manager import ws_manager
                    payload = {"tab_id": tab_id, "url": url, "title": title}
                    await ws_manager.broadcast("tab_changed", payload)

                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        asyncio.run_coroutine_threadsafe(_fetch_title_and_broadcast(), loop)
                    else:
                        from urllib.parse import urlparse
                        domain = urlparse(url).netloc or url
                        self._broadcast_tab_changed(tab_id, url, domain)
                except Exception:
                    from urllib.parse import urlparse
                    domain = urlparse(url).netloc or url
                    self._broadcast_tab_changed(tab_id, url, domain)
            except Exception as e:
                logger.debug(f"TabRegistry.set_active broadcast/persist error: {e}")

        return tab_id

    def set_active_by_target_id(self, target_id: str, source="unknown") -> bool:
        """
        Called directly from the CDP ``Target.targetActivated`` handler with
        the raw Chrome targetId.  Returns True if the target was known.
        """
        with self._mu:
            tab_id = self._target_to_tab.get(target_id)

        if not tab_id:
            return False  # Unknown target — caller will fall back to URL scan

        with self._mu:
            page = self._pages.get(tab_id)

        if not page:
            return False

        try:
            if page.is_closed():
                self.unregister(page)
                return False
        except Exception:
            return False

        # Only update if actually changed (avoids redundant log + WebSocket noise)
        with self._mu:
            if self._active_tab_id == tab_id:
                return True  # Already correct — no-op

        self.set_active(page, source=source)
        return True

    def get_active(self) -> object | None:
        with self._mu:
            tab_id = self._active_tab_id
            if not tab_id:
                return None
            page = self._pages.get(tab_id)

        if page is None:
            return None

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
                    title="",
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
        saved_url = self._persisted.get("active_url", "")
        saved_tab_id = self._persisted.get("active_tab_id", "")
        if not saved_url:
            return None

        # Pass 1: exact URL match
        for page in pages:
            try:
                if _urls_match_exact(page.url, saved_url):
                    self.set_active(page, source="disk_recovery_exact")
                    logger.info(f"TabRegistry: recovered active tab (exact url) → {saved_url!r}")
                    return page
            except Exception:
                continue

        # Pass 2: same-origin match (handles SPA hash/path changes)
        for page in pages:
            try:
                if _urls_same_origin(page.url, saved_url):
                    self.set_active(page, source="disk_recovery_origin")
                    logger.info(f"TabRegistry: recovered active tab (origin match) → {page.url!r}")
                    return page
            except Exception:
                continue

        return None

    # ── CDP event wiring ──────────────────────────────────────────────────────

    async def wire_cdp_session(self, context) -> None:
        """
        Subscribe to Chrome CDP ``Target.targetActivated`` for instant tab-switch
        detection.  Uses targetId (not URL) so SPA navigations never break matching.

        Also populates targetId mappings for all currently registered pages by
        calling ``Target.getTargets`` once at wire time.
        """
        try:
            pages = [p for p in context.pages if not p.is_closed()]
            if not pages:
                logger.debug("TabRegistry: no pages available for CDP session")
                return

            # Establish browser-level CDP session for stable, browser-wide events
            browser = getattr(context, "browser", None)
            if browser and hasattr(browser, "new_browser_cdp_session"):
                cdp = await browser.new_browser_cdp_session()
                logger.info("TabRegistry: established browser-level CDP session")
            else:
                anchor = pages[-1] if len(pages) > 1 else pages[0]
                cdp = await context.new_cdp_session(anchor)
                logger.info("TabRegistry: established page-level CDP session (fallback)")
            self._cdp_session = cdp

            # Enable target discovery so activatedTarget events flow
            await cdp.send("Target.setDiscoverTargets", {"discover": True})

            # ── CDP event handler ─────────────────────────────────────────────
            def _on_target_activated(event: dict) -> None:
                # 1. Target.targetActivated parameters contain only 'targetId'.
                # In case other CDP versions pass targetInfo wrapper, check both.
                target_id = event.get("targetId")
                if not target_id:
                    target_info = event.get("targetInfo", {})
                    target_id = target_info.get("targetId", "")

                if not target_id:
                    return

                # Fast path: targetId is already mapped → O(1) lookup
                if self.set_active_by_target_id(target_id, source="cdp_target_activated"):
                    return

                # Slow path: targetId not yet mapped (manually-opened tab or late registration).
                # Since the event parameters do not include targetInfo/url, we must
                # query Target.getTargetInfo asynchronously to find the URL.
                if self._cdp_session:
                    async def _resolve_and_activate():
                        try:
                            res = await self._cdp_session.send("Target.getTargetInfo", {"targetId": target_id})
                            t_info = res.get("targetInfo", {})
                            if t_info.get("type") == "page":
                                t_url = t_info.get("url", "")
                                if t_url:
                                    with self._mu:
                                        matching_tab_ids = []
                                        items = list(self._pages.items())
                                        for tab_id, page in items:
                                            if not page.is_closed() and _urls_match(page.url, t_url):
                                                matching_tab_ids.append(tab_id)
                                        
                                        if len(matching_tab_ids) == 1:
                                            t_id = matching_tab_ids[0]
                                            self._target_ids[t_id] = target_id
                                            self._target_to_tab[target_id] = t_id
                                            logger.debug(
                                                f"TabRegistry: unique URL-matched activatedTarget fallback "
                                                f"{t_id[:8]}… {t_url!r}"
                                            )
                                            page_to_activate = self._pages.get(t_id)
                                        else:
                                            page_to_activate = None
                                            if len(matching_tab_ids) > 1:
                                                logger.debug(
                                                    f"TabRegistry: activatedTarget fallback matched multiple pages "
                                                    f"for {t_url!r}, skipping auto-map to avoid collision"
                                                )
                                    
                                    if page_to_activate:
                                        self.set_active(page_to_activate, source="cdp_target_activated_fallback")
                        except Exception as ex:
                            logger.debug(f"TabRegistry: fallback URL activation failed: {ex}")

                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            asyncio.ensure_future(_resolve_and_activate(), loop=loop)
                    except Exception:
                        pass

            # ── CDP Target Info Changed Handler ───────────────────────────────
            def _on_target_info_changed(event: dict) -> None:
                target_info = event.get("targetInfo", {})
                if target_info.get("type") != "page":
                    return

                target_id = target_info.get("targetId", "")
                target_url = target_info.get("url", "")
                target_title = target_info.get("title", "")
                if not target_id or not target_url or target_url.lower() in ("about:blank", ""):
                    return

                with self._mu:
                    tab_id = self._target_to_tab.get(target_id)
                    is_active = (self._active_tab_id == tab_id) if tab_id else False
                    last_url = self._persisted.get("active_url") if self._persisted else None

                if tab_id:
                    # If this is the active tab and the URL has navigated/changed, propagate it.
                    if is_active and target_url != last_url:
                        logger.info(f"TabRegistry: active tab URL updated via CDP → url={target_url!r}")
                        self._persist(tab_id, target_url)
                        self._broadcast_tab_changed(tab_id, target_url, target_title)
                    return

                # Match this targetId to a registered Playwright page by URL matching
                # Safety fallback only if target_id is not already mapped
                # AND there is exactly one registered page whose URL matches target_url.
                # If multiple pages match the URL, do NOT auto-map to avoid collision.
                with self._mu:
                    matching_tab_ids = []
                    items = list(self._pages.items())
                    for t_id, page in items:
                        try:
                            if not page.is_closed() and _urls_match(page.url, target_url):
                                matching_tab_ids.append(t_id)
                        except Exception:
                            continue
                    
                    if len(matching_tab_ids) == 1:
                        t_id = matching_tab_ids[0]
                        self._target_ids[t_id] = target_id
                        self._target_to_tab[target_id] = t_id
                        logger.debug(
                            f"TabRegistry: unique URL-matched targetInfoChanged fallback "
                            f"{t_id[:8]}… {target_url!r}"
                        )
                        is_now_active = (self._active_tab_id == t_id)
                        if is_now_active:
                            self._persist(t_id, target_url)
                            self._broadcast_tab_changed(t_id, target_url, target_title)
                    elif len(matching_tab_ids) > 1:
                        logger.debug(
                            f"TabRegistry: targetInfoChanged matched multiple pages "
                            f"for {target_url!r}, skipping auto-map to avoid collision"
                        )

            # ── New page handler ──────────────────────────────────────────────
            def _on_new_page_in_context(page) -> None:
                """Auto-register new pages and seed their targetId."""
                self.register(page)

            try:
                context.on("page", _on_new_page_in_context)
            except Exception:
                pass  # context may not support additional "page" listeners

            cdp.on("Target.targetActivated", _on_target_activated)
            cdp.on("Target.targetCreated", _on_target_info_changed)
            cdp.on("Target.targetInfoChanged", _on_target_info_changed)
            logger.info("✅ TabRegistry: CDP Target event handlers subscribed")

            # ── Seed targetId mapping ─────────────────────────────────────────
            # Direct-seed targetId for all open pages in parallel background tasks
            async def _seed_page(p):
                try:
                    tab_id = self.get_tab_id(p)
                    if not tab_id:
                        tab_id = self.register(p)
                    
                    page_cdp = await context.new_cdp_session(p)
                    t_id = None
                    if hasattr(page_cdp, "_impl_obj") and hasattr(page_cdp._impl_obj, "_guid"):
                        guid = page_cdp._impl_obj._guid
                        if "@" in guid:
                            t_id = guid.split("@")[-1]
                    try:
                        await page_cdp.detach()
                    except Exception:
                        pass
                    if t_id:
                        with self._mu:
                            self._target_ids[tab_id] = t_id
                            self._target_to_tab[t_id] = tab_id
                            logger.debug(f"TabRegistry: wired seed targetId for page {tab_id[:8]}… ↔ {t_id[:8]}…")
                except Exception as p_err:
                    logger.debug(f"TabRegistry: seeding for page failed: {p_err}")

            for p in pages:
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        asyncio.ensure_future(_seed_page(p), loop=loop)
                except Exception:
                    pass

        except Exception as e:
            logger.warning(
                f"TabRegistry: CDP session unavailable "
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
        for tab_id, page in reversed(list(self._pages.items())):
            try:
                if not page.is_closed():
                    return tab_id
            except Exception:
                continue
        return None

    def _get_fallback_page(self) -> object | None:
        with self._mu:
            items = list(self._pages.items())
        for tab_id, page in reversed(items):
            try:
                if not page.is_closed():
                    self.set_active(page, source="get_fallback_page")
                    return page
            except Exception:
                continue
        return None

    def _persist(self, tab_id: str, url: str) -> None:
        state = {"active_tab_id": tab_id, "active_url": url, "saved_at": time.time()}
        self._persisted = state
        _save_persisted_state(state)

    def _broadcast_tab_changed(self, tab_id: str, url: str, title: str) -> None:
        try:
            from app.websocket.manager import ws_manager
            import asyncio as _a

            payload = {"tab_id": tab_id, "url": url, "title": title}
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
                pass
        except Exception as e:
            logger.debug(f"TabRegistry: tab_changed broadcast error: {e}")


# ── Singleton ─────────────────────────────────────────────────────────────────

tab_registry = TabRegistry()