import asyncio
from loguru import logger
from automation.browser.browser_engine import BrowserEngine

class BrowserLauncher:
    """Helper class to manage Chrome lifecycle (Deprecated, use BrowserEngine)"""
    @staticmethod
    async def launch(port: int = 9222) -> bool:
        logger.warning("BrowserLauncher.launch is deprecated. BrowserEngine manages its own lifecycle.")
        return True

class BrowserController:
    """Controls Chrome instance. (Deprecated wrapper, uses BrowserEngine)"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.engine = BrowserEngine()
        return cls._instance

    async def connect(self, port: int = 9222) -> bool:
        """Connect to the running Chrome instance."""
        try:
            await self.engine.ensure_browser()
            return True
        except Exception as e:
            logger.error(f"Failed to connect via engine: {e}")
            return False

    async def disconnect(self):
        """Detach from Chrome without closing it."""
        await self.engine.close_browser()

    async def _ensure_page(self):
        return await self.engine.ensure_browser()

    # --- Tab Management ---
    async def get_all_tabs(self):
        return await self.engine.get_all_tabs()

    async def switch_to_tab(self, index: int):
        return await self.engine.switch_tab(index)

    async def switch_to_last_tab(self):
        return await self.engine.switch_tab_last()

    async def close_all_tabs(self):
        return await self.engine.close_all_tabs()

    async def switch_to_tab_by_url(self, partial_url: str):
        return await self.engine.switch_tab_by_url(partial_url)

    async def new_tab(self, url: str = None):
        return await self.engine.new_tab(url)

    # --- Navigation ---
    async def navigate(self, url: str):
        return await self.engine.navigate(url)

    async def go_back(self):
        return await self.engine.go_back()

    async def go_forward(self):
        return await self.engine.go_forward()

    async def refresh(self):
        return await self.engine.refresh()

    # --- Clicking ---
    async def click(self, selector: str):
        return await self.engine.click(selector)

    async def click_text(self, text: str):
        return await self.engine.click_text(text)

    async def double_click(self):
        return await self.engine.double_click()

    async def right_click(self):
        return await self.engine.right_click()

    async def hover(self, selector: str):
        return await self.engine.hover(selector)

    # --- Scrolling ---
    async def scroll(self, direction: str, amount: int = 500):
        return await self.engine.scroll(direction, amount)
        
    async def scroll_amount(self, direction: str, magnitude: str):
        return await self.engine.scroll_amount(direction, magnitude)

    async def scroll_to_top(self):
        return await self.engine.scroll_to_top()

    async def scroll_to_bottom(self):
        return await self.engine.scroll_to_bottom()

    async def scroll_element(self, selector: str):
        # Implementation could be added to engine if needed
        pass

    # --- Typing ---
    async def type_text(self, selector: str, text: str):
        return await self.engine.type_text(selector, text, human_like=True)

    async def press_key(self, key: str):
        return await self.engine.press_key(key)
        
    async def clipboard_action(self, action: str):
        if action == "copy": return await self.engine.clipboard_copy()
        elif action == "paste": return await self.engine.clipboard_paste()
        elif action == "cut": return await self.engine.clipboard_cut()
        elif action == "select_all": return await self.engine.clipboard_select_all()
        return "Unknown clipboard action"

    async def search_google(self, query: str):
        return await self.engine.search_google(query)

    async def search_youtube(self, query: str):
        return await self.engine.search_youtube(query)

    # --- Media ---
    async def play_pause(self):
        return await self.engine.play_pause()
    async def media_play_pause(self):
        return await self.engine.play_pause()

    async def youtube_seek(self, seconds: int):
        page = await self.engine.ensure_browser()
        script = f"""
            let v = document.querySelector('video');
            if (v) {{ v.currentTime += {seconds}; }}
        """
        for frame in page.frames:
            try: await frame.evaluate(script)
            except: pass
        return "Seeked video"

    async def youtube_fullscreen(self):
        page = await self.engine.ensure_browser()
        script = """
            let btn = document.querySelector('.ytp-fullscreen-button');
            if (btn) btn.click();
            else {
                let v = document.querySelector('video');
                if (v && v.requestFullscreen) v.requestFullscreen();
            }
        """
        for frame in page.frames:
            try: await frame.evaluate(script)
            except: pass
        return "Toggled fullscreen"

    async def youtube_mute(self):
        page = await self.engine.ensure_browser()
        script = """
            let v = document.querySelector('video');
            if (v) { v.muted = !v.muted; }
            else {
                let btn = document.querySelector('.ytp-mute-button');
                if (btn) btn.click();
            }
        """
        for frame in page.frames:
            try: await frame.evaluate(script)
            except: pass
        return "Toggled mute"

    async def youtube_next(self):
        page = await self.engine.ensure_browser()
        await page.keyboard.press("Shift+N")
        return "Next video"

    # --- Utilities ---
    async def get_page_title(self):
        return await self.engine.get_page_title()

    async def extract_page_content(self):
        return await self.engine.extract_page_content()

    async def click_first_result(self):
        return await self.engine.click_first_result()

    async def run_js(self, script: str):
        page = await self.engine.ensure_browser()
        return await page.evaluate(script)

    async def get_page_text(self):
        return await self.engine.extract_page_content()

    async def screenshot(self, path: str, full_page: bool = False):
        import os
        filename = os.path.basename(path)
        res_path = await self.engine.screenshot(filename, full_page)
        return f"Screenshot saved to {res_path}"

    async def clear_marks(self):
        return await self.engine.clear_marks()
        
    async def restart_browser(self):
        return await self.engine.restart_browser()

    async def wait_for(self, selector: str):
        return await self.engine.wait_for(selector)

    async def set_window_state(self, state: str):
        return await self.engine.set_window_state(state)

    async def download_file(self):
        return await self.engine.download_file()

    async def upload_file(self):
        return await self.engine.upload_file()

    async def find_and_click(self, text_or_selector: str):
        try:
            return await self.engine.click(text_or_selector)
        except Exception:
            try:
                return await self.engine.click_text(text_or_selector)
            except Exception:
                return "Failed to find element to click"


class VoiceBrowserCommands:
    """Maps voice transcripts to controller methods."""
    def __init__(self):
        self.ctrl = BrowserController()
        
        try:
            from automation.browser.crm_workflows import CRMMacros
            self.crm = CRMMacros(self.ctrl.engine)
        except ImportError:
            self.crm = None

    async def execute(self, transcript: str) -> str:
        transcript = transcript.lower().strip()
        
        # --- CRM Workflows ---
        if self.crm:
            if "open my crm" in transcript or "open crm" in transcript or "open ace crm" in transcript:
                return await self.crm.open_crm()
            if "log in" in transcript or "login" in transcript:
                return await self.crm.login()
            
            # Dynamic creation handling
            if "new " in transcript or "create " in transcript or "add " in transcript or "make " in transcript or "generate " in transcript:
                import re
                m = re.search(r'(?:create|add|make|generate)(?:\s+(?:a\s+)?(?:new\s+)?)?\s+(lead|quote|quotation|contact|customer|account|opportunity|order|product|task)', transcript)
                if not m:
                    m = re.search(r'new\s+(lead|quote|quotation|contact|customer|account|opportunity|order|product|task)', transcript)
                if m:
                    entity = m.group(1)
                    if entity == "quotation": entity = "quote"
                    if entity == "customer": entity = "account"
                    return await self.crm.create_entity(entity)
            
            # Dynamic module navigation
            import re
            m = re.search(r'\b(leads|contacts|opportunities|accounts|customers|quotes|quotations|orders|products|dashboard|tasks|reports|home)\b', transcript)
            if m and not ("new " in transcript or "create " in transcript or "add " in transcript or "make " in transcript or "generate " in transcript or "search " in transcript or "edit " in transcript or "update " in transcript or "assign " in transcript):
                if "go to" in transcript or "open" in transcript or "show" in transcript or transcript == m.group(1):
                    mod = m.group(1)
                    if mod == "quotations": mod = "quotes"
                    if mod == "customers": mod = "accounts"
                    if mod == "home": mod = "dashboard"
                    return await self.crm.navigate_to_module(mod)
                    
            # Search Handling
            if "search " in transcript:
                import re
                m = re.search(r'search\s+(lead|opportunity|customer|order|quote|task|account|contact)\s+(.+)', transcript)
                if m:
                    entity = m.group(1)
                    query = m.group(2)
                    if entity == "customer": entity = "account"
                    return await self.crm.search_record(entity, query)
                    
            # Grid Interaction Handling
            if "first " in transcript or "top " in transcript:
                import re
                m = re.search(r'(?:open|select|click)\s+(?:first|top)\s+(?:record|row|lead|opportunity|customer|order|quote|task|account|contact)', transcript)
                if m:
                    return await self.crm.open_first_record()
                    
            # Edit / Update / Assign Handling via DOMAgent fallback
            if "edit " in transcript or "assign " in transcript or "update " in transcript:
                from automation.browser.dom_agent import DOMAgent
                page = await self.ctrl._ensure_page()
                agent = DOMAgent(page)
                return await agent.execute_intent(transcript)
                    
            if "cancel" in transcript:
                return await self.ctrl.find_and_click("Cancel")
        
        # --- Tab Management ---
        if "new tab" in transcript:
            return await self.ctrl.new_tab()
        if "close all tabs" in transcript:
            return await self.ctrl.close_all_tabs()
        if "close tab" in transcript or "close this tab" in transcript:
            return await self.ctrl.close_tab()
        if "show all tabs" in transcript:
            tabs = await self.ctrl.get_all_tabs()
            return f"There are {len(tabs)} tabs open."
        if "switch to last tab" in transcript:
            return await self.ctrl.switch_to_last_tab()
        if "switch to tab" in transcript:
            import re
            match = re.search(r'\d+', transcript)
            if match:
                idx = int(match.group()) - 1
                return await self.ctrl.switch_to_tab(idx)
            domain = transcript.replace("switch to the", "").replace("switch to", "").replace("tab", "").strip()
            return await self.ctrl.switch_to_tab_by_url(domain)

        # --- Scrolling ---
        if "scroll to the bottom" in transcript or "scroll to bottom" in transcript:
            return await self.ctrl.scroll_to_bottom()
        if "scroll to the top" in transcript or "scroll to top" in transcript:
            return await self.ctrl.scroll_to_top()
        if "scroll down a little" in transcript:
            return await self.ctrl.scroll_amount("down", "little")
        if "scroll up a little" in transcript:
            return await self.ctrl.scroll_amount("up", "little")
        if "scroll down" in transcript:
            return await self.ctrl.scroll("down")
        if "scroll up" in transcript:
            return await self.ctrl.scroll("up")

        # --- Window & Marking ---
        if "restart browser" in transcript:
            return await self.ctrl.restart_browser()
        if "clear highlights" in transcript or "remove marks" in transcript:
            return await self.ctrl.clear_marks()

        # --- Keyboard & Clipboard ---
        if "press enter" in transcript: return await self.ctrl.press_key("Enter")
        if "press escape" in transcript: return await self.ctrl.press_key("Escape")
        if "press tab" in transcript: return await self.ctrl.press_key("Tab")
        if "select all" in transcript: return await self.ctrl.clipboard_action("select_all")
        if "copy" in transcript and "text" in transcript: return await self.ctrl.clipboard_action("copy")
        if "paste" in transcript: return await self.ctrl.clipboard_action("paste")
        if "cut" in transcript: return await self.ctrl.clipboard_action("cut")

        # --- Media & YouTube Controls ---
        import re
        if re.fullmatch(r'(?:play|pause)(?:\s+(?:the\s+)?(?:video|music|song|playback))?', transcript):
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
        import re
        search_m = re.match(r"(?:search|google)\s+(?:for\s+)?(.+)", transcript)
        if search_m:
            return await self.ctrl.search_google(search_m.group(1).strip())

        # --- Deterministic Fallbacks (Zero LLM Tokens) ---
        try:
            page = await self.ctrl._ensure_page()
            import re
            
            # 1. Exact "click <text>"
            if transcript.startswith("click ") and len(transcript) > 6:
                target_text = transcript[6:].strip()
                locators = [
                    page.get_by_role("button", name=re.compile(f"^{re.escape(target_text)}$", re.IGNORECASE)),
                    page.get_by_role("link", name=re.compile(f"^{re.escape(target_text)}$", re.IGNORECASE)),
                    page.locator(f"text=\"{target_text}\"").filter(has_not=page.locator("body, html, main"))
                ]
                for loc in locators:
                    try:
                        if await loc.count() > 0:
                            await loc.first.click(timeout=1000)
                            return f"Clicked '{target_text}' (deterministic)"
                    except Exception:
                        pass

            # 2. Exact "type <text> into <field>"
            type_match = re.match(r"(?:type|enter|write)\s+(.+?)\s+(?:in|into|to|on)\s+(?:the\s+)?(.+)", transcript)
            if type_match:
                value = type_match.group(1).strip()
                field = type_match.group(2).strip()
                locators = [
                    page.get_by_label(re.compile(f"^{re.escape(field)}$", re.IGNORECASE)),
                    page.get_by_placeholder(re.compile(f"^{re.escape(field)}$", re.IGNORECASE)),
                ]
                for loc in locators:
                    try:
                        if await loc.count() > 0:
                            await loc.first.fill(value, timeout=1000)
                            return f"Typed '{value}' into '{field}' (deterministic)"
                    except Exception:
                        pass
        except Exception as e:
            logger.debug(f"Deterministic fallback failed: {e}")

        # --- Dynamic DOM Agent (Clicking, Typing, Interaction) ---
        try:
            from automation.browser.dom_agent import DOMAgent
            page = await self.ctrl._ensure_page()
            agent = DOMAgent(page)
            return await agent.execute_intent(transcript)
        except Exception as e:
            logger.error(f"DOM Agent failed: {e}")
            return "Command not recognized and dynamic agent failed."
