import asyncio
from loguru import logger
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

class ACEBrowserLauncher:
    """Helper class to manage Chrome lifecycle"""
    @staticmethod
    def launch(port: int = 9222):
        from automation.ace_browser.ace_launch_chrome import main, is_cdp_open, kill_chrome_processes, get_default_chrome_profile, launch_chrome
        import time
        if is_cdp_open(port):
            logger.info("Chrome already open with CDP")
            return True
        logger.info("Restarting Chrome with CDP...")
        kill_chrome_processes()
        launch_chrome(get_default_chrome_profile(), port)
        for _ in range(10):
            if is_cdp_open(port):
                return True
            time.sleep(1)
        return False

class ACEBrowserController:
    """Controls an already-running Chrome instance via CDP."""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._playwright = None
            cls._instance._browser = None
            cls._instance._context = None
            cls._instance._page = None
        return cls._instance

    async def connect(self, port: int = 9222) -> bool:
        """Connect to the running Chrome instance."""
        if self._browser and self._browser.is_connected():
            return True
            
        if not self._playwright:
            self._playwright = await async_playwright().start()
            
        try:
            logger.info(f"Connecting to Chrome via CDP on port {port}...")
            self._browser = await self._playwright.chromium.connect_over_cdp(f"http://localhost:{port}")
            self._context = self._browser.contexts[0]
            self._page = self._context.pages[0] if self._context.pages else await self._context.new_page()
            return True
        except Exception as e:
            logger.error(f"Failed to connect via CDP: {e}")
            return False

    async def disconnect(self):
        """Detach from Chrome without closing it."""
        if self._browser:
            await self._browser.close() # Closes the CDP connection, not the browser
            self._browser = None
            self._context = None
            self._page = None

    async def _ensure_page(self) -> Page:
        if not self._browser or not self._browser.is_connected():
            success = await self.connect()
            if not success:
                raise Exception("Could not connect to Chrome.")
        
        if not self._page or self._page.is_closed():
            try:
                self._page = await self._context.new_page()
            except Exception:
                await self.connect()
                
        return self._page

    # --- Tab Management ---
    async def get_all_tabs(self):
        await self._ensure_page()
        return self._context.pages

    async def switch_to_tab(self, index: int):
        await self._ensure_page()
        pages = self._context.pages
        if 0 <= index < len(pages):
            self._page = pages[index]
            await self._page.bring_to_front()
            return f"Switched to tab {index + 1}"
        return f"Tab index {index + 1} out of bounds"

    async def switch_to_tab_by_url(self, partial_url: str):
        await self._ensure_page()
        for p in self._context.pages:
            if partial_url.lower() in p.url.lower():
                self._page = p
                await self._page.bring_to_front()
                return f"Switched to tab matching {partial_url}"
        return f"No tab found matching {partial_url}"

    async def new_tab(self, url: str = None):
        await self._ensure_page()
        self._page = await self._context.new_page()
        if url:
            await self.navigate(url)
        return "Opened new tab"

    # --- Navigation ---
    async def navigate(self, url: str):
        page = await self._ensure_page()
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"
        await page.goto(url, wait_until="commit", timeout=10000)
        return f"Navigated to {url}"

    async def go_back(self):
        page = await self._ensure_page()
        await page.go_back()
        return "Navigated back"

    async def go_forward(self):
        page = await self._ensure_page()
        await page.go_forward()
        return "Navigated forward"

    async def refresh(self):
        page = await self._ensure_page()
        await page.reload()
        return "Refreshed page"

    # --- Clicking ---
    async def click(self, selector: str):
        page = await self._ensure_page()
        await page.click(selector)
        return "Clicked element"

    async def click_text(self, text: str):
        page = await self._ensure_page()
        await page.get_by_text(text).first.click()
        return f"Clicked '{text}'"

    async def double_click(self):
        page = await self._ensure_page()
        await page.mouse.dblclick(0, 0) # Fallback if no selector provided
        return "Double clicked"

    async def right_click(self):
        page = await self._ensure_page()
        await page.mouse.click(0, 0, button="right")
        return "Right clicked"
        
    async def hover(self, selector: str):
        page = await self._ensure_page()
        await page.hover(selector)
        return "Hovered element"

    # --- Scrolling ---
    async def scroll(self, direction: str, amount: int = 500):
        page = await self._ensure_page()
        sign = 1 if direction == "down" else -1
        await page.mouse.wheel(0, sign * amount)
        return f"Scrolled {direction}"

    async def scroll_to_top(self):
        page = await self._ensure_page()
        await page.evaluate("window.scrollTo(0, 0)")
        return "Scrolled to top"

    async def scroll_to_bottom(self):
        page = await self._ensure_page()
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        return "Scrolled to bottom"

    async def scroll_element(self, selector: str):
        page = await self._ensure_page()
        await page.locator(selector).scroll_into_view_if_needed()
        return "Scrolled to element"

    # --- Typing ---
    async def type_text(self, selector: str, text: str):
        page = await self._ensure_page()
        await page.fill(selector, text)
        return f"Typed text"

    async def press_key(self, key: str):
        page = await self._ensure_page()
        await page.keyboard.press(key)
        return f"Pressed {key}"

    async def search_google(self, query: str):
        await self.new_tab()
        await self.navigate(f"https://www.google.com/search?q={query}")
        return f"Searched Google for {query}"

    async def search_youtube(self, query: str):
        await self.new_tab()
        await self.navigate(f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}")
        return f"Searched YouTube for {query}"

    # --- Media ---
    async def play_pause(self):
        return await self.media_play_pause()
    async def media_play_pause(self):
        page = await self._ensure_page()
        if "youtube.com" in page.url:
            await page.keyboard.press("k")
        elif "spotify.com" in page.url:
            await page.locator("[data-testid='control-button-playpause']").click()
        else:
            await page.keyboard.press("Space")
        return "Toggled playback"

    async def youtube_seek(self, seconds: int):
        page = await self._ensure_page()
        key = "l" if seconds > 0 else "j"
        await page.keyboard.press(key)
        return "Seeked video"

    async def youtube_fullscreen(self):
        page = await self._ensure_page()
        await page.keyboard.press("f")
        return "Toggled fullscreen"

    async def youtube_mute(self):
        page = await self._ensure_page()
        await page.keyboard.press("m")
        return "Toggled mute"

    async def youtube_next(self):
        page = await self._ensure_page()
        await page.keyboard.press("Shift+N")
        return "Next video"

    # --- Utilities ---
    async def get_page_title(self):
        page = await self._ensure_page()
        return await page.title()

    async def extract_page_content(self):
        return await self.get_page_text()

    async def click_first_result(self):
        page = await self._ensure_page()
        try:
            # Try YouTube first
            if "youtube.com/results" in page.url:
                await page.locator("ytd-video-renderer a#video-title").first.click()
            # Try Google
            elif "google.com/search" in page.url:
                await page.locator("div#search a h3").first.click()
            else:
                return "Not on a supported search page"
            return "Clicked first result"
        except Exception as e:
            return f"Failed to click first result: {e}"

    async def run_js(self, script: str):
        page = await self._ensure_page()
        return await page.evaluate(script)

    async def get_page_text(self):
        page = await self._ensure_page()
        return await page.inner_text("body")

    async def screenshot(self, path: str):
        page = await self._ensure_page()
        await page.screenshot(path=path)
        return f"Screenshot saved to {path}"

    async def wait_for(self, selector: str):
        page = await self._ensure_page()
        await page.wait_for_selector(selector)
        return "Selector found"

    async def find_and_click(self, text_or_selector: str):
        page = await self._ensure_page()
        try:
            await page.click(text_or_selector, timeout=2000)
        except Exception:
            try:
                await page.get_by_text(text_or_selector).first.click(timeout=2000)
            except Exception:
                return "Failed to find element to click"
        return "Clicked element"

class ACEVoiceBrowserCommands:
    """Maps voice transcripts to controller methods."""
    def __init__(self):
        self.ctrl = ACEBrowserController()

    async def execute(self, transcript: str) -> str:
        transcript = transcript.lower().strip()
        
        # --- Tab Management ---
        if "new tab" in transcript:
            return await self.ctrl.new_tab()
        if "close tab" in transcript or "close this tab" in transcript:
            page = await self.ctrl._ensure_page()
            await page.close()
            return "Closed tab"
        if "show all tabs" in transcript:
            tabs = await self.ctrl.get_all_tabs()
            return f"There are {len(tabs)} tabs open."
        if "switch to tab" in transcript:
            import re
            match = re.search(r'\d+', transcript)
            if match:
                idx = int(match.group()) - 1
                return await self.ctrl.switch_to_tab(idx)
            # Try to switch by domain/name
            domain = transcript.replace("switch to the", "").replace("switch to", "").replace("tab", "").strip()
            return await self.ctrl.switch_to_tab_by_url(domain)

        # --- Scrolling ---
        if "scroll to the bottom" in transcript or "scroll to bottom" in transcript:
            return await self.ctrl.scroll_to_bottom()
        if "scroll to the top" in transcript or "scroll to top" in transcript:
            return await self.ctrl.scroll_to_top()
        if "scroll down" in transcript:
            return await self.ctrl.scroll("down")
        if "scroll up" in transcript:
            return await self.ctrl.scroll("up")

        # --- Media & YouTube Controls ---
        if "play" in transcript or "pause" in transcript:
            return await self.ctrl.media_play_pause()
        if "mute" in transcript:
            return await self.ctrl.youtube_mute()
        if "fullscreen" in transcript:
            return await self.ctrl.youtube_fullscreen()
        if "skip ahead" in transcript or "skip forward" in transcript:
            return await self.ctrl.youtube_seek(10)
        if "go back 10" in transcript:
            return await self.ctrl.youtube_seek(-10)
        if "next video" in transcript:
            return await self.ctrl.youtube_next()

        # --- Navigation ---
        if "go back" in transcript:
            return await self.ctrl.go_back()
        if "refresh" in transcript or "reload" in transcript:
            return await self.ctrl.refresh()
        if transcript.startswith("open "):
            url = transcript.replace("open ", "").strip()
            return await self.ctrl.navigate(url)
        if transcript.startswith("search for "):
            query = transcript.replace("search for ", "").strip()
            return await self.ctrl.search_google(query)

        # --- Dynamic DOM Agent (Clicking, Typing, Interaction) ---
        # If it doesn't match a static command, route it to the LLM agent
        try:
            from automation.ace_browser.dom_agent import DOMAgent
            page = await self.ctrl._ensure_page()
            agent = DOMAgent(page)
            return await agent.execute_intent(transcript)
        except Exception as e:
            logger.error(f"DOM Agent failed: {e}")
            return "Command not recognized and dynamic agent failed."
