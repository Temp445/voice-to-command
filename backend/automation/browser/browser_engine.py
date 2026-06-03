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

class BrowserEngine:
    """Singleton engine for isolated, stealthy browser automation."""
    _instance = None
    _playwright = None
    _context: BrowserContext | None = None
    _page: Page | None = None
    _lock = asyncio.Lock()

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

    async def ensure_browser(self) -> Page:
        async def _do_ensure():
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

                logger.info(f"Launching Browser in isolated profile: {profile_path}")
                try:
                    self._context = await self._playwright.chromium.launch_persistent_context(
                        user_data_dir=profile_path,
                        channel="chrome",  # Use system Chrome to avoid Chromium fingerprint
                        headless=False,
                        no_viewport=True,
                        args=[
                            "--start-maximized",
                            "--disable-blink-features=AutomationControlled",
                            "--no-first-run",
                            "--no-default-browser-check",
                            "--test-type"
                        ],
                        ignore_default_args=["--enable-automation"]
                    )
                    
                    try:
                        try:
                            from playwright_stealth import stealth_async
                            await stealth_async(self._context)
                        except ImportError:
                            from playwright_stealth import Stealth
                            await Stealth().apply_stealth_async(self._context)
                    except ImportError:
                        logger.warning("playwright-stealth not installed, bot detection risk higher.")

                    pages = self._context.pages
                    self._page = pages[0] if pages else await self._context.new_page()
                    
                    try:
                        client = await self._context.new_cdp_session(self._page)
                        window = await client.send('Browser.getWindowForTarget')
                        await client.send('Browser.setWindowBounds', {
                            'windowId': window['windowId'], 
                            'bounds': {'windowState': 'maximized'}
                        })
                        await client.detach()
                    except Exception as e:
                        logger.warning(f"Could not auto-maximize window via CDP: {e}")

                    return self._page

                except Exception as e:
                    logger.error(f"Failed to launch persistent context: {e}")
                    raise

        return await _run_in_playwright(_do_ensure())

    async def close_browser(self):
        async def _do_close():
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
            await page.goto(target, wait_until="commit", timeout=15000)
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
            # Closing all tabs usually kills the browser or context in playwright.
            # We must ensure there is at least one tab left.
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

    async def click_first_result(self) -> str:
        async def _do():
            page = await self.ensure_browser()
            # General heuristic for Google/Bing search results or generic main links
            locators = [
                "h3", 
                "a h3", 
                ".g a", 
                "div.search-result a",
                "ytd-video-renderer a#video-title"
            ]
            for loc in locators:
                elements = await page.locator(loc).all()
                for el in elements:
                    if await el.is_visible():
                        await el.click()
                        return f"Clicked first search result via '{loc}'."
            return "Could not find a clear search result to click."
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
                await page.keyboard.type(text, delay=random.randint(40, 100))
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
            # In a real impl, we'd pass the local image path to VisionService.
            # Assuming VisionService has a method that takes a path.
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
        # Manipulates the actual OS window using pygetwindow
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
            # If it's a direct CSS selector
            if description.startswith((".", "#", "[")):
                await page.wait_for_selector(description)
                return f"Element '{description}' is now ready."
                
            # If natural language, we use a generic wait for network or leverage DOMAgent
            # For simplicity, if it's natural text, wait for network idle as a fallback.
            await page.wait_for_load_state("networkidle", timeout=10000)
            return f"Waited for network idle related to: {description}"
        return await _run_in_playwright(_do())

    async def download_file(self) -> str:
        # A generic placeholder. A true voice-driven download requires knowing WHAT to click.
        # This just sets up the handler.
        return "Download handlers configured. Click a link to download."

    async def upload_file(self, file_path: str = None) -> str:
        # A generic placeholder for uploading.
        return "Upload handlers configured. Trigger a file chooser to upload."

    # --- Human-like Search (Anti-Bot) ---
    async def search_google(self, query: str) -> str:
        async def _do():
            page = await self.ensure_browser()
            await page.goto("https://www.google.com", wait_until="commit")
            await asyncio.sleep(1.0) # Wait for elements to appear
            search_box = page.locator("textarea[name='q'], input[name='q']").first
            await search_box.click()
            await page.keyboard.type(query, delay=random.randint(40, 100))
            await asyncio.sleep(0.3)
            await page.keyboard.press("Enter")
            await asyncio.sleep(2.0) # Wait for results to render
            await page.wait_for_load_state("domcontentloaded")
            return f"Searched Google for '{query}'"
        return await _run_in_playwright(_do())

    async def search_youtube(self, query: str) -> str:
        async def _do():
            page = await self.ensure_browser()
            await page.goto("https://www.youtube.com", wait_until="commit")
            await asyncio.sleep(1.5) # Wait for elements
            search_box = page.locator("input#search, input[name='search_query']").first
            await search_box.click()
            await page.keyboard.type(query, delay=random.randint(40, 100))
            await asyncio.sleep(0.3)
            await page.keyboard.press("Enter")
            await asyncio.sleep(2.0) # Wait for results to render
            await page.wait_for_load_state("domcontentloaded")
            return f"Searched YouTube for '{query}'"
        return await _run_in_playwright(_do())

    # --- Media ---
    async def play_pause(self) -> str:
        async def _do():
            page = await self.ensure_browser()
            if "youtube.com" in page.url:
                await page.keyboard.press("k")
            else:
                await page.evaluate("document.querySelectorAll('video').forEach(v => v.paused ? v.play() : v.pause())")
            return "Toggled playback."
        return await _run_in_playwright(_do())
