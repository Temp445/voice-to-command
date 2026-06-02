"""
ACE Voice Controller — Browser Controller (Playwright)
Async browser automation: navigate, search, fill forms, multi-tab.
"""

import asyncio
import sys
import threading
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from loguru import logger
from app.config import settings
from app.core.exceptions import BrowserAutomationError
# from playwright_stealth import Stealth  # Disabled due to hanging


# --- Dedicated Playwright Event Loop ---
# Uvicorn on Windows defaults to SelectorEventLoop, which lacks subprocess support
# and causes NotImplementedError. We isolate Playwright in its own ProactorEventLoop.
_playwright_loop = None

def _get_playwright_loop():
    global _playwright_loop
    if _playwright_loop is None:
        if sys.platform == 'win32':
            _playwright_loop = asyncio.ProactorEventLoop()
        else:
            _playwright_loop = asyncio.new_event_loop()
        t = threading.Thread(target=_playwright_loop.run_forever, daemon=True, name="PlaywrightThread")
        t.start()
    return _playwright_loop

async def _run_in_playwright(coro):
    future = asyncio.run_coroutine_threadsafe(coro, _get_playwright_loop())
    return await asyncio.wrap_future(future)


class BrowserController:
    """Singleton Playwright browser controller with CDP Attachment."""

    _playwright = None
    _browser: Browser | None = None
    _context: BrowserContext | None = None
    _page: Page | None = None

    async def _ensure_browser(self) -> Page:
        async def _do_ensure():
            needs_init = True
            if BrowserController._browser and BrowserController._browser.is_connected():
                needs_init = False
            elif BrowserController._context and BrowserController._browser is None:
                # Persistent context check
                try:
                    if BrowserController._context.pages:
                        needs_init = False
                except Exception:
                    pass

            if needs_init:
                if not BrowserController._playwright:
                    BrowserController._playwright = await async_playwright().start()
                
                try:
                    # 1. Try attaching to existing Chrome instance via CDP
                    BrowserController._browser = await BrowserController._playwright.chromium.connect_over_cdp("http://localhost:9222")
                    logger.info("Connected to existing Chrome instance via CDP (port 9222)")
                    BrowserController._context = BrowserController._browser.contexts[0]
                    BrowserController._page = BrowserController._context.pages[0] if BrowserController._context.pages else await BrowserController._context.new_page()
                except Exception:
                    logger.info("No active CDP Chrome found. Attempting to launch persistent context...")
                    
                    import os
                    from pathlib import Path
                    import psutil
                    
                    # 2. Find profile path
                    profile_paths = [
                        (r"%LOCALAPPDATA%\Google\Chrome\User Data", "chrome", "chrome.exe"),
                        (r"%LOCALAPPDATA%\Microsoft\Edge\User Data", "msedge", "msedge.exe"),
                        (r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\User Data", "chrome", "brave.exe")
                    ]
                    
                    selected_path = None
                    selected_channel = "chrome"
                    selected_exe = "chrome.exe"
                    for p, channel, exe in profile_paths:
                        expanded = os.path.expandvars(p)
                        if Path(expanded).exists():
                            selected_path = expanded
                            selected_channel = channel
                            selected_exe = exe
                            break
                            
                    # Check if the browser is already running (which means profile is locked)
                    browser_running = False
                    for proc in psutil.process_iter(['name']):
                        try:
                            if proc.info['name'] and proc.info['name'].lower() == selected_exe:
                                browser_running = True
                                break
                        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                            pass
                            
                    if selected_path and not browser_running:
                        try:
                            # 3. Launch persistent context
                            BrowserController._context = await BrowserController._playwright.chromium.launch_persistent_context(
                                user_data_dir=selected_path,
                                channel=selected_channel,
                                headless=False,
                                no_viewport=True,
                                args=["--start-maximized"]
                            )
                            logger.info(f"Launched persistent context with profile: {selected_path}")
                            BrowserController._browser = None # Persistent context doesn't expose browser
                            BrowserController._page = BrowserController._context.pages[0] if BrowserController._context.pages else await BrowserController._context.new_page()
                        except Exception as e:
                            logger.error(f"Failed to launch persistent context: {e}")
                            logger.warning("Profile locked. Falling back to a temporary system Chrome instance...")
                            
                            import tempfile
                            temp_dir = tempfile.mkdtemp(prefix="ace_temp_profile_")
                            BrowserController._context = await BrowserController._playwright.chromium.launch_persistent_context(
                                user_data_dir=temp_dir,
                                channel=selected_channel,
                                headless=False,
                                no_viewport=True,
                                args=[
                                    "--start-maximized",
                                    "--no-first-run",
                                    "--no-default-browser-check",
                                    "--disable-sync",
                                    "--disable-infobars",
                                    "--disable-features=OptimizationHints,MediaRouter,DialMediaRouteProvider,CalculateNativeWinOcclusion,ProfilePicker"
                                ]
                            )
                            BrowserController._browser = None
                            BrowserController._page = BrowserController._context.pages[0] if BrowserController._context.pages else await BrowserController._context.new_page()
                    else:
                        if browser_running:
                            logger.warning(f"Browser ({selected_exe}) is already running normally. Launching temporary system Chrome instance...")
                        else:
                            logger.warning("No compatible profile found. Launching temporary system Chrome instance...")
                            
                        import tempfile
                        temp_dir = tempfile.mkdtemp(prefix="ace_temp_profile_")
                        
                        BrowserController._context = await BrowserController._playwright.chromium.launch_persistent_context(
                            user_data_dir=temp_dir,
                            channel=selected_channel,
                            headless=False,
                            no_viewport=True,
                            args=[
                                "--start-maximized",
                                "--no-first-run",
                                "--no-default-browser-check",
                                "--disable-sync",
                                "--disable-infobars",
                                "--disable-features=OptimizationHints,MediaRouter,DialMediaRouteProvider,CalculateNativeWinOcclusion,ProfilePicker"
                            ]
                        )
                        BrowserController._browser = None
                        BrowserController._page = BrowserController._context.pages[0] if BrowserController._context.pages else await BrowserController._context.new_page()

            if not BrowserController._page or BrowserController._page.is_closed():
                try:
                    BrowserController._page = await BrowserController._context.new_page()
                except Exception as e:
                    logger.warning(f"Browser context appears dead ({e}). Re-initializing...")
                    BrowserController._context = None
                    BrowserController._browser = None
                    BrowserController._page = None
                    return await _do_ensure()

            return BrowserController._page
            
        return await _run_in_playwright(_do_ensure())

    async def navigate(self, url: str) -> str:
        """Navigate to a URL using the Playwright browser."""
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"
        await self.new_tab(url)
        logger.info(f"Navigated to: {url} (via Playwright)")
        return f"Opened {url}"

    async def search_google(self, query: str, browser: str | None = None) -> str:
        search_engine = "Google"
        search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
        
        if browser:
            b_name = browser.lower().strip()
            if b_name == "edge":
                search_engine = "Bing"
                search_url = f"https://www.bing.com/search?q={query.replace(' ', '+')}"
                
        await self.new_tab(search_url)
        return f"Searched {search_engine} for: {query}"

    async def search_youtube(self, query: str) -> str:
        search_url = f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}"
        await self.new_tab(search_url)
        return f"Searched YouTube for: {query}"

    async def fill_form(self, selector: str, value: str) -> None:
        async def _do_fill():
            page = await self._ensure_browser()
            await page.fill(selector, value)
        await _run_in_playwright(_do_fill())

    async def click(self, selector: str) -> None:
        async def _do_click():
            page = await self._ensure_browser()
            await page.click(selector)
        await _run_in_playwright(_do_click())

    async def get_page_title(self) -> str:
        async def _do_get_title():
            page = await self._ensure_browser()
            return await page.title()
        return await _run_in_playwright(_do_get_title())

    async def extract_page_content(self) -> str:
        async def _do_extract():
            page = await self._ensure_browser()
            # Try to get the main content, fallback to body text if necessary
            # Clean up excessive whitespace
            text = await page.inner_text("body")
            import re
            return re.sub(r'\n+', '\n', text).strip()
        return await _run_in_playwright(_do_extract())

    async def _find_page_by_domain(self, domain: str) -> Page | None:
        """Finds a background tab matching the domain."""
        await self._ensure_browser()
        if BrowserController._context:
            for p in BrowserController._context.pages:
                if domain in p.url:
                    return p
        return None

    async def play_pause(self) -> str:
        """Toggle media playback. Works natively on YouTube using 'k'."""
        async def _do_toggle():
            # Find the YouTube tab even if it's in the background!
            target_page = await self._find_page_by_domain("youtube.com")
            if not target_page:
                target_page = await self._ensure_browser()

            url = target_page.url
            if "youtube.com" in url:
                await target_page.keyboard.press("k")
                return "Toggled YouTube playback in background."
            else:
                await target_page.evaluate("document.querySelectorAll('video').forEach(v => v.paused ? v.play() : v.pause())")
                return "Toggled generic video playback."
        return await _run_in_playwright(_do_toggle())

    async def go_back(self) -> str:
        async def _do_back():
            page = await self._ensure_browser()
            await page.go_back()
            return "Navigated back."
        return await _run_in_playwright(_do_back())

    async def click_first_result(self) -> str:
        """Attempts to click the first meaningful search result or video."""
        async def _do_click_first():
            try:
                # Try to find a background tab with search results first
                yt_page = await self._find_page_by_domain("youtube.com/results")
                goog_page = await self._find_page_by_domain("google.com/search")
                
                target_page = yt_page or goog_page or await self._ensure_browser()
                url = target_page.url
                
                if "youtube.com/results" in url:
                    await target_page.locator("ytd-video-renderer a#video-title").first.click(timeout=8000)
                    return "Clicked first YouTube video in background."
                elif "google.com/search" in url:
                    await target_page.locator("div#search a h3").first.click(timeout=8000)
                    return "Clicked first Google result in background."
                else:
                    return "Not on a supported search page."
            except Exception as e:
                import traceback
                from loguru import logger
                logger.error(f"Click error: {traceback.format_exc()}")
                return f"Could not find first result: {type(e).__name__} - {str(e)}"
        return await _run_in_playwright(_do_click_first())

    async def new_tab(self, url: str | None = None) -> str:
        async def _do_new_tab():
            if not BrowserController._context:
                await self._ensure_browser()
            try:
                BrowserController._page = await BrowserController._context.new_page()
            except Exception:
                # If the context was closed manually, re-ensure
                BrowserController._context = None
                BrowserController._browser = None
                await self._ensure_browser()
                # _ensure_browser already creates a page if needed
            # await Stealth().apply_stealth_async(BrowserController._page)
            if url:
                target_url = url
                if not target_url.startswith(("http://", "https://")):
                    target_url = f"https://{target_url}"
                try:
                    await BrowserController._page.goto(target_url, wait_until="commit", timeout=5000)
                except Exception as e:
                    import logging
                    logging.warning(f"Goto timeout or error, but page likely loaded enough: {e}")
            return "New tab opened"
        return await _run_in_playwright(_do_new_tab())

    async def close(self) -> None:
        async def _do_close():
            if BrowserController._browser:
                await BrowserController._browser.close()
                BrowserController._browser = None
                BrowserController._context = None
                BrowserController._page = None
            if BrowserController._playwright:
                await BrowserController._playwright.stop()
                BrowserController._playwright = None
        await _run_in_playwright(_do_close())
