"""
Browser Engine — Enterprise web automation using Playwright.
Isolates automation to a dedicated persistent profile (no CDP, no killing user's Chrome).
Integrates stealth and human-like typing to avoid bot detection.
"""

import asyncio
import os
import sys
import threading
import random
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

# Common Chrome launch args that reduce automation fingerprint
CHROME_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--no-first-run",
    "--no-default-browser-check",
    "--test-type",
    "--remote-debugging-port=9222",
    "--disable-features=PasswordManager,IsolateOrigins,site-per-process",
    "--disable-ipc-flooding-protection",
    "--start-maximized",
    "--flag-switches-begin",
    "--flag-switches-end",
]


class BrowserEngine:
    """Singleton engine for isolated, stealthy browser automation."""
    _instance = None
    _playwright = None
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
        """Prewarm the Chrome profile and Playwright binaries completely invisibly."""
        async def _do():
            if not self._playwright:
                self._playwright = await async_playwright().start()

            profile_path = self._get_profile_path()
            os.makedirs(profile_path, exist_ok=True)

            # Prevent "Restore pages?" bubble by fixing the Preferences file
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

            # Launch headless briefly to populate cache and binaries
            try:
                temp_ctx = await self._playwright.chromium.launch_persistent_context(
                    user_data_dir=profile_path,
                    channel="chrome",
                    headless=True,
                    user_agent=STANDARD_UA,
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--no-first-run",
                        "--no-default-browser-check",
                        "--disable-features=PasswordManager",
                        "--start-maximized"
                    ]
                )
                await asyncio.sleep(0.5)
                await temp_ctx.close()
                logger.info("✅ Headless pre-warm completed successfully.")
            except Exception as e:
                logger.debug(f"Headless prewarm skipped/failed: {e}")

        await _run_in_playwright(_do())

    async def ensure_browser(self, background: bool = False) -> Page:
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

                logger.info(f"Launching Browser ({settings.browser_type}) in isolated profile: {profile_path}")
                is_cdp_reconnect = False

                try:
                    b_type = settings.browser_type.lower()

                    try:
                        if b_type == "firefox":
                            self._context = await self._playwright.firefox.launch_persistent_context(
                                user_data_dir=profile_path,
                                headless=False,
                                no_viewport=True,
                            )
                        elif b_type == "webkit":
                            self._context = await self._playwright.webkit.launch_persistent_context(
                                user_data_dir=profile_path,
                                headless=False,
                                no_viewport=True,
                            )
                        else:
                            # Attempt to reconnect via CDP first
                            try:
                                browser = await self._playwright.chromium.connect_over_cdp("http://localhost:9222")
                                self._context = browser.contexts[0] if browser.contexts else await browser.new_context()
                                is_cdp_reconnect = True
                                logger.info("Successfully reconnected to existing Chrome instance via CDP.")
                            except Exception as e:
                                logger.debug(f"No active CDP session found (expected if browser is closed): {e}")
                                logger.info("Launching new persistent context.")

                                # FIX: user_agent now set on the primary launch path
                                self._context = await self._playwright.chromium.launch_persistent_context(
                                    user_data_dir=profile_path,
                                    channel="chrome",
                                    headless=False,
                                    no_viewport=True,
                                    user_agent=STANDARD_UA,
                                    args=CHROME_ARGS,
                                    ignore_default_args=["--enable-automation"]
                                )

                    except Exception as launch_err:
                        logger.warning(f"Browser launch failed, attempting to kill locked processes: {launch_err}")
                        import psutil
                        for proc in psutil.process_iter(['name', 'cmdline']):
                            try:
                                if proc.info['name'] and proc.info['name'].lower() in ['chrome.exe', 'msedge.exe', 'firefox.exe']:
                                    cmdline = proc.info.get('cmdline')
                                    if cmdline and any('ACE\\BrowserProfile' in str(arg) for arg in cmdline):
                                        logger.info(f"Killing orphaned browser process: {proc.info['name']} (PID: {proc.pid})")
                                        proc.kill()
                            except (psutil.NoSuchProcess, psutil.AccessDenied):
                                pass

                        await asyncio.sleep(2.0)

                        # Retry once after cleanup
                        if b_type == "firefox":
                            self._context = await self._playwright.firefox.launch_persistent_context(
                                user_data_dir=profile_path, headless=False, no_viewport=True
                            )
                        elif b_type == "webkit":
                            self._context = await self._playwright.webkit.launch_persistent_context(
                                user_data_dir=profile_path, headless=False, no_viewport=True
                            )
                        else:
                            self._context = await self._playwright.chromium.launch_persistent_context(
                                user_data_dir=profile_path,
                                channel="chrome",
                                headless=False,
                                no_viewport=True,
                                user_agent=STANDARD_UA,
                                args=CHROME_ARGS + ["--disable-session-crashed-bubble"],
                                ignore_default_args=["--enable-automation"]
                            )

                    if not is_cdp_reconnect:
                        b_type = settings.browser_type.lower()
                        if b_type not in ["firefox", "webkit"]:
                            # Apply stealth to the context
                            await self._apply_stealth(self._context)
                            # Apply stealth to any already-open pages
                            for p in self._context.pages:
                                await self._apply_stealth(p)
                            # FIX: let stealth JS patches settle before any navigation
                            await asyncio.sleep(0.3)

                    pages = self._context.pages

                    # Intelligently find the active/relevant page,
                    # filtering out extensions, blanks, and the command console
                    active_page = None
                    for p in reversed(pages):
                        url = p.url.lower()
                        if (not url.startswith('chrome-extension://')
                                and url != 'about:blank'
                                and 'localhost:3000' not in url
                                and '127.0.0.1:3000' not in url):
                            active_page = p
                            break

                    self._page = active_page if active_page else (pages[-1] if pages else await self._context.new_page())
                    return self._page

                except Exception as e:
                    logger.error(f"Failed to launch persistent context: {e}")
                    raise

        return await _run_in_playwright(_do_ensure())

    async def close_browser(self):
        async def _do_close():
            if self._lock is None:
                self._lock = asyncio.Lock()
            async with self._lock:
                if self._context:
                    await self._context.close()
                    self._context = None
                    self._page = None
                if self._playwright:
                    await self._playwright.stop()
                    self._playwright = None
        await _run_in_playwright(_do_close())

    async def restart_browser(self):
        await self.close_browser()
        await self.ensure_browser()
        return "Browser restarted."

    # --- Navigation ---
    async def navigate(self, url: str) -> str:
        async def _do_nav():
            page = await self.ensure_browser()
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
            page = await self.ensure_browser()
            await page.go_back()
            return "Navigated back."
        return await _run_in_playwright(_do())

    async def go_forward(self) -> str:
        async def _do():
            page = await self.ensure_browser()
            await page.go_forward()
            return "Navigated forward."
        return await _run_in_playwright(_do())

    async def refresh(self) -> str:
        async def _do():
            page = await self.ensure_browser()
            await page.reload()
            return "Page refreshed."
        return await _run_in_playwright(_do())

    async def get_url(self) -> str:
        async def _do():
            page = await self.ensure_browser()
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
            page = await self.ensure_browser()
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
            page = await self.ensure_browser()
            await page.click(selector)
            return f"Clicked {selector}."
        return await _run_in_playwright(_do())

    async def click_text(self, text: str) -> str:
        async def _do():
            page = await self.ensure_browser()
            await page.get_by_text(text).first.click()
            return f"Clicked text '{text}'."
        return await _run_in_playwright(_do())

    async def click_search_result(self, index: int = 0) -> str:
        async def _do():
            page = await self.ensure_browser()
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
            page = await self.ensure_browser()
            if selector:
                await page.dblclick(selector)
            else:
                await page.mouse.dblclick(0, 0)
            return "Double clicked."
        return await _run_in_playwright(_do())

    async def right_click(self, selector: str = None) -> str:
        async def _do():
            page = await self.ensure_browser()
            if selector:
                await page.click(selector, button="right")
            else:
                await page.mouse.click(0, 0, button="right")
            return "Right clicked."
        return await _run_in_playwright(_do())

    async def hover(self, selector: str) -> str:
        async def _do():
            page = await self.ensure_browser()
            await page.hover(selector)
            return f"Hovered over {selector}."
        return await _run_in_playwright(_do())

    async def type_text(self, selector: str, text: str, human_like: bool = True) -> str:
        async def _do():
            page = await self.ensure_browser()
            if human_like:
                await page.locator(selector).first.click()
                await page.keyboard.type(text, delay=random.randint(20, 60))
            else:
                await page.fill(selector, text)
            return f"Typed text into {selector}."
        return await _run_in_playwright(_do())

    async def press_key(self, key: str) -> str:
        async def _do():
            page = await self.ensure_browser()
            await page.keyboard.press(key)
            return f"Pressed {key}."
        return await _run_in_playwright(_do())

    # --- Clipboard ---
    async def clipboard_select_all(self) -> str:
        async def _do():
            page = await self.ensure_browser()
            key = "Meta+A" if sys.platform == "darwin" else "Control+A"
            await page.keyboard.press(key)
            return "Selected all text."
        return await _run_in_playwright(_do())

    async def clipboard_copy(self) -> str:
        async def _do():
            page = await self.ensure_browser()
            key = "Meta+C" if sys.platform == "darwin" else "Control+C"
            await page.keyboard.press(key)
            return "Copied text."
        return await _run_in_playwright(_do())

    async def clipboard_cut(self) -> str:
        async def _do():
            page = await self.ensure_browser()
            key = "Meta+X" if sys.platform == "darwin" else "Control+X"
            await page.keyboard.press(key)
            return "Cut text."
        return await _run_in_playwright(_do())

    async def clipboard_paste(self) -> str:
        async def _do():
            page = await self.ensure_browser()
            key = "Meta+V" if sys.platform == "darwin" else "Control+V"
            await page.keyboard.press(key)
            return "Pasted text."
        return await _run_in_playwright(_do())

    # --- Scrolling ---
    async def scroll(self, direction: str, amount: int = 500) -> str:
        async def _do():
            page = await self.ensure_browser()
            sign = 1 if direction == "down" else -1
            await page.mouse.wheel(0, sign * amount)
            return f"Scrolled {direction}."
        return await _run_in_playwright(_do())

    async def scroll_amount(self, direction: str, magnitude: str) -> str:
        amount = 200 if magnitude == "little" else 800 if magnitude in ["lot", "more"] else 500
        return await self.scroll(direction, amount)

    async def scroll_to_top(self) -> str:
        async def _do():
            page = await self.ensure_browser()
            await page.evaluate("window.scrollTo(0, 0)")
            return "Scrolled to top."
        return await _run_in_playwright(_do())

    async def scroll_to_bottom(self) -> str:
        async def _do():
            page = await self.ensure_browser()
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            return "Scrolled to bottom."
        return await _run_in_playwright(_do())

    # --- Reading & Information ---
    async def get_page_title(self) -> str:
        async def _do():
            page = await self.ensure_browser()
            return await page.title()
        return await _run_in_playwright(_do())

    async def extract_page_content(self) -> str:
        async def _do():
            page = await self.ensure_browser()
            import re
            text = await page.inner_text("body")
            return re.sub(r'\n+', '\n', text).strip()
        return await _run_in_playwright(_do())

    async def extract_clean_text(self) -> str:
        """Extract clean text using BeautifulSoup4 (bypasses Playwright's inner_text slowness)."""
        async def _do():
            page = await self.ensure_browser()
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
            page = await self.ensure_browser()
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
            page = await self.ensure_browser()
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
            page = await self.ensure_browser()
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
            page = await self.ensure_browser()
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
    async def search_google(self, query: str) -> str:
        """
        FIX: Navigate to google.com homepage first, then type the query like a human.
        Going directly to /search?q= is a major bot detection signal.
        """
        async def _do():
            page = await self.ensure_browser()
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

    async def search_youtube(self, query: str) -> str:
        """
        FIX: Navigate to YouTube homepage first, then type into the search box
        instead of going directly to the search results URL.
        """
        async def _do():
            page = await self.ensure_browser()
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
            page = await self.ensure_browser()
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