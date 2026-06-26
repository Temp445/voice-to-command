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
        return await self.engine.get_active_page()

    # --- Tab Management ---
    async def get_all_tabs(self):
        return await self.engine.get_all_tabs()

    async def switch_to_tab(self, index: int):
        return await self.engine.switch_tab(index)

    async def switch_to_last_tab(self):
        return await self.engine.switch_tab_last()

    async def switch_to_next_tab(self):
        return await self.engine.switch_tab_next()

    async def switch_to_prev_tab(self):
        return await self.engine.switch_tab_prev()

    async def close_all_tabs(self):
        return await self.engine.close_all_tabs()

    async def switch_to_tab_by_url(self, partial_url: str):
        return await self.engine.switch_tab_by_url(partial_url)

    async def new_tab(self, url: str = None):
        return await self.engine.new_tab(url)

    async def navigate(self, url: str, new_tab: bool = False):
        return await self.engine.navigate(url, new_tab=new_tab)

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

    async def search_google(self, query: str, new_tab: bool = False):
        return await self.engine.search_google(query, new_tab=new_tab)

    async def search_youtube(self, query: str, new_tab: bool = False):
        return await self.engine.search_youtube(query, new_tab=new_tab)

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
            except Exception as e:
                logger.error(f"[{__name__}] {type(e).__name__}: {e}")
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
            except Exception as e:
                logger.error(f"[{__name__}] {type(e).__name__}: {e}")
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
            except Exception as e:
                logger.error(f"[{__name__}] {type(e).__name__}: {e}")
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

    async def click_search_result(self, index: int = 0):
        return await self.engine.click_search_result(index)

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
        is_selector = text_or_selector.startswith((".", "#", "[")) or ":" in text_or_selector
        try:
            if is_selector:
                return await self.engine.click(text_or_selector)
            else:
                return await self.engine.click_text(text_or_selector)
        except Exception as e:
            logger.error(f"[{__name__}] {type(e).__name__}: {e}")
            try:
                if is_selector:
                    return await self.engine.click_text(text_or_selector)
                else:
                    return await self.engine.click(text_or_selector)
            except Exception as e:
                logger.error(f"[{__name__}] {type(e).__name__}: {e}")
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
        transcript_lower = transcript.lower().strip()
        transcript = transcript.strip()   # preserve original casing for credentials

        # ── Credential-pair shortcut ─────────────────────────────────────────
        # If the transcript is JUST "email , password" (no login/CRM keywords),
        # go directly to DOMAgent.fill_form — skip the LLM router entirely.
        import re as _re
        _raw_tokens = transcript.split()
        _email_cands = [t.strip(',.') for t in _raw_tokens if '@' in t and '.' in t.split('@')[-1]]
        _stop = {'type','enter','write','fill','and','with','the','into','in','to'}
        _pass_cands = [
            t.strip(',.')
            for t in _raw_tokens
            if t.strip(',.') not in _email_cands
            and t.strip(',.').lower() not in _stop
            and len(t.strip(',.')) > 3
        ]
        # Only activate when: there is an email-like token AND a password-like token
        # AND no login/CRM navigation verbs (those have their own handlers below)
        _cred_action_verbs = _re.search(r'\b(login|log in|log into|sign in|sign into|authenticate)\b', transcript_lower)
        if _email_cands and _pass_cands and not _cred_action_verbs:
            try:
                page = await self.ctrl._ensure_page()
                email_val = _email_cands[0]
                pass_val = _pass_cands[-1]
                
                # Fill Email
                email_loc = page.locator("input[type='email'], input[name*='email' i], input[placeholder*='email' i]").first
                if await email_loc.count() > 0:
                    await email_loc.fill(email_val)
                    
                # Fill Password
                pass_loc = page.locator("input[type='password'], input[name*='pass' i], input[placeholder*='pass' i]").first
                if await pass_loc.count() > 0:
                    await pass_loc.fill(pass_val)
                    # Attempt to press enter to submit
                    await pass_loc.press("Enter")
                    
                return "Filled credentials and submitted."
            except Exception as _e:
                logger.debug(f"Credential shortcut failed, continuing: {_e}")
        # ── End credential-pair shortcut ─────────────────────────────────────

        # --- Resolve the active page ONCE per command ----------------------------
        # TabRegistry is the SINGLE source-of-truth. It is updated within ~1ms
        # of any tab switch (event-driven via CDP Target.activatedTarget), so
        # this always returns the tab the user is currently looking at.
        try:
            from automation.browser.tab_registry import tab_registry as _tab_reg
            active_page = _tab_reg.get_active()
            # Guard: if the registry returned a closed page, unregister it and
            # fall back to the engine's detection pipeline.
            if active_page is not None and active_page.is_closed():
                _tab_reg.unregister(active_page)
                active_page = None
        except Exception as _page_err:
            logger.warning(f"TabRegistry lookup failed in execute(): {_page_err}")
            active_page = None

        # Fallback: engine heuristics (visibilityState → hasFocus → CDP REST)
        if active_page is None:
            try:
                active_page = await self.ctrl.engine.get_active_page()
            except Exception as _page_err:
                logger.warning(f"Could not resolve active page: {_page_err}")
                active_page = None
        active_url = active_page.url if active_page else ""

        # Site-guard helpers — used below to decide if CRM macros are applicable.
        from app.config import settings as _settings
        import json as _json
        try:
            _all_sites = _json.loads(_settings.crm_sites) if _settings.crm_sites else []
        except Exception:
            _all_sites = []
        if not _all_sites:
            _all_sites = [{"url": _settings.crm_url, "keywords": _settings.crm_keywords}]
        _crm_hosts = set()
        for _s in _all_sites:
            _su = _s.get("url", "")
            if _su:
                _crm_hosts.add(_su.replace("https://", "").replace("http://", "").split("/")[0].lower())
        _active_tab_is_crm = any(h and h in active_url.lower() for h in _crm_hosts)

        # --- Deterministic Fallbacks (Zero LLM Tokens) ---
        try:
            page = active_page
            import re
            
            # 1. Exact "click <text>" or matching a short phrase directly to a button
            target_text = transcript_lower
            if transcript_lower.startswith("click ") and len(transcript_lower) > 6:
                target_text = transcript_lower[6:].strip()
                
            if len(target_text) > 0 and len(target_text.split()) <= 4:
                locators = [
                    # 1. Exact Matches
                    page.get_by_role("button", name=re.compile(f"^{re.escape(target_text)}$", re.IGNORECASE)),
                    page.get_by_role("link", name=re.compile(f"^{re.escape(target_text)}$", re.IGNORECASE)),
                    page.get_by_text(target_text, exact=True),
                    # 2. Partial Matches
                    page.get_by_role("button", name=re.compile(re.escape(target_text), re.IGNORECASE)),
                    page.get_by_role("link", name=re.compile(re.escape(target_text), re.IGNORECASE)),
                    page.get_by_text(target_text, exact=False)
                ]
                for loc in locators:
                    try:
                        count = await loc.count()
                        for i in range(count):
                            element = loc.nth(i)
                            if await element.is_visible():
                                await element.click(timeout=1000)
                                return f"Clicked '{target_text}'"
                    except Exception as e:
                        logger.error(f"[{__name__}] {type(e).__name__}: {e}")
                        pass

            # 2. Exact "type <text> into <field>"
            type_match = re.match(r"(?:type|enter|write)\s+(.+?)\s+(?:in|into|to|on)\s+(?:the\s+)?(.+)", transcript_lower)
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
                            return f"Typed '{value}' into '{field}'"
                    except Exception as e:
                        logger.error(f"[{__name__}] {type(e).__name__}: {e}")
                        pass
        except Exception as e:
            logger.debug(f"Deterministic fallback failed: {e}")

        # --- Toggle / Enable / Disable Handler ---
        # Handles: "enable device 1", "disable device 2", "toggle background auto-sync"
        _toggle_match = re.match(
            r'^(?P<action>enable|disable|toggle|turn\s+on|turn\s+off|activate|deactivate)\s+(?P<target>.+)$',
            transcript_lower.strip()
        )
        if _toggle_match and active_page:
            _action = _toggle_match.group("action")
            _target = _toggle_match.group("target").strip()
            _want_enabled = _action in ("enable", "turn on", "activate")
            _want_disabled = _action in ("disable", "turn off", "deactivate")
            try:
                # Strategy: find any checkbox/toggle/switch near text matching the target
                _clicked = await active_page.evaluate("""
                    (args) => {
                        const { target, wantEnabled, wantDisabled } = args;

                        // Helper: does this element or its ancestors contain the target text?
                        function nearText(el) {
                            const row = el.closest('tr, li, div.device, div.card, div.item, section, article, [class*="row"], [class*="card"], [class*="item"], [class*="device"]');
                            const scope = row || el.parentElement?.parentElement || document;
                            return scope.innerText?.toLowerCase().includes(target);
                        }

                        // 1. Look for role=switch or input[type=checkbox] near the target text
                        const toggles = Array.from(document.querySelectorAll(
                            'input[type=checkbox], [role=switch], [role=checkbox], button[class*="toggle" i], button[class*="switch" i], span[class*="toggle" i], div[class*="toggle" i]'
                        ));
                        
                        for (const t of toggles) {
                            if (!nearText(t)) continue;
                            const isChecked = t.checked ?? t.getAttribute('aria-checked') === 'true' 
                                ?? t.classList.contains('active') ?? t.classList.contains('enabled');
                            
                            if (wantEnabled && isChecked) return 'already_on';
                            if (wantDisabled && !isChecked) return 'already_off';
                            t.click();
                            return 'clicked';
                        }
                        
                        // 2. Look for any element with visible text "DISABLED" or "ENABLED" near the target
                        const labels = Array.from(document.querySelectorAll('*')).filter(el => {
                            const txt = el.innerText?.trim().toUpperCase();
                            return (txt === 'DISABLED' || txt === 'ENABLED') && el.children.length === 0;
                        });
                        for (const lbl of labels) {
                            if (!nearText(lbl)) continue;
                            const txt = lbl.innerText?.trim().toUpperCase();
                            if (wantEnabled && txt === 'ENABLED') return 'already_on';
                            if (wantDisabled && txt === 'DISABLED') return 'already_off';
                            // click the parent toggle container
                            const clickTarget = lbl.closest('button, [role=switch], label, [class*="toggle" i]') || lbl.parentElement;
                            clickTarget?.click();
                            return 'clicked_label';
                        }
                        
                        return 'not_found';
                    }
                """, {"target": _target, "wantEnabled": _want_enabled, "wantDisabled": _want_disabled})

                if _clicked == "clicked" or _clicked == "clicked_label":
                    state = "enabled" if _want_enabled else ("disabled" if _want_disabled else "toggled")
                    return f"Successfully {state} '{_target}'."
                elif _clicked == "already_on":
                    return f"'{_target}' is already enabled."
                elif _clicked == "already_off":
                    return f"'{_target}' is already disabled."
                else:
                    logger.info(f"Toggle handler could not find '{_target}' on page — falling through to DOMAgent.")
            except Exception as _te:
                logger.warning(f"Toggle handler error: {_te}")
        
        # --- CRM Workflows ---
        if self.crm:
            from app.config import settings
            import json as _json

            # ── Multi-site keyword matching ───────────────────────────────────
            # Build list of (url, keywords) from crm_sites JSON; fall back to
            # the single crm_url/crm_keywords if crm_sites is empty or invalid.
            _matched_url: str | None = None
            try:
                _all_sites = _json.loads(settings.crm_sites) if settings.crm_sites else []
            except Exception as e:
                logger.error(f"[{__name__}] {type(e).__name__}: {e}")
                _all_sites = []
            if not _all_sites:
                _all_sites = [{"url": settings.crm_url, "keywords": settings.crm_keywords}]

            for _site in _all_sites:
                _site_keys = [k.strip().lower() for k in _site.get("keywords", "").split(",") if k.strip()]
                if any(key in transcript_lower for key in _site_keys if key):
                    _matched_url = _site.get("url", settings.crm_url)
                    break

            # Built-in synonym pattern — catches generic 'open crm', 'go to crm', etc.
            _builtin_crm_pattern = re.compile(
                r'\b(launch|start|run|go\s+to|open|load|boot|bring\s+up)\s+(my\s+)?(ace\s+)?crm\b'
                r'|\bopen\s+my\s+crm\b'
                r'|\bcrm\b',
                re.IGNORECASE
            )
            if _matched_url is None and bool(_builtin_crm_pattern.search(transcript)):
                _matched_url = settings.crm_url   # fall back to primary for generic matches

            crm_match = _matched_url is not None

            # ── Navigation bypass — always open/navigate even from non-CRM tab ──
            # Commands like "open crm", "go to crm", "launch crm" are navigation
            # intents — they should ALWAYS call open_crm() regardless of the active
            # tab.  Only in-page interaction commands (create, edit, change view …)
            # need the site-guard below.
            _nav_only_pattern = re.compile(
                r'^\s*(?:open|launch|start|go\s+to|goto|load|bring\s+up|navigate\s+to)\s+'
                r'(?:my\s+)?(?:ace\s+)?crm\s*$',
                re.IGNORECASE
            )
            _is_crm_navigation = bool(_nav_only_pattern.match(transcript_lower))

            if crm_match and _is_crm_navigation:
                logger.info(
                    f"CRM navigation command detected ('{transcript}') — "
                    f"bypassing site-guard and calling open_crm()"
                )
                return await self.crm.open_crm(transcript, target_url=_matched_url)

            # ── Explicit CRM Auth Bypass ─────────────────────────────────────────
            # "sign in crm", "log in crm", "login to crm" — these commands explicitly
            # name the CRM, so they must ALWAYS go to crm.login() regardless of which
            # tab is currently active.  crm.login() uses _crm_page() internally to
            # find the CRM tab, so it never touches the Payroll tab.
            _explicit_crm_auth = bool(re.search(
                r'\b(?:sign\s*in|log\s*in|login|signin)\b.{0,20}\bcrm\b'
                r'|\bcrm\b.{0,20}\b(?:sign\s*in|log\s*in|login|signin)\b',
                transcript_lower
            ))
            if _explicit_crm_auth:
                logger.info(
                    f"Explicit CRM auth detected ('{transcript}') — "
                    f"bypassing site-guard and routing directly to crm.login()"
                )
                return await self.crm.login()

            # ── Site-Guard ──────────────────────────────────────────────────────
            # If the active tab is NOT a CRM page, in-page interaction commands
            # (create, edit, change view, search …) must not run on the wrong tab —
            # instead fall through to DOMAgent on the actual active tab.
            if crm_match and not _active_tab_is_crm:
                logger.info(
                    f"CRM keyword matched but active tab is '{active_url}' — "
                    f"routing to DOMAgent on active tab instead of CRM."
                )
                if active_page:
                    from automation.browser.dom_agent import DOMAgent
                    _agent = DOMAgent(active_page)
                    return await _agent.execute_intent(transcript)
                return "CRM keyword matched but no active browser tab found."

            if crm_match:
                return await self.crm.open_crm(transcript, target_url=_matched_url)
                
            # Direct Login Credential Extraction
            cred_match = re.search(r"(?:email|username)(?:\s+is)?[\s\:]+([^\s\,]+)(?:[\,\s]+and[\,\s]+|[\,\s]+)password(?:\s+is)?[\s\:]+([^\s]+)", transcript, re.IGNORECASE)
            if cred_match:
                return await self.crm.login(username=cred_match.group(1), password=cred_match.group(2))
                
            _login_signup_keywords = ["log in", "login", "sign in", "sign up", "signup", "register", "create account"]
            is_search_or_url = transcript.startswith("search ") or re.search(r"https?://", transcript)
            if any(w in transcript for w in _login_signup_keywords) and not is_search_or_url:
                page = active_page or await self.ctrl._ensure_page()
                url = await self.ctrl.engine.get_url()
                from app.config import settings
                crm_host = settings.crm_url.replace("https://", "").replace("http://", "").split("/")[0] if settings.crm_url else ""
                is_on_crm = bool(url and crm_host and crm_host in url)
                wants_crm = "crm" in transcript_lower
                
                if (wants_crm or is_on_crm) and not any(w in transcript for w in ["sign up", "signup", "register"]):
                    return await self.crm.login()
                else:
                    # Generic login/signup: click button on the current page.
                    # Build ordered list: prioritize spoken keywords first.
                    search_words = []
                    for w in _login_signup_keywords:
                        if w in transcript:
                            search_words.append(w)
                    for w in _login_signup_keywords + ["submit"]:
                        if w not in search_words:
                            search_words.append(w)

                    for btn_text in search_words:
                        locators = [
                            page.get_by_role("button", name=re.compile(f"^{re.escape(btn_text)}$", re.IGNORECASE)),
                            page.get_by_role("link", name=re.compile(f"^{re.escape(btn_text)}$", re.IGNORECASE)),
                            page.locator(f"text=\"{btn_text}\"").filter(has_not=page.locator("body, html, main"))
                        ]
                        for loc in locators:
                            try:
                                if await loc.count() > 0:
                                    await loc.first.click(timeout=1000)
                                    return f"Clicked '{btn_text}'"
                            except Exception as e:
                                logger.error(f"[{__name__}] {type(e).__name__}: {e}")
                                pass
                    # If not found, fall back to DOMAgent clicking the element on this page
                    from automation.browser.dom_agent import DOMAgent
                    agent = DOMAgent(page)
                    return await agent.execute_intent(transcript)


            _logout_triggers = [
                    "log out", "logout", "sign out", "signout",
                    "sign off", "log off",
                ]
            if any(t in transcript_lower for t in _logout_triggers):
                page = active_page or await self.ctrl._ensure_page()
                url = await self.ctrl.engine.get_url()
                from app.config import settings
                crm_host = settings.crm_url.replace("https://", "").replace("http://", "").split("/")[0] if settings.crm_url else ""
                is_on_crm = bool(url and crm_host and crm_host in url)
                wants_crm = "crm" in transcript_lower

                if wants_crm or is_on_crm:
                    return await self.crm.logout()
                else:
                    # Smart multi-layer logout: profile menu detection, DOM scan, DOMAgent fallback
                    from automation.browser.logout_handler import LogoutHandler
                    handler = LogoutHandler(page)
                    return await handler.smart_logout()
            
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
                
                # Generic search fallback for the browser
                m_gen = re.match(r"^search\s+(?:for\s+)?(.+)$", transcript)
                if m_gen:
                    query = m_gen.group(1).strip()
                    
                    tab_match = re.search(r'(?:\s+)?in\s+(?:a\s+|the\s+)?new\s+tab$', query, re.IGNORECASE)
                    if tab_match:
                        query = query[:tab_match.start()].strip()
                        if not query:
                            return await self.ctrl.new_tab()
                        await self.ctrl.new_tab()
                        
                    # If query looks like a URL, navigate directly
                    if re.match(r"^(?:https?://)?[\w\-\.]+\.\w{2,}(?:/\S*)?$", query):
                        url_to_open = query if query.startswith("http") else f"https://{query}"
                        return await self.ctrl.engine.navigate(url_to_open)

                    url = await self.ctrl.engine.get_url()
                    if url and "youtube.com" in url:
                        return await self.ctrl.engine.search_youtube(query)
                    return await self.ctrl.engine.search_google(query)
                    
            # Grid Interaction Handling
            if "first " in transcript or "top " in transcript:
                import re
                m = re.search(r'(?:open|select|click)\s+(?:first|top)\s+(?:record|row|lead|opportunity|customer|order|quote|task|account|contact)', transcript)
                if m:
                    return await self.crm.open_first_record()
                    
            # DOMAgent Interaction Fallback (Edit, Change, Modify, Type, Fill, Select, Check, Upload, etc.)
            import re
            # Guard: skip DOMAgent for date-range commands like "set date 4 may 2026 to 10 jun 2026"
            # or "filter date 1-4-2026 to 20-5-2026" — these are handled by the browser_date_filter
            # intent and DOMAgent would get confused by the date syntax.
            _is_date_filter_cmd = bool(re.search(
                r'\b(?:filter|set|change|update|from|between)\b.{1,30}\b\d{1,2}\b.{1,20}\bto\b.{1,20}\b\d{4}\b',
                transcript, re.IGNORECASE
            ))
            if not _is_date_filter_cmd and re.search(r'\b(edit|assign|update|change|modify|revise|correct|alter|fix|replace|type|fill|enter|write|put|set|input|select|choose|pick|grab|check|uncheck|tick|untick|mark|unmark|deselect|clear|upload|attach|enable|disable|toggle|activate|deactivate|switch|turn\s+on|turn\s+off)\b', transcript, re.IGNORECASE):
                from automation.browser.dom_agent import DOMAgent
                page = active_page or await self.ctrl._ensure_page()
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


        # --- Dynamic DOM Agent (Clicking, Typing, Interaction) ---
        try:
            from automation.browser.dom_agent import DOMAgent
            page = active_page or await self.ctrl.engine.get_active_page()
            agent = DOMAgent(page)
            import asyncio
            return await asyncio.wait_for(agent.execute_intent(transcript), timeout=20.0)
        except Exception as e:
            logger.error(f"DOM Agent failed: {e}")
            return "Command not recognized and dynamic agent failed."
