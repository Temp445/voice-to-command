"""
Browser Engine — Enterprise web automation using Playwright.

Lifecycle model (v2 — Detached Chrome):
  Chrome is launched as an INDEPENDENT process (not a child of Python) via subprocess.
  Playwright connects to it via CDP (port 9222). When the backend restarts/reloads,
  Chrome stays alive and the next ensure_browser() call reconnects via CDP instantly.
  This eliminates the 15-30s cold-start on every server reload.
"""

import asyncio
import os
import subprocess
import sys
import threading
import random
import time
from pathlib import Path
from loguru import logger
from playwright.async_api import async_playwright, BrowserContext, Page
from app.config import settings

# Dedicated Playwright event loop for thread safety with FastAPI
_playwright_loop = None

def _get_playwright_loop():
    global _playwright_loop
    if _playwright_loop is None:
        if sys.platform == 'win32':
            _playwright_loop = asyncio.ProactorEventLoop()
        else:
            _playwright_loop = asyncio.new_event_loop()
        t = threading.Thread(target=_playwright_loop.run_forever, daemon=True, name="BrowserThread")
        t.start()
    return _playwright_loop

async def _run_in_playwright(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop is _get_playwright_loop():
        return await coro
    future = asyncio.run_coroutine_threadsafe(coro, _get_playwright_loop())
    try:
        return await asyncio.wrap_future(future)
    except PermissionError:
        raise  # let caller handle restriction errors with a friendly message

# Realistic user agent — prevents "HeadlessChrome" fingerprint leaking
STANDARD_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)

# Chrome args for the detached subprocess launch
_SUBPROCESS_CHROME_ARGS = [
    "--remote-debugging-port=9222",
    "--disable-blink-features=AutomationControlled",
    "--no-first-run",
    "--no-default-browser-check",
    "--test-type",
    "--disable-features=PasswordManager,IsolateOrigins,site-per-process",
    "--disable-ipc-flooding-protection",
    "--disable-session-crashed-bubble",
    "--start-maximized",
    "--password-store=basic",
    "--disable-save-password-bubble",
    "--flag-switches-begin",
    "--flag-switches-end",
]

# Playwright context args (used when connect_over_cdp returns a context without args)
CHROME_ARGS = _SUBPROCESS_CHROME_ARGS


def _find_chrome_executable() -> str | None:
    """Locate the system Chrome/Chromium executable."""
    if sys.platform == "win32":
        candidates = [
            os.path.expandvars(r"%PROGRAMFILES%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%PROGRAMFILES(X86)%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        ]
    elif sys.platform == "darwin":
        candidates = ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"]
    else:
        candidates = ["/usr/bin/google-chrome", "/usr/bin/chromium-browser", "/usr/bin/chromium"]

    for c in candidates:
        if os.path.exists(c):
            return c
    return None


def _is_chrome_running_on_debug_port(port: int = 9222) -> bool:
    """Check if a Chrome instance is already listening on the remote debugging port."""
    import socket
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.5):
            return True
    except OSError:
        return False


def _patch_chrome_preferences(profile_path: str) -> None:
    """Patch Chrome Preferences to disable password manager and 'Restore pages?' bubbles."""
    import json
    prefs_dir = os.path.join(profile_path, "Default")
    os.makedirs(prefs_dir, exist_ok=True)
    prefs_path = os.path.join(prefs_dir, "Preferences")
    
    prefs = {}
    if os.path.exists(prefs_path):
        try:
            with open(prefs_path, "r", encoding="utf-8") as f:
                prefs = json.load(f)
        except Exception as e:
            logger.debug(f"Failed to read Chrome preferences: {e}")
            
    if "profile" not in prefs:
        prefs["profile"] = {}
    prefs["profile"]["exit_type"] = "Normal"
    prefs["profile"]["exited_cleanly"] = True
    prefs["profile"]["password_manager_enabled"] = False
    
    prefs["credentials_enable_service"] = False
    
    try:
        with open(prefs_path, "w", encoding="utf-8") as f:
            json.dump(prefs, f)
        logger.info("✅ Patched Chrome preferences (disabled password manager/restore bubbles).")
    except Exception as e:
        logger.debug(f"Failed to write Chrome preferences: {e}")


def _launch_detached_chrome(profile_path: str, port: int = 9222) -> None:
    """
    Spawn Chrome as a fully DETACHED process — independent of the Python process tree.
    When the backend restarts, Chrome keeps running and we reconnect via CDP.
    """
    exe = _find_chrome_executable()
    if not exe:
        raise RuntimeError(
            "Google Chrome not found on this system. "
            "Install Chrome or set the CHROME_EXECUTABLE environment variable."
        )

    args = [
        exe,
        f"--user-data-dir={profile_path}",
        f"--remote-debugging-port={port}",
    ] + [
        a for a in _SUBPROCESS_CHROME_ARGS
        if not a.startswith("--remote-debugging-port")  # already added above
    ]

    if sys.platform == "win32":
        # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP ensures Chrome
        # is NOT in Python's process tree and survives server restarts.
        DETACHED_PROCESS = 0x00000008
        CREATE_NEW_PROCESS_GROUP = 0x00000200
        subprocess.Popen(
            args,
            creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP,
            close_fds=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    else:
        subprocess.Popen(
            args,
            start_new_session=True,   # POSIX equivalent of detached
            close_fds=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    logger.info(f"🚀 Detached Chrome launched (port {port}): {exe}")


class BrowserEngine:
    """Singleton engine for isolated, stealthy browser automation."""
    _instance = None
    _playwright = None
    _browser = None
    _context: BrowserContext | None = None
    _page: Page | None = None
    _lock = None
    # Short-lived cache for get_active_page() — avoids redundant CDP/JS calls
    # within a single command's execution pipeline (~80-150ms saved per call).
    # TTL reduced to 150ms (was 300ms) so a quick manual tab-switch between
    # two voice commands is reflected on the very next command.
    _active_page_cache: "tuple[float, Page] | None" = None
    _ACTIVE_PAGE_TTL: float = 0.15  # seconds (was 0.3 — reduced for tab-switch accuracy)
    # _last_navigated_page REMOVED — replaced by TabRegistry.get_active() which is
    # event-driven (CDP Target.activatedTarget) and never stale.
    _active_page_override = None
    _detector_task = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @staticmethod
    def _get_profile_path():
        if sys.platform == "win32":
            return os.path.expandvars(r"%LOCALAPPDATA%\ACE\BrowserProfile")
        elif sys.platform == "darwin":
            return os.path.expanduser("~/Library/Application Support/ACE/BrowserProfile")
        else:
            return os.path.expanduser("~/.config/ace/browser-profile")

    async def _apply_stealth(self, target):
        """Apply playwright-stealth to a context or page, handling both API versions."""
        try:
            try:
                from playwright_stealth import stealth_async
                await stealth_async(target)
            except ImportError:
                from playwright_stealth import Stealth
                stealth_instance = Stealth()
                await stealth_instance.apply_stealth_async(target)
        except Exception as e:
            logger.warning(f"Stealth could not be applied to target: {e}")

    async def _human_mouse_wiggle(self, page: Page):
        """Simulate natural mouse movement to build interaction entropy before actions."""
        for _ in range(random.randint(2, 4)):
            x = random.randint(200, 1200)
            y = random.randint(100, 600)
            await page.mouse.move(x, y, steps=random.randint(5, 10))
            await asyncio.sleep(random.uniform(0.02, 0.08))

    async def prewarm_profile(self):
        """
        Pre-warm: ensure a detached Chrome is already running before the first
        command arrives. If Chrome is already up (server hot-reload), this is a
        no-op and returns immediately.
        """
        async def _do():
            if not self._playwright:
                self._playwright = await async_playwright().start()

            profile_path = self._get_profile_path()
            os.makedirs(profile_path, exist_ok=True)

            # If Chrome is already running (surviving a server reload), do nothing.
            if _is_chrome_running_on_debug_port(9222):
                logger.info("✅ Chrome already running on port 9222 — pre-warm skipped (server reload detected).")
                return

            _patch_chrome_preferences(profile_path)

            try:
                _launch_detached_chrome(profile_path)
                # Wait up to 8s for Chrome to open its debug port
                for _ in range(16):
                    await asyncio.sleep(0.5)
                    if _is_chrome_running_on_debug_port(9222):
                        logger.info("✅ Detached Chrome is ready on port 9222.")
                        break
                else:
                    logger.warning("⚠️  Chrome did not open debug port in 8s — first command will be slow.")
            except Exception as e:
                logger.warning(f"⚠️  Detached Chrome launch failed during pre-warm: {e}")

        await _run_in_playwright(_do())

    def invalidate_active_page_cache(self) -> None:
        """Force the next get_active_page() call to do a fresh tab detection.
        Call this whenever a navigation or tab-switch occurs."""
        self._active_page_cache = None

    def pin_active_page(self, page: "Page", source: str = "unknown") -> None:
        """
        Mark *page* as the active tab in both the legacy ``_page`` slot and the
        new ``TabRegistry``.  Named ``pin_active_page`` for backward compatibility
        with callers across the codebase — internally it now delegates to the
        registry, which handles persistence and WebSocket broadcast.
        """
        self.invalidate_active_page_cache()
        self._page = page
        # Delegate to TabRegistry — it handles UUID assignment, disk persistence,
        # and the tab_changed WebSocket broadcast in one atomic call.
        try:
            from automation.browser.tab_registry import tab_registry
            tab_registry.set_active(page, source=source)
        except Exception as e:
            logger.debug(f"TabRegistry.set_active failed in pin_active_page: {e}")
        # Wipe page-context snapshot — it belongs to the old tab
        try:
            from app.services.page_context_service import page_context_service
            page_context_service.invalidate()
        except Exception:
            pass
        logger.debug(f"Active page pinned (TabRegistry, source={source}): {page.url}")

    def set_active_page_override(self, page: Page) -> None:
        self._active_page_override = page
        logger.debug(f"BrowserEngine: locked active page override to {page.url if page else 'None'}")

    def clear_active_page_override(self) -> None:
        self._active_page_override = None
        logger.debug("BrowserEngine: cleared active page override")

    def _is_shortcut_url(self, url: str) -> bool:
        """Returns True if url matches any configured crm_sites entry or global shortcut."""
        import json
        from urllib.parse import urlparse
        try:
            url_lower = url.lower().strip()
            if not url_lower or url_lower.startswith((
                "about:",
                "chrome:",
                "chrome-error:",
                "chrome-extension:",
                "chrome-search:",
                "chrome-untrusted:",
                "devtools:",
                "data:"
            )) or "chromewebdata" in url_lower or "localhost" in url_lower or "127.0.0.1" in url_lower or "new-tab-page" in url_lower or "newtab" in url_lower:
                return True

            # 1. Load user-specific shortcuts
            raw = getattr(settings, "crm_sites", "[]") or "[]"
            sites = json.loads(raw)
            if not isinstance(sites, list):
                sites = []

            # 2. Merge with global website shortcuts (from command_service cache if available)
            try:
                from app.services.command_service import command_service
                if hasattr(command_service, "_global_ws_sites") and command_service._global_ws_sites:
                    sites = list(sites) + list(command_service._global_ws_sites)
            except Exception as e:
                logger.debug(f"Could not load global shortcuts from command_service: {e}")

            if not sites:
                return False

            # Add protocol prefix if missing so urlparse extracts netloc correctly
            active_url = url_lower if url_lower.startswith(("http://", "https://")) else f"https://{url_lower}"
            active_host = urlparse(active_url).netloc.lower()

            # Whitelist Google search domains
            if active_host == "google.com" or active_host.endswith(".google.com"):
                return True

            for site in sites:
                site_url = site.get("url", "")
                if not site_url:
                    continue
                site_url_with_scheme = site_url.lower().strip()
                if not site_url_with_scheme.startswith(("http://", "https://")):
                    site_url_with_scheme = f"https://{site_url_with_scheme}"
                site_host = urlparse(site_url_with_scheme).netloc.lower()
                
                # Match on hostname (ignores path/query differences)
                if active_host and site_host and (
                    active_host == site_host or active_host.endswith("." + site_host)
                ):
                    return True
        except Exception:
            pass
        return False

    async def _animate_action(self, page: Page, target, action_type="click"):
        """Animate visual feedback (cursor, highlight, ripple) if enabled."""
        if not getattr(settings, "browser_animations_enabled", True):
            return
        try:
            # 1. Resolve bounding box
            box = None
            if isinstance(target, str):
                loc = page.locator(target).first
                if await loc.count() > 0:
                    box = await loc.bounding_box()
            elif hasattr(target, "bounding_box"):
                box = await target.bounding_box()
            elif isinstance(target, dict) and "x" in target and "y" in target:
                box = target
            
            if not box:
                return

            if "width" in box and "height" in box:
                x = box["x"] + box["width"] / 2
                y = box["y"] + box["height"] / 2
            else:
                x = box["x"]
                y = box["y"]

            # Ensure x and y are within viewport bounds
            viewport = page.viewport_size
            if viewport:
                x = min(max(0, x), viewport["width"])
                y = min(max(0, y), viewport["height"])

            js_script = """
            async (args) => {
                const { x, y, actionType } = args;
                let style = document.getElementById('ace-animations-style');
                if (!style) {
                    style = document.createElement('style');
                    style.id = 'ace-animations-style';
                    style.innerHTML = `
                        .ace-virtual-cursor {
                            position: fixed;
                            width: 18px;
                            height: 18px;
                            background-image: url("data:image/svg+xml,%3Csvg width='28' height='28' viewBox='0 0 28 28' xmlns='http://www.w3.org/2000/svg'%3E%3Cg transform='translate(0.9,0) scale(0.8,1)'%3E%3Cpath d='M11 6.1 C11 5 11.8 4.15 12.8 4.15 C13.8 4.15 14.6 5 14.6 6.1 L14.6 13.6 Q14.6 14.1 15.9 14.1 C15.9 14.1 15.9 11.55 15.9 10.85 C15.9 9.85 16.76 9.05 17.85 9.05 C18.94 9.05 19.8 9.85 19.8 10.85 C19.8 11.55 19.8 13.6 19.8 13.6 Q19.8 14.1 20.1 14.1 C20.1 14.1 20.1 12.15 20.1 11.55 C20.1 10.65 20.86 9.95 21.85 9.95 C22.84 9.95 23.6 10.65 23.6 11.55 C23.6 12.15 23.6 14 23.6 14 L23.6 14.1 Q23.6 14.4 23.95 14.5 C23.95 14.5 24 13.35 24 12.9 C24 12.05 24.65 11.4 25.5 11.4 C26.35 11.4 27 12.05 27 12.9 C27 13.35 27 14.6 27 15.4 L26.8 18.7 C26.8 22.5 24.2 26.2 20.75 26.2 C18.7 26.2 16.9 26.2 15.5 26.2 C13.6 26.2 12 25.1 11.2 23.6 L6.4 18.3 C5.5 17.05 5.6 16.1 6.5 15.35 C7.2 14.7 8.3 14.7 9 15.35 L11 17.3 L11 6.1 Z' fill='%23ffffff' stroke='%23000000' stroke-width='0.7' stroke-linejoin='round' stroke-linecap='round'/%3E%3C/g%3E%3C/svg%3E");
                            background-size: contain;
                            background-repeat: no-repeat;
                            pointer-events: none;
                            z-index: 10000000;
                            opacity: 0;
                            transition: opacity 0.3s ease, left 0.5s cubic-bezier(0.25, 1, 0.5, 1), top 0.5s cubic-bezier(0.25, 1, 0.5, 1);
                            filter: drop-shadow(0px 1px 2px rgba(0,0,0,0.4));
                        }
                        .ace-click-ripple {
                            position: fixed;
                            border: 3px solid rgba(0, 149, 255, 0.9);
                            border-radius: 50%;
                            pointer-events: none;
                            z-index: 10000000;
                            transform: translate(-50%, -50%);
                            animation: ace-ripple-ani 0.4s ease-out forwards;
                        }
                        .ace-element-highlight {
                            outline: 3px solid rgba(0, 149, 255, 0.9) !important;
                            outline-offset: 2px !important;
                            transition: outline 0.2s ease;
                        }
                        @keyframes ace-ripple-ani {
                            0% { width: 0px; height: 0px; opacity: 1; }
                            100% { width: 40px; height: 40px; opacity: 0; }
                        }
                    `;
                    document.head.appendChild(style);
                }
                let cursor = document.querySelector('.ace-virtual-cursor');
                if (!cursor) {
                    cursor = document.createElement('div');
                    cursor.className = 'ace-virtual-cursor';
                    cursor.style.left = x + 'px';
                    cursor.style.top = y + 'px';
                    document.body.appendChild(cursor);
                    cursor.offsetWidth;
                }
                const el = document.elementFromPoint(x, y);
                if (el) {
                    el.classList.add('ace-element-highlight');
                    setTimeout(() => el.classList.remove('ace-element-highlight'), 1000);
                }

                const actionId = Date.now().toString();
                cursor.dataset.lastActionId = actionId;
                cursor.style.opacity = '1';
                cursor.style.left = x + 'px';
                cursor.style.top = y + 'px';
                await new Promise(r => setTimeout(r, 500));
                if (actionType === 'click' || actionType === 'dblclick') {
                    const ripple = document.createElement('div');
                    ripple.className = 'ace-click-ripple';
                    ripple.style.left = x + 'px';
                    ripple.style.top = y + 'px';
                    document.body.appendChild(ripple);
                    setTimeout(() => ripple.remove(), 400);
                }
                
                setTimeout(() => {
                    if (cursor.dataset.lastActionId === actionId) {
                        cursor.style.opacity = '0';
                    }
                }, 1000);
            }
            """
            await page.evaluate(js_script, {"x": x, "y": y, "actionType": action_type})
        except Exception as e:
            logger.debug(f"Failed to show browser action animation: {e}")

    async def get_active_page(self, allow_restricted: bool = False, read_only: bool = False) -> Page:
        """Return the tab the user is currently looking at.

        Detection priority:
          0. Override active page (if set and not closed)
          1. TabRegistry (Event-driven CDP Target.targetActivated & REST sync loop)
          2. Fallback to last/first non-closed page in context
        """
        # ── Override layer ───────────────────────────────────────────────────
        if self._active_page_override is not None:
            if not self._active_page_override.is_closed():
                page = self._active_page_override
            else:
                self._active_page_override = None
                page = None
        else:
            page = None

        if page is None:
            # ── Cache layer ───────────────────────────────────────────────────────
            if self._active_page_cache is not None:
                ts, cached_page = self._active_page_cache
                if (time.time() - ts) < self._ACTIVE_PAGE_TTL and not cached_page.is_closed():
                    page = cached_page
                else:
                    self._active_page_cache = None  # expired or closed

        if page is None:
            async def _do_get_active():
                if not self._context or getattr(self._context, 'is_closed', lambda: True)():
                    return await self.ensure_browser()

                pages = [
                    p for p in self._context.pages
                    if not p.is_closed()
                    and not p.url.lower().startswith("chrome-extension://")
                    and p.url.lower() not in ("about:blank", "")
                    and "localhost:3000" not in p.url
                    and "127.0.0.1:3000" not in p.url
                ]

                if not pages:
                    return await self.ensure_browser()

                from automation.browser.tab_registry import tab_registry

                # Priority 1: Check TabRegistry active tab
                try:
                    reg_page = tab_registry.get_active()
                    if reg_page and not reg_page.is_closed() and reg_page in pages:
                        self._page = reg_page
                        return reg_page
                except Exception as e:
                    logger.debug(f"TabRegistry active lookup failed: {e}")

                # Priority 2: Last resort fallback (most recently opened or last page)
                fallback = pages[-1]
                self._page = fallback
                if tab_registry.get_active() is None:
                    self.pin_active_page(fallback, source="get_active_page_bootstrap_fallback")
                return fallback

            page = await _run_in_playwright(_do_get_active())
            if page and not page.is_closed():
                self._active_page_cache = (time.time(), page)

        if page and not allow_restricted and getattr(settings, "restrict_browser_automation", False):
            current_url = page.url
            if not self._is_shortcut_url(current_url):
                originated_from_search = False
                try:
                    referrer = await page.evaluate("document.referrer")
                    if referrer and isinstance(referrer, str) and self._is_shortcut_url(referrer):
                        originated_from_search = True
                except Exception as ref_err:
                    logger.debug(f"Failed to evaluate document.referrer: {ref_err}")

                if read_only and originated_from_search:
                    logger.debug(f"Permitting read-only action on restricted site {current_url} since it originated from whitelisted referrer {referrer}")
                    return page

                from urllib.parse import urlparse
                host = urlparse(current_url).netloc or current_url
                raise PermissionError(
                    f"Automation restricted. '{host}' is not in your shortcuts."
                )

        return page

    async def ensure_browser(self, background: bool = False) -> Page:
        """
        Connect to an already-running detached Chrome via CDP.
        If Chrome is not running yet, launch it as a detached subprocess first.
        """
        async def _do_ensure():
            if self._lock is None:
                self._lock = asyncio.Lock()
            async with self._lock:
                if self._context and not getattr(self._context, 'is_closed', lambda: True)():
                    if not self._page or self._page.is_closed():
                        pages = self._context.pages
                        self._page = pages[0] if pages else await self._context.new_page()
                    return self._page

                if not self._playwright:
                    self._playwright = await async_playwright().start()

                profile_path = self._get_profile_path()
                os.makedirs(profile_path, exist_ok=True)
                b_type = settings.browser_type.lower()

                # ── Firefox / WebKit: classic persistent context ──────────────
                if b_type == "firefox":
                    self._context = await self._playwright.firefox.launch_persistent_context(
                        user_data_dir=profile_path, headless=False, no_viewport=True,
                    )
                elif b_type == "webkit":
                    self._context = await self._playwright.webkit.launch_persistent_context(
                        user_data_dir=profile_path, headless=False, no_viewport=True,
                    )
                else:
                    # ── Chrome: detached subprocess + CDP ────────────────────
                    # Step 1: Ensure Chrome is running on port 9222
                    if not _is_chrome_running_on_debug_port(9222):
                        logger.info("Chrome not detected on port 9222 — launching detached process.")
                        try:
                            _patch_chrome_preferences(profile_path)
                            _launch_detached_chrome(profile_path)
                        except Exception as launch_err:
                            logger.error(f"Failed to launch Chrome: {launch_err}")
                            raise

                        # Wait up to 10s for Chrome's debug port to become ready
                        for _ in range(20):
                            await asyncio.sleep(0.5)
                            if _is_chrome_running_on_debug_port(9222):
                                break
                        else:
                            raise RuntimeError("Chrome launched but debug port 9222 never opened.")

                    # Step 2: Connect via CDP (fast, ~50ms)
                    logger.info("Connecting to Chrome via CDP on port 9222...")
                    try:
                        self._browser = await self._playwright.chromium.connect_over_cdp("http://localhost:9222")
                        self._context = self._browser.contexts[0] if self._browser.contexts else await self._browser.new_context()
                        logger.info("✅ Connected to Chrome via CDP.")
                    except Exception as cdp_err:
                        logger.error(f"CDP connection failed: {cdp_err}")
                        raise

                # ── Register all existing pages in TabRegistry ─────────────
                # This runs on every connect (cold start OR server hot-reload).
                try:
                    from automation.browser.tab_registry import tab_registry as _tr
                    _real_pages = [
                        p for p in self._context.pages
                        if not p.is_closed()
                        and not p.url.lower().startswith("chrome-extension://")
                        and p.url.lower() not in ("about:blank", "")
                    ]
                    # Seed targetId for all pages at connect time via Target.getTargets
                    _target_id_map: dict[str, str] = {}  # url → targetId
                    try:
                        _cdp_anchor = await self._context.new_cdp_session(_real_pages[0])
                        _tgt_result = await _cdp_anchor.send("Target.getTargets")
                        await _cdp_anchor.detach()
                        for _t in _tgt_result.get("targetInfos", []):
                            if _t.get("type") == "page" and _t.get("targetId"):
                                _target_id_map[_t.get("url", "").rstrip("/")] = _t["targetId"]
                    except Exception as _tid_err:
                        logger.debug(f"targetId pre-seed failed (non-fatal): {_tid_err}")

                    for _p in _real_pages:
                        _tid = _target_id_map.get(_p.url.rstrip("/"), None)
                        if not _tid:  # try origin match
                            from urllib.parse import urlparse as _uparse
                            _pn = _uparse(_p.url).netloc.lower()
                            for _u, _id in _target_id_map.items():
                                if _uparse(_u).netloc.lower() == _pn:
                                    _tid = _id
                                    break
                        _tr.register(_p, target_id=_tid)

                    # New-page hook: auto-register + async targetId seed
                    def _on_new_page(page):
                        _tr.register(page)  # wire_cdp_session seeds targetId async

                    self._context.on("page", _on_new_page)

                    # Recover last active tab from disk (survives server restarts)
                    recovered = _tr.recover_from_disk(_real_pages)
                    if not recovered and _real_pages:
                        _tr.set_active(_real_pages[-1], source="initial_tab_setup")

                    # Wire CDP Target.activatedTarget for instant tab-switch detection
                    asyncio.ensure_future(_tr.wire_cdp_session(self._context))





                    logger.info(
                        f"✅ TabRegistry: registered {len(_real_pages)} existing tab(s), "
                        f"active = {_tr.get_active_tab_id()}"
                    )
                except Exception as _tr_err:
                    logger.warning(f"TabRegistry init error (non-fatal): {_tr_err}")

                # ── Page selection (cold start) ────────────────────────────
                pages = self._context.pages
                self._page = pages[0] if pages else await self._context.new_page()
                return self._page

        return await _run_in_playwright(_do_ensure())

    async def close_browser(self):
        """
        Disconnect Playwright from Chrome WITHOUT killing the Chrome process.
        Chrome stays alive so the next server startup can reconnect in ~50ms.
        Call kill_browser() explicitly if you actually want to terminate Chrome.
        """


        async def _do_close():
            if self._lock is None:
                self._lock = asyncio.Lock()
            async with self._lock:
                if self._detector_task and not self._detector_task.done():
                    self._detector_task.cancel()
                    self._detector_task = None
                if self._browser:
                    try:
                        await self._browser.close()
                    except Exception:
                        pass
                self._browser = None
                self._context = None
                self._page = None
                if self._playwright:
                    await self._playwright.stop()
                    self._playwright = None
                logger.info("Playwright disconnected from Chrome (Chrome process still running).")
        await _run_in_playwright(_do_close())

    async def kill_browser(self):
        """Terminate the Chrome process entirely (use only when a full restart is needed)."""


        import psutil
        killed = False
        for proc in psutil.process_iter(['name', 'cmdline']):
            try:
                if proc.info['name'] and proc.info['name'].lower() in ('chrome.exe', 'chromium', 'chromium-browser'):
                    cmdline = proc.info.get('cmdline') or []
                    if any('--remote-debugging-port=9222' in str(a) for a in cmdline):
                        proc.terminate()
                        killed = True
                        logger.info(f"Terminated Chrome process PID {proc.pid}.")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        if self._browser:
            try:
                await self._browser.close()
            except Exception:
                pass
        self._browser = None
        self._context = None
        self._page = None
        if self._detector_task and not self._detector_task.done():
            self._detector_task.cancel()
            self._detector_task = None
        if self._playwright:
            async def _stop():
                await self._playwright.stop()
                self._playwright = None
            await _run_in_playwright(_stop())
        return "Chrome terminated." if killed else "No ACE Chrome process found to terminate."

    async def restart_browser(self):
        """Kill Chrome and relaunch it fresh."""
        await self.kill_browser()
        import asyncio as _a
        await _a.sleep(1.0)  # let the OS release the port
        await self.ensure_browser()
        return "Browser restarted."

    async def navigate(self, url: str, new_tab: bool = False) -> str:
        async def _do_nav():
            target = f"https://{url}" if not url.startswith(("http://", "https://")) else url

            if getattr(settings, "restrict_browser_automation", False) and not self._is_shortcut_url(target):
                from urllib.parse import urlparse
                host = urlparse(target).netloc or target
                raise PermissionError(
                    f"Automation restricted. '{host}' is not in your shortcuts."
                )

            await self.ensure_browser()

            # ── Tab-reuse: if target domain is already open, switch to that
            # tab instead of navigating the current one. This gives voice
            # commands the same multi-tab awareness as the command console.
            if not new_tab and self._context:
                from urllib.parse import urlparse as _up
                target_netloc = _up(target).netloc.lower()
                if target_netloc:
                    for _p in self._context.pages:
                        try:
                            if _p.is_closed():
                                continue
                            existing_netloc = _up(_p.url).netloc.lower()
                            if existing_netloc == target_netloc:
                                await _p.bring_to_front()
                                self.pin_active_page(_p)
                                try:
                                    from automation.browser.tab_registry import tab_registry as _tr
                                    _tr.set_active(_p, source="navigate_tab_reuse")
                                except Exception:
                                    pass
                                logger.info(f"navigate: reusing existing tab for {target_netloc}")
                                return f"Switched to existing tab: {target}"
                        except Exception:
                            continue

            if new_tab:
                if not self._context:
                    raise RuntimeError("Browser context not initialized.")
                new_page = await self._context.new_page()
                await self._apply_stealth(new_page)
                # Register in TabRegistry BEFORE pin so the UUID exists
                try:
                    from automation.browser.tab_registry import tab_registry as _tr
                    _tr.register(new_page)
                except Exception:
                    pass
                # Pin this new tab as the active page immediately so all follow-on
                # commands in the same pipeline target it — not the previous tab.
                self.pin_active_page(new_page)
                page = new_page
            else:
                page = await self.get_active_page(allow_restricted=True)

            # Bring to front and maximize BEFORE goto() to avoid main-thread block
            try:
                cdp = await page.context.new_cdp_session(page)
                res = await cdp.send("Browser.getWindowForTarget")
                window_id = res.get("windowId")
                if window_id:
                    await cdp.send("Browser.setWindowBounds", {
                        "windowId": window_id,
                        "bounds": {"windowState": "maximized"}
                    })
            except Exception as e:
                logger.debug(f"CDP maximize skipped: {e}")

            # Windows Focus Stealing Bypass
            try:
                import uuid
                import ctypes
                import pygetwindow as gw

                unique_title = str(uuid.uuid4())
                original_title = await page.evaluate("document.title")
                await page.evaluate(f"document.title = '{unique_title}'")
                await asyncio.sleep(0.1)

                wins = gw.getWindowsWithTitle(unique_title)
                if wins:
                    win = wins[0]
                    ctypes.windll.user32.keybd_event(0x12, 0, 0, 0)  # ALT down
                    ctypes.windll.user32.keybd_event(0x12, 0, 2, 0)  # ALT up
                    if win.isMinimized:
                        win.restore()
                    win.maximize()
                    ctypes.windll.user32.SetForegroundWindow(win._hWnd)

                await page.evaluate(f"document.title = '{original_title}'")
            except Exception as e:
                logger.debug(f"Focus bypass skipped: {e}")

            from playwright.async_api import TimeoutError as PlaywrightTimeoutError
            try:
                await page.goto(target, wait_until="commit", timeout=20000)
            except PlaywrightTimeoutError:
                logger.warning(f"Timeout (commit) navigating to {target}, retrying...")
                try:
                    await page.goto(target, wait_until="domcontentloaded", timeout=20000)
                except PlaywrightTimeoutError:
                    return f"Failed to load {target} — network timeout."

            try:
                await page.bring_to_front()
            except Exception as e:
                logger.debug(f"bring_to_front skipped: {e}")

            # Pin this tab as the active page — URL has changed and it's now in focus.
            # Using pin_active_page() rather than just invalidating ensures that
            # any command immediately following navigation targets this tab,
            # not whatever tab happens to answer visibilityState first.
            self.pin_active_page(page)
            return f"Navigated to {target}"
        return await _run_in_playwright(_do_nav())


    async def go_back(self) -> str:
        async def _do():
            page = await self.get_active_page(allow_restricted=True)
            await page.go_back()
            return "Navigated back."
        return await _run_in_playwright(_do())

    async def go_forward(self) -> str:
        async def _do():
            page = await self.get_active_page(allow_restricted=True)
            await page.go_forward()
            return "Navigated forward."
        return await _run_in_playwright(_do())

    async def refresh(self) -> str:
        async def _do():
            page = await self.get_active_page(allow_restricted=True)
            await page.reload()
            return "Page refreshed."
        return await _run_in_playwright(_do())

    async def get_url(self) -> str:
        async def _do():
            page = await self.get_active_page(allow_restricted=True)
            return page.url
        return await _run_in_playwright(_do())

    # --- Tabs ---
    async def new_tab(self, url: str | None = None) -> str:
        async def _do():
            await self.ensure_browser()
            new_page = await self._context.new_page()
            # Apply stealth to every new tab immediately
            await self._apply_stealth(new_page)
            # Register in TabRegistry BEFORE navigation so UUID is stable
            try:
                from automation.browser.tab_registry import tab_registry as _tr
                _tr.register(new_page)
            except Exception:
                pass
            if url:
                target = f"https://{url}" if not url.startswith(("http://", "https://")) else url
                await new_page.goto(target)
            # Pin the new tab as active (updates registry + broadcasts)
            self.pin_active_page(new_page)
            return "Opened new tab."
        return await _run_in_playwright(_do())

    async def close_tab(self) -> str:
        async def _do():
            page = await self.get_active_page(allow_restricted=True)
            # Unregister BEFORE close so crash-handler doesn't fire confusingly
            try:
                from automation.browser.tab_registry import tab_registry as _tr
                _tr.unregister(page)
            except Exception:
                pass
            await page.close()
            # Find next live tab from remaining pages
            live_pages = [
                p for p in self._context.pages
                if not p.is_closed()
                and not p.url.lower().startswith("chrome-extension://")
            ]
            if live_pages:
                self.pin_active_page(live_pages[-1])
            else:
                # No tabs left — open a blank tab so the engine stays healthy
                blank = await self._context.new_page()
                try:
                    from automation.browser.tab_registry import tab_registry as _tr
                    _tr.register(blank)
                except Exception:
                    pass
                self.invalidate_active_page_cache()
                self._page = blank
            return "Tab closed."
        return await _run_in_playwright(_do())

    async def close_all_tabs(self) -> str:
        async def _do():
            await self.ensure_browser()
            pages = list(self._context.pages)
            for p in pages:
                await p.close()
            self._page = await self._context.new_page()
            return "All tabs closed."
        return await _run_in_playwright(_do())

    async def get_all_tabs(self):
        async def _do():
            await self.ensure_browser()
            try:
                from automation.browser.tab_registry import tab_registry as _tr
                tab_infos = _tr.all_tabs()
                result = []
                for i, info in enumerate(tab_infos):
                    page = _tr.get_page(info.tab_id)
                    title = ""
                    if page:
                        try:
                            title = await page.title()
                        except Exception:
                            pass
                    result.append({
                        "index": i,
                        "tab_id": info.tab_id,
                        "title": title,
                        "url": info.url,
                        "is_active": info.is_active,
                    })
                return result
            except Exception:
                # Fallback to legacy approach if registry unavailable
                return [{"index": i, "tab_id": None, "title": await p.title(), "url": p.url, "is_active": False}
                        for i, p in enumerate(self._context.pages)]
        return await _run_in_playwright(_do())

    async def switch_tab(self, index: int) -> str:
        async def _do():
            await self.ensure_browser()
            # Build the list from the registry so index is stable
            try:
                from automation.browser.tab_registry import tab_registry as _tr
                tabs = _tr.all_tabs()
                if 0 <= index < len(tabs):
                    target_page = _tr.get_page(tabs[index].tab_id)
                    if target_page and not target_page.is_closed():
                        await target_page.bring_to_front()
                        self.pin_active_page(target_page)
                        return f"Switched to tab {index + 1}."
                return "Tab index out of range."
            except Exception:
                # Legacy fallback
                pages = self._context.pages
                if 0 <= index < len(pages):
                    target_page = pages[index]
                    await target_page.bring_to_front()
                    self.pin_active_page(target_page)
                    return f"Switched to tab {index + 1}."
                return "Tab index out of range."
        return await _run_in_playwright(_do())

    async def switch_tab_last(self) -> str:
        async def _do():
            await self.ensure_browser()
            pages = self._context.pages
            if pages:
                target_page = pages[-1]
                await target_page.bring_to_front()
                self.pin_active_page(target_page)
                return "Switched to last tab."
            return "No tabs open."
        return await _run_in_playwright(_do())

    async def switch_tab_next(self) -> str:
        async def _do():
            await self.ensure_browser()
            pages = self._context.pages
            if not pages:
                return "No tabs open."
            try:
                current_idx = pages.index(self._page) if self._page else 0
            except ValueError:
                current_idx = 0
            next_idx = (current_idx + 1) % len(pages)
            target_page = pages[next_idx]
            await target_page.bring_to_front()
            self.pin_active_page(target_page)
            return f"Switched to next tab ({next_idx + 1} of {len(pages)})."
        return await _run_in_playwright(_do())

    async def switch_tab_prev(self) -> str:
        async def _do():
            await self.ensure_browser()
            pages = self._context.pages
            if not pages:
                return "No tabs open."
            try:
                current_idx = pages.index(self._page) if self._page else 0
            except ValueError:
                current_idx = 0
            prev_idx = (current_idx - 1) % len(pages)
            target_page = pages[prev_idx]
            await target_page.bring_to_front()
            self.pin_active_page(target_page)
            return f"Switched to previous tab ({prev_idx + 1} of {len(pages)})."
        return await _run_in_playwright(_do())

    async def switch_tab_by_url(self, partial_url: str) -> str:
        async def _do():
            await self.ensure_browser()
            for p in self._context.pages:
                if partial_url.lower() in p.url.lower():
                    await p.bring_to_front()
                    self.pin_active_page(p)
                    return f"Switched to tab matching {partial_url}."
            return f"No tab found matching {partial_url}."
        return await _run_in_playwright(_do())

    # --- Clicking & Interaction ---
    async def click(self, selector: str) -> str:
        async def _do():
            page = await self.get_active_page()
            await self._animate_action(page, selector, "click")
            await page.click(selector)
            return f"Clicked {selector}."
        return await _run_in_playwright(_do())

    async def click_text(self, text: str) -> str:
        async def _do():
            page = await self.get_active_page()
            loc = page.get_by_text(text).first
            await self._animate_action(page, loc, "click")
            await loc.click()
            return f"Clicked text '{text}'."
        return await _run_in_playwright(_do())

    async def click_search_result(self, index: int = 0) -> str:
        async def _do():
            page = await self.get_active_page()
            url = page.url

            if "google.com/search" in url:
                elements = await page.locator("div#search h3").all()
                if not elements:
                    elements = await page.locator("div.g a").all()
                if 0 <= index < len(elements):
                    text = await elements[index].inner_text()
                    await self._animate_action(page, elements[index], "click")
                    await elements[index].click()
                    return f"Clicked Google result: {text}"
                return f"Could not find result at index {index + 1} (Found {len(elements)})"

            elif "youtube.com/results" in url:
                elements = await page.locator("ytd-video-renderer a#video-title").all()
                if 0 <= index < len(elements):
                    text = await elements[index].inner_text()
                    await self._animate_action(page, elements[index], "click")
                    await elements[index].click()
                    return f"Clicked YouTube result: {text}"
                return f"Could not find video at index {index + 1} (Found {len(elements)})"

            else:
                # Generic fallback
                locators = ["h3", "a h3", ".g a", "div.search-result a"]
                for loc in locators:
                    elements = await page.locator(loc).all()
                    visible = [el for el in elements if await el.is_visible()]
                    if len(visible) > index:
                        await self._animate_action(page, visible[index], "click")
                        await visible[index].click()
                        return f"Clicked search result {index + 1} via '{loc}'."
                return f"Could not find search result {index + 1}."

        return await _run_in_playwright(_do())

    async def double_click(self, selector: str = None) -> str:
        async def _do():
            page = await self.get_active_page()
            if selector:
                await self._animate_action(page, selector, "dblclick")
                await page.dblclick(selector)
            else:
                await page.mouse.dblclick(0, 0)
            return "Double clicked."
        return await _run_in_playwright(_do())

    async def right_click(self, selector: str = None) -> str:
        async def _do():
            page = await self.get_active_page()
            if selector:
                await self._animate_action(page, selector, "click")
                await page.click(selector, button="right")
            else:
                await page.mouse.click(0, 0, button="right")
            return "Right clicked."
        return await _run_in_playwright(_do())

    async def hover(self, selector: str) -> str:
        async def _do():
            page = await self.get_active_page()
            await self._animate_action(page, selector, "hover")
            await page.hover(selector)
            return f"Hovered over {selector}."
        return await _run_in_playwright(_do())

    async def type_text(self, selector: str, text: str, human_like: bool = True) -> str:
        async def _do():
            page = await self.get_active_page()
            await self._animate_action(page, selector, "click")
            if human_like:
                await page.locator(selector).first.click()
                await page.keyboard.type(text, delay=random.randint(20, 60))
            else:
                await page.fill(selector, text)
            return f"Typed text into {selector}."
        return await _run_in_playwright(_do())

    async def press_key(self, key: str) -> str:
        async def _do():
            page = await self.get_active_page()
            await page.keyboard.press(key)
            return f"Pressed {key}."
        return await _run_in_playwright(_do())

    # --- Clipboard ---
    async def clipboard_select_all(self) -> str:
        async def _do():
            page = await self.get_active_page(read_only=True)
            key = "Meta+A" if sys.platform == "darwin" else "Control+A"
            await page.keyboard.press(key)
            return "Selected all text."
        return await _run_in_playwright(_do())

    async def clipboard_copy(self) -> str:
        async def _do():
            page = await self.get_active_page(read_only=True)
            key = "Meta+C" if sys.platform == "darwin" else "Control+C"
            await page.keyboard.press(key)
            return "Copied text."
        return await _run_in_playwright(_do())

    async def clipboard_cut(self) -> str:
        async def _do():
            page = await self.get_active_page()
            key = "Meta+X" if sys.platform == "darwin" else "Control+X"
            await page.keyboard.press(key)
            return "Cut text."
        return await _run_in_playwright(_do())

    async def clipboard_paste(self) -> str:
        async def _do():
            page = await self.get_active_page()
            key = "Meta+V" if sys.platform == "darwin" else "Control+V"
            await page.keyboard.press(key)
            return "Pasted text."
        return await _run_in_playwright(_do())

    # --- Scrolling ---
    async def scroll(self, direction: str, amount: int = 500) -> str:
        async def _do():
            page = await self.get_active_page(read_only=True)
            sign = 1 if direction == "down" else -1
            await page.mouse.wheel(0, sign * amount)
            return f"Scrolled {direction}."
        return await _run_in_playwright(_do())

    async def scroll_amount(self, direction: str, magnitude: str) -> str:
        amount = 200 if magnitude == "little" else 800 if magnitude in ["lot", "more"] else 500
        return await self.scroll(direction, amount)

    async def scroll_to_top(self) -> str:
        async def _do():
            page = await self.get_active_page(read_only=True)
            await page.evaluate("window.scrollTo(0, 0)")
            return "Scrolled to top."
        return await _run_in_playwright(_do())

    async def scroll_to_bottom(self) -> str:
        async def _do():
            page = await self.get_active_page(read_only=True)
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            return "Scrolled to bottom."
        return await _run_in_playwright(_do())

    # --- Reading & Information ---
    async def get_page_title(self) -> str:
        async def _do():
            page = await self.get_active_page(allow_restricted=True)
            return await page.title()
        return await _run_in_playwright(_do())

    async def extract_page_content(self) -> str:
        async def _do():
            page = await self.get_active_page(allow_restricted=True)
            import re
            text = await page.inner_text("body")
            return re.sub(r'\n+', '\n', text).strip()
        return await _run_in_playwright(_do())

    async def extract_clean_text(self) -> str:
        """Extract clean text using BeautifulSoup4 (bypasses Playwright's inner_text slowness)."""
        async def _do():
            page = await self.get_active_page(allow_restricted=True)
            html_content = await page.content()
            try:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(html_content, "lxml")
                for element in soup(["script", "style", "noscript", "header", "footer", "nav", "svg", "img"]):
                    element.decompose()
                text = soup.get_text(separator=' ', strip=True)
                import re
                return re.sub(r'\s+', ' ', text).strip()
            except Exception as e:
                logger.error(f"BeautifulSoup parsing failed: {e}")
                text = await page.inner_text("body")
                import re
                return re.sub(r'\n+', '\n', text).strip()
        return await _run_in_playwright(_do())

    # --- Screenshots & Visuals ---
    async def screenshot(self, filename: str = "screenshot.png", full_page: bool = False) -> str:
        async def _do():
            page = await self.get_active_page(allow_restricted=True)
            path = os.path.join(self._get_profile_path(), "screenshots", filename)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            await page.screenshot(path=path, full_page=full_page)
            return path
        return await _run_in_playwright(_do())

    async def analyze_screen(self, query: str = "Describe what is on this screen.") -> str:
        async def _do():
            path = await self.screenshot("analysis.png")
            from app.services.vision_service import VisionService
            return await VisionService.describe_image(path, query)
        return await _run_in_playwright(_do())

    async def mark_elements(self) -> str:
        async def _do():
            page = await self.get_active_page()
            script = """
            () => {
                let id = 0;
                document.querySelectorAll('a, button, input, textarea, select, [role="button"], [onclick]').forEach(el => {
                    const rect = el.getBoundingClientRect();
                    if(rect.width > 0 && rect.height > 0) {
                        el.style.border = '2px solid red';
                        const label = document.createElement('span');
                        label.textContent = id++;
                        label.style.position = 'absolute';
                        label.style.background = 'yellow';
                        label.style.color = 'black';
                        label.style.fontSize = '12px';
                        label.style.zIndex = '99999';
                        el.appendChild(label);
                        el.setAttribute('data-ace-mark-id', id-1);
                    }
                });
            }
            """
            await page.evaluate(script)
            return "Marked interactive elements."
        return await _run_in_playwright(_do())

    async def clear_marks(self) -> str:
        async def _do():
            page = await self.get_active_page()
            script = """
            () => {
                document.querySelectorAll('[data-ace-mark-id]').forEach(el => {
                    el.style.border = '';
                    const label = Array.from(el.children).find(c => c.style && c.style.zIndex === '99999');
                    if(label) label.remove();
                    el.removeAttribute('data-ace-mark-id');
                });
            }
            """
            await page.evaluate(script)
            return "Cleared all element marks."
        return await _run_in_playwright(_do())

    # --- Window & Advanced ---
    async def set_window_state(self, state: str) -> str:
        try:
            import pygetwindow as gw
            windows = gw.getWindowsWithTitle('Chrome')
            if not windows:
                windows = gw.getWindowsWithTitle('Google Chrome')
            if windows:
                win = windows[0]
                if state == "minimize":
                    win.minimize()
                    return "Minimized browser window."
                elif state == "maximize":
                    win.maximize()
                    return "Maximized browser window."
                elif state == "restore":
                    win.restore()
                    return "Restored browser window."
            return "Could not find active browser window to manipulate."
        except ImportError:
            return "Window manipulation requires pygetwindow (pip install pygetwindow)."
        except Exception as e:
            return f"Failed to set window state: {e}"

    async def wait_for(self, description: str) -> str:
        async def _do():
            page = await self.get_active_page()
            if description.startswith((".", "#", "[")):
                await page.wait_for_selector(description)
                return f"Element '{description}' is now ready."
            await page.wait_for_load_state("networkidle", timeout=10000)
            return f"Waited for network idle related to: {description}"
        return await _run_in_playwright(_do())

    async def download_file(self) -> str:
        return "Download handlers configured. Click a link to download."

    async def upload_file(self, file_path: str = None) -> str:
        return "Upload handlers configured. Trigger a file chooser to upload."

    # --- Human-like Search (Anti-Bot) ---
    async def search_google(self, query: str, new_tab: bool = False) -> str:
        """
        Navigate to google.com homepage first, then type the query like a human.
        Going directly to /search?q= is a major bot detection signal.
        """
        async def _do():
            if new_tab:
                await self.ensure_browser()
                if not self._context:
                    raise RuntimeError("Browser context not initialized.")
                new_page = await self._context.new_page()
                await self._apply_stealth(new_page)
                # Register + pin the new tab so all follow-on commands target it
                try:
                    from automation.browser.tab_registry import tab_registry as _tr
                    _tr.register(new_page)
                except Exception:
                    pass
                self.pin_active_page(new_page)
                page = new_page
            else:
                # Use registry to get whatever tab is currently active — NOT self._page
                # (self._page may still point at the tab from a previous navigation)
                page = await self.get_active_page(allow_restricted=True)
            logger.info(f"[search_google] Navigating to Google homepage then typing query: '{query}'")

            from playwright.async_api import TimeoutError as PlaywrightTimeoutError

            # Step 1: Go to the homepage, not the search URL directly
            try:
                await page.goto("https://www.google.com", wait_until="domcontentloaded", timeout=30000)
            except PlaywrightTimeoutError:
                logger.warning("Timeout loading Google homepage, retrying...")
                try:
                    await page.reload(timeout=30000)
                except PlaywrightTimeoutError:
                    return "Network timeout while loading Google homepage."

            # Step 2: Human-like pause after page load
            await asyncio.sleep(random.uniform(0.3, 0.7))

            # Step 3: Wiggle mouse to build interaction entropy
            await self._human_mouse_wiggle(page)

            # Step 4: Click the search box (textarea on modern Google, input on older)
            try:
                search_box = page.locator('textarea[name="q"], input[name="q"]').first
                await search_box.wait_for(state="visible", timeout=5000)
                await self._animate_action(page, search_box, "click")
                await search_box.click()
                await asyncio.sleep(random.uniform(0.3, 0.7))
            except Exception as e:
                logger.warning(f"Could not locate Google search box: {e}")
                return f"Could not find Google search box: {e}"

            # Step 5: Type the query with human-like delays
            await page.keyboard.type(query, delay=random.randint(30, 75))
            await asyncio.sleep(random.uniform(0.1, 0.4))

            # Step 6: Submit with Enter
            await page.keyboard.press("Enter")

            try:
                await page.wait_for_load_state("domcontentloaded", timeout=30000)
            except PlaywrightTimeoutError:
                logger.warning("Timeout waiting for Google results page to load.")

            return f"Searched Google for '{query}'"
        return await _run_in_playwright(_do())

    async def search_youtube(self, query: str, new_tab: bool = False) -> str:
        """
        Navigate to YouTube homepage first, then type into the search box
        instead of going directly to the search results URL.
        """
        async def _do():
            if new_tab:
                await self.ensure_browser()
                if not self._context:
                    raise RuntimeError("Browser context not initialized.")
                new_page = await self._context.new_page()
                await self._apply_stealth(new_page)
                # Register + pin the new tab so all follow-on commands target it
                try:
                    from automation.browser.tab_registry import tab_registry as _tr
                    _tr.register(new_page)
                except Exception:
                    pass
                self.pin_active_page(new_page)
                page = new_page
            else:
                # Use registry to get whatever tab is currently active — NOT self._page
                page = await self.get_active_page(allow_restricted=True)
            logger.info(f"[search_youtube] Navigating to YouTube homepage then typing query: '{query}'")

            from playwright.async_api import TimeoutError as PlaywrightTimeoutError

            # Step 1: Go to YouTube homepage
            try:
                await page.goto("https://www.youtube.com", wait_until="domcontentloaded", timeout=30000)
            except PlaywrightTimeoutError:
                logger.warning("Timeout loading YouTube homepage, retrying...")
                try:
                    await page.reload(timeout=30000)
                except PlaywrightTimeoutError:
                    return "Network timeout while loading YouTube homepage."

            # Step 2: Human-like pause
            await asyncio.sleep(random.uniform(0.3, 0.7))

            # Step 3: Wiggle mouse
            await self._human_mouse_wiggle(page)

            # Step 4: Click the search box
            try:
                search_box = page.locator('input#search').first
                await search_box.wait_for(state="visible", timeout=5000)
                await self._animate_action(page, search_box, "click")
                await search_box.click()
                await asyncio.sleep(random.uniform(0.3, 0.6))
            except Exception as e:
                logger.warning(f"Could not locate YouTube search box: {e}")
                return f"Could not find YouTube search box: {e}"

            # Step 5: Type the query with human-like delays
            await page.keyboard.type(query, delay=random.randint(30, 75))
            await asyncio.sleep(random.uniform(0.1, 0.4))

            # Step 6: Submit
            await page.keyboard.press("Enter")

            try:
                await page.wait_for_load_state("domcontentloaded", timeout=30000)
            except PlaywrightTimeoutError:
                logger.warning("Timeout waiting for YouTube results page to load.")

            return f"Searched YouTube for '{query}'"
        return await _run_in_playwright(_do())

    # --- Media ---
    async def play_pause(self) -> str:
        async def _do():
            page = await self.get_active_page()
            script = """
                let v = document.querySelector('video');
                if (v) { v.paused ? v.play() : v.pause(); }
                else {
                    let btn = document.querySelector('.ytp-play-button');
                    if (btn) btn.click();
                }
            """
            for frame in page.frames:
                try:
                    await frame.evaluate(script)
                except Exception as e:
                    logger.error(f"[{__name__}] {type(e).__name__}: {e}")
                    pass
            return "Toggled playback."
        return await _run_in_playwright(_do())