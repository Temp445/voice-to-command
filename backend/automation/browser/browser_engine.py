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
    future = asyncio.run_coroutine_threadsafe(coro, _get_playwright_loop())
    return await asyncio.wrap_future(future)

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

            # Patch Chrome Preferences to prevent "Restore pages?" crash bubble
            prefs_path = os.path.join(profile_path, "Default", "Preferences")
            if os.path.exists(prefs_path):
                try:
                    import json
                    with open(prefs_path, "r", encoding="utf-8") as f:
                        prefs = json.load(f)
                    if "profile" in prefs:
                        prefs["profile"]["exit_type"] = "Normal"
                        prefs["profile"]["exited_cleanly"] = True
                    with open(prefs_path, "w", encoding="utf-8") as f:
                        json.dump(prefs, f)
                except Exception as e:
                    logger.debug(f"Failed to patch Chrome preferences: {e}")

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

    async def get_active_page(self) -> Page:
        """Return the tab the user is currently looking at.

        Three-layer detection — each layer is tried in order:
          1. document.visibilityState == "visible"  → the OS-foreground tab
          2. document.hasFocus()                    → fallback when visibility API is blocked
          3. Most-recently opened non-extension tab → final fallback

        This replaces the old self._page cache as the source-of-truth for every
        automation command. self._page is now only used to track the tab that ACE
        itself navigated to (so voice navigate commands still work), but every
        click/type/fill resolves the real active tab at call time.
        """
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
                # No real pages — return whatever ensure_browser gives us
                return await self.ensure_browser()

            if len(pages) == 1:
                self._page = pages[0]
                return self._page

            # Layer 1: visibilityState — most reliable; only the OS-foreground tab
            # returns "visible". Hidden tabs (background, minimised) return "hidden".
            for p in pages:
                try:
                    state = await p.evaluate("document.visibilityState")
                    if state == "visible":
                        if self._page != p:
                            logger.debug(f"Active tab (visibilityState): {p.url}")
                        self._page = p
                        return p
                except Exception:
                    continue

            # Layer 2: hasFocus — fires when the document has keyboard focus
            for p in pages:
                try:
                    focused = await p.evaluate("document.hasFocus()")
                    if focused:
                        if self._page != p:
                            logger.debug(f"Active tab (hasFocus): {p.url}")
                        self._page = p
                        return p
                except Exception:
                    continue

            # Layer 3: Most recently opened non-system tab (pages list is creation-order)
            fallback = pages[-1]
            if self._page != fallback:
                logger.debug(f"Active tab (fallback most-recent): {fallback.url}")
            self._page = fallback
            return fallback

        return await _run_in_playwright(_do_get_active())

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
            if new_tab:
                await self.ensure_browser()
                if not self._context:
                    raise RuntimeError("Browser context not initialized.")
                self._page = await self._context.new_page()
                await self._apply_stealth(self._page)
                page = self._page
            else:
                page = await self.get_active_page()
            target = f"https://{url}" if not url.startswith(("http://", "https://")) else url

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

            return f"Navigated to {target}"
        return await _run_in_playwright(_do_nav())

    async def go_back(self) -> str:
        async def _do():
            page = await self.get_active_page()
            await page.go_back()
            return "Navigated back."
        return await _run_in_playwright(_do())

    async def go_forward(self) -> str:
        async def _do():
            page = await self.get_active_page()
            await page.go_forward()
            return "Navigated forward."
        return await _run_in_playwright(_do())

    async def refresh(self) -> str:
        async def _do():
            page = await self.get_active_page()
            await page.reload()
            return "Page refreshed."
        return await _run_in_playwright(_do())

    async def get_url(self) -> str:
        async def _do():
            page = await self.get_active_page()
            return page.url
        return await _run_in_playwright(_do())

    # --- Tabs ---
    async def new_tab(self, url: str | None = None) -> str:
        async def _do():
            await self.ensure_browser()
            self._page = await self._context.new_page()
            # FIX: apply stealth to every new tab immediately
            await self._apply_stealth(self._page)
            if url:
                target = f"https://{url}" if not url.startswith(("http://", "https://")) else url
                await self._page.goto(target)
            return "Opened new tab."
        return await _run_in_playwright(_do())

    async def close_tab(self) -> str:
        async def _do():
            page = await self.get_active_page()
            await page.close()
            pages = self._context.pages
            if pages:
                self._page = pages[-1]
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
            return [{"index": i, "title": await p.title(), "url": p.url} for i, p in enumerate(self._context.pages)]
        return await _run_in_playwright(_do())

    async def switch_tab(self, index: int) -> str:
        async def _do():
            await self.ensure_browser()
            pages = self._context.pages
            if 0 <= index < len(pages):
                self._page = pages[index]
                await self._page.bring_to_front()
                return f"Switched to tab {index + 1}."
            return "Tab index out of range."
        return await _run_in_playwright(_do())

    async def switch_tab_last(self) -> str:
        async def _do():
            await self.ensure_browser()
            pages = self._context.pages
            if pages:
                self._page = pages[-1]
                await self._page.bring_to_front()
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
                current_idx = pages.index(self._page)
            except ValueError:
                current_idx = 0
            next_idx = (current_idx + 1) % len(pages)
            self._page = pages[next_idx]
            await self._page.bring_to_front()
            return f"Switched to next tab ({next_idx + 1} of {len(pages)})."
        return await _run_in_playwright(_do())

    async def switch_tab_prev(self) -> str:
        async def _do():
            await self.ensure_browser()
            pages = self._context.pages
            if not pages:
                return "No tabs open."
            try:
                current_idx = pages.index(self._page)
            except ValueError:
                current_idx = 0
            prev_idx = (current_idx - 1) % len(pages)
            self._page = pages[prev_idx]
            await self._page.bring_to_front()
            return f"Switched to previous tab ({prev_idx + 1} of {len(pages)})."
        return await _run_in_playwright(_do())

    async def switch_tab_by_url(self, partial_url: str) -> str:
        async def _do():
            await self.ensure_browser()
            for p in self._context.pages:
                if partial_url.lower() in p.url.lower():
                    self._page = p
                    await self._page.bring_to_front()
                    return f"Switched to tab matching {partial_url}."
            return f"No tab found matching {partial_url}."
        return await _run_in_playwright(_do())

    # --- Clicking & Interaction ---
    async def click(self, selector: str) -> str:
        async def _do():
            page = await self.get_active_page()
            await page.click(selector)
            return f"Clicked {selector}."
        return await _run_in_playwright(_do())

    async def click_text(self, text: str) -> str:
        async def _do():
            page = await self.get_active_page()
            await page.get_by_text(text).first.click()
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
                    await elements[index].click()
                    return f"Clicked Google result: {text}"
                return f"Could not find result at index {index + 1} (Found {len(elements)})"

            elif "youtube.com/results" in url:
                elements = await page.locator("ytd-video-renderer a#video-title").all()
                if 0 <= index < len(elements):
                    text = await elements[index].inner_text()
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
                        await visible[index].click()
                        return f"Clicked search result {index + 1} via '{loc}'."
                return f"Could not find search result {index + 1}."

        return await _run_in_playwright(_do())

    async def double_click(self, selector: str = None) -> str:
        async def _do():
            page = await self.get_active_page()
            if selector:
                await page.dblclick(selector)
            else:
                await page.mouse.dblclick(0, 0)
            return "Double clicked."
        return await _run_in_playwright(_do())

    async def right_click(self, selector: str = None) -> str:
        async def _do():
            page = await self.get_active_page()
            if selector:
                await page.click(selector, button="right")
            else:
                await page.mouse.click(0, 0, button="right")
            return "Right clicked."
        return await _run_in_playwright(_do())

    async def hover(self, selector: str) -> str:
        async def _do():
            page = await self.get_active_page()
            await page.hover(selector)
            return f"Hovered over {selector}."
        return await _run_in_playwright(_do())

    async def type_text(self, selector: str, text: str, human_like: bool = True) -> str:
        async def _do():
            page = await self.get_active_page()
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
            page = await self.get_active_page()
            key = "Meta+A" if sys.platform == "darwin" else "Control+A"
            await page.keyboard.press(key)
            return "Selected all text."
        return await _run_in_playwright(_do())

    async def clipboard_copy(self) -> str:
        async def _do():
            page = await self.get_active_page()
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
            page = await self.get_active_page()
            sign = 1 if direction == "down" else -1
            await page.mouse.wheel(0, sign * amount)
            return f"Scrolled {direction}."
        return await _run_in_playwright(_do())

    async def scroll_amount(self, direction: str, magnitude: str) -> str:
        amount = 200 if magnitude == "little" else 800 if magnitude in ["lot", "more"] else 500
        return await self.scroll(direction, amount)

    async def scroll_to_top(self) -> str:
        async def _do():
            page = await self.get_active_page()
            await page.evaluate("window.scrollTo(0, 0)")
            return "Scrolled to top."
        return await _run_in_playwright(_do())

    async def scroll_to_bottom(self) -> str:
        async def _do():
            page = await self.get_active_page()
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            return "Scrolled to bottom."
        return await _run_in_playwright(_do())

    # --- Reading & Information ---
    async def get_page_title(self) -> str:
        async def _do():
            page = await self.get_active_page()
            return await page.title()
        return await _run_in_playwright(_do())

    async def extract_page_content(self) -> str:
        async def _do():
            page = await self.get_active_page()
            import re
            text = await page.inner_text("body")
            return re.sub(r'\n+', '\n', text).strip()
        return await _run_in_playwright(_do())

    async def extract_clean_text(self) -> str:
        """Extract clean text using BeautifulSoup4 (bypasses Playwright's inner_text slowness)."""
        async def _do():
            page = await self.get_active_page()
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
            page = await self.get_active_page()
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
        FIX: Navigate to google.com homepage first, then type the query like a human.
        Going directly to /search?q= is a major bot detection signal.
        """
        async def _do():
            if new_tab:
                await self.ensure_browser()
                if not self._context:
                    raise RuntimeError("Browser context not initialized.")
                self._page = await self._context.new_page()
                await self._apply_stealth(self._page)
                page = self._page
            else:
                page = await self.get_active_page()
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
        FIX: Navigate to YouTube homepage first, then type into the search box
        instead of going directly to the search results URL.
        """
        async def _do():
            if new_tab:
                await self.ensure_browser()
                if not self._context:
                    raise RuntimeError("Browser context not initialized.")
                self._page = await self._context.new_page()
                await self._apply_stealth(self._page)
                page = self._page
            else:
                page = await self.get_active_page()
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