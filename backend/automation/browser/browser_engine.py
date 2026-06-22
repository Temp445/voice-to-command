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

    async def ensure_browser(self) -> Page:
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
                                logger.error(f"Error: {e}")
                                logger.info("No active CDP session found. Launching new persistent context.")
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
                                        "--test-type",
                                        "--remote-debugging-port=9222",
                                        "--disable-features=PasswordManager"
                                    ],
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
                            self._context = await self._playwright.firefox.launch_persistent_context(user_data_dir=profile_path, headless=False, no_viewport=True)
                        elif b_type == "webkit":
                            self._context = await self._playwright.webkit.launch_persistent_context(user_data_dir=profile_path, headless=False, no_viewport=True)
                        else:
                            self._context = await self._playwright.chromium.launch_persistent_context(
                                user_data_dir=profile_path, channel="chrome", headless=False, no_viewport=True,
                                args=["--start-maximized", "--disable-blink-features=AutomationControlled", "--no-first-run", "--no-default-browser-check", "--test-type", "--remote-debugging-port=9222", "--disable-features=PasswordManager"],
                                ignore_default_args=["--enable-automation"]
                            )
                    
                    if not is_cdp_reconnect:
                        try:
                            if b_type not in ["firefox", "webkit"]:
                                try:
                                    from playwright_stealth import stealth_async
                                    await stealth_async(self._context)
                                except ImportError:
                                    from playwright_stealth import Stealth
                                    await Stealth().apply_stealth_async(self._context)
                        except Exception as e:
                            logger.warning(f"Stealth could not be applied: {e}")

                    pages = self._context.pages
                    
                    # Intelligently find the active/relevant page, filtering out extensions, blanks, and the command console itself
                    active_page = None
                    for p in reversed(pages): # Iterate backwards to get the most recently opened tab
                        url = p.url.lower()
                        if not url.startswith('chrome-extension://') and url != 'about:blank' and 'localhost:3000' not in url and '127.0.0.1:3000' not in url:
                            active_page = p
                            break
                            
                    self._page = active_page if active_page else (pages[-1] if pages else await self._context.new_page())
                    
                    if not is_cdp_reconnect:
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
            from playwright.async_api import TimeoutError as PlaywrightTimeoutError
            try:
                await page.goto(target, wait_until="domcontentloaded", timeout=30000)
            except PlaywrightTimeoutError:
                logger.warning(f"Timeout navigating to {target}, retrying...")
                try:
                    await page.reload(timeout=30000)
                except PlaywrightTimeoutError:
                    return f"Failed to fully load {target} due to network timeout."
            
            # Restore and focus the browser window
            try:
                from automation.desktop.window_manager import WindowManager
                from app.config import settings
                wm = WindowManager()
                
                # Fetch active page title for precise window matching
                page_title = await page.title()
                target_title = page_title if page_title and page_title.lower() != "about:blank" else ""
                
                if not target_title:
                    b_type = settings.browser_type.lower()
                    target_title = "chrome" if b_type == "chromium" else b_type
                
                wm.force_focus_by_title(target_title)
            except Exception as e:
                logger.warning(f"Failed to focus browser window after navigation: {e}")
                
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

    async def click_search_result(self, index: int = 0) -> str:
        async def _do():
            page = await self.ensure_browser()
            # General heuristic for Google/Bing search results or generic main links
            locators = [
                "ytd-video-renderer a#video-title", # YouTube specific
                "div.g h3", # Google specific
                "h3", 
                "a h3", 
                ".g a", 
                "div.search-result a"
            ]
            for loc in locators:
                elements = await page.locator(loc).all()
                visible_elements = []
                for el in elements:
                    if await el.is_visible():
                        visible_elements.append(el)
                        
                if len(visible_elements) > index:
                    await visible_elements[index].click()
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

    async def extract_clean_text(self) -> str:
        """Extract clean text from the current page using BeautifulSoup4 (bypasses Playwright's inner_text slowness)."""
        async def _do():
            page = await self.ensure_browser()
            html_content = await page.content()
            try:
                from bs4 import BeautifulSoup
                # Parse with lxml for speed
                soup = BeautifulSoup(html_content, "lxml")
                
                # Remove unwanted tags
                for element in soup(["script", "style", "noscript", "header", "footer", "nav", "svg", "img"]):
                    element.decompose()
                    
                # Extract text
                text = soup.get_text(separator=' ', strip=True)
                
                # Clean up multiple spaces and newlines
                import re
                clean_text = re.sub(r'\s+', ' ', text).strip()
                return clean_text
            except Exception as e:
                logger.error(f"BeautifulSoup parsing failed: {e}")
                # Fallback to Playwright
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
            logger.info(f"[search_google] Current URL: {page.url} — navigating directly to Google search for query: '{query}'")
            import urllib.parse
            encoded_query = urllib.parse.quote_plus(query)
            search_url = f"https://www.google.com/search?q={encoded_query}"
            
            from playwright.async_api import TimeoutError as PlaywrightTimeoutError
            try:
                await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
            except PlaywrightTimeoutError:
                logger.warning(f"Timeout navigating to Google search, retrying...")
                try:
                    await page.reload(timeout=30000)
                except PlaywrightTimeoutError:
                    return f"Network timeout while trying to search Google for '{query}'"
            
            try:
                # Defocus the URL bar by physically clicking the page's search box
                await page.locator("[name='q']").click(force=True, timeout=3000)
                await page.mouse.click(10, 100) # Safe click on the left margin
                # Pressing a harmless key ensures the OS transfers focus to the web view
                await page.keyboard.press("Control")
            except Exception as e:
                logger.error(f"Error: {e}")
                pass
                
            await asyncio.sleep(1.0)
            return f"Searched Google for '{query}'"
        return await _run_in_playwright(_do())

    async def click_search_result(self, index: int = 0) -> str:
        async def _do():
            page = await self.ensure_browser()
            url = page.url
            
            if "google.com/search" in url:
                # Target the h3 headings which contain the links
                elements = await page.locator("div#search h3").all()
                if not elements:
                    # Fallback to general links in results
                    elements = await page.locator("div.g a").all()
                    
                if 0 <= index < len(elements):
                    text = await elements[index].inner_text()
                    await elements[index].click()
                    return f"Clicked Google result: {text}"
                return f"Could not find result at index {index+1} (Found {len(elements)})"
                
            elif "youtube.com/results" in url:
                elements = await page.locator("ytd-video-renderer a#video-title").all()
                if 0 <= index < len(elements):
                    text = await elements[index].inner_text()
                    await elements[index].click()
                    return f"Clicked YouTube result: {text}"
                return f"Could not find video at index {index+1} (Found {len(elements)})"
                
            else:
                return "Not on a recognized search results page."
                
        return await _run_in_playwright(_do())

    async def search_youtube(self, query: str) -> str:
        async def _do():
            page = await self.ensure_browser()
            logger.info(f"[search_youtube] Current URL: {page.url} — navigating directly to YouTube search for query: '{query}'")
            import urllib.parse
            encoded_query = urllib.parse.quote_plus(query)
            search_url = f"https://www.youtube.com/results?search_query={encoded_query}"
            
            from playwright.async_api import TimeoutError as PlaywrightTimeoutError
            try:
                await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
            except PlaywrightTimeoutError:
                logger.warning(f"Timeout navigating to YouTube search, retrying...")
                try:
                    await page.reload(timeout=30000)
                except PlaywrightTimeoutError:
                    return f"Network timeout while trying to search YouTube for '{query}'"
            
            try:
                # Defocus the URL bar by physically clicking the page's search box
                await page.locator("input#search").click(force=True, timeout=3000)
                await page.mouse.click(10, 100) # Safe click on the left margin
                await page.keyboard.press("Control")
            except Exception as e:
                logger.error(f"Error: {e}")
                pass
                
            await asyncio.sleep(1.0)
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
                    logger.error(f"Error: {e}")
                    pass
            return "Toggled playback."
        return await _run_in_playwright(_do())
