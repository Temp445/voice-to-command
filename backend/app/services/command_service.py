"""
ACE Voice Controller — Command Service
Pure rule-based NLU: regex pattern matching + rapidfuzz fuzzy fallback.
No LLM dependency.

Async Optimizations (v2):
  - Intent pre-index: _regex_match uses a dict keyed by (domain, is_fallback)
    → 1 pass per priority bucket instead of 6 full list scans.
  - Spelling correction offloaded to asyncio.to_thread() — event loop never blocked.
  - Website shortcuts pre-warmed at startup via warm_website_shortcuts().
  - Workflow macro steps execute in parallel when no delay_ms barrier is present.
  - Workflow cache has a 5-minute TTL with background auto-refresh.
"""

import asyncio
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable

try:
    from rapidfuzz import process, fuzz
    _RAPIDFUZZ_AVAILABLE = True
except ImportError:
    _RAPIDFUZZ_AVAILABLE = False

from loguru import logger


@dataclass
class Intent:
    """A registered command intent with its pattern and handler."""
    name: str
    patterns: list[str]
    handler: Callable[..., Awaitable[str]]
    description: str
    examples: list[str] = field(default_factory=list)
    param_names: list[str] = field(default_factory=list)
    domain: str = "global"
    is_fallback: bool = False

    def __post_init__(self):
        self._compiled = [re.compile(p, re.IGNORECASE) for p in self.patterns]

    def match(self, text: str) -> tuple[bool, dict[str, Any]]:
        """Try to match text against all patterns. Returns (matched, params)."""
        for pattern in self._compiled:
            m = pattern.search(text)
            if m:
                return True, m.groupdict()
        return False, {}


# Priority order for regex matching — (domain_key, is_fallback)
# We evaluate non-fallback first, then fallback; current domain first, then global, then others.
_MATCH_PRIORITY = [
    # (is_fallback, domain_key)   ← used as _intent_index lookup
    (False, "current"),   # placeholder: resolved at match time
    (False, "global"),
    (False, "other"),
    (True,  "current"),
    (True,  "global"),
    (True,  "other"),
]

# Workflow cache TTL in seconds (5 minutes)
_CACHE_TTL = 300


class CommandService:
    """
    Parses raw text into an intent + parameters, then executes the handler.

    Matching pipeline (fast → slow):
      Layer 0: User-defined macros (in-memory cache, no DB)
      Layer 0.5: Website shortcuts (pre-warmed at startup)
      Layer 1: Regex matching (pre-indexed by domain+fallback bucket)
      Layer 1.5: Fuzzy matching (rapidfuzz, via thread)
      Layer 2: Semantic matching (FastEmbed, pre-warmed, via thread)
      Layer 3: LLM fallback (only when ALL local layers miss)
    """

    def __init__(self):
        self._intents: list[Intent] = []
        # ── Optimization: pre-indexed intent buckets ──────────────────────────
        # Key: (is_fallback: bool, domain: str)
        # Value: list of intents in that bucket
        # Built incrementally by register(); avoids 6 full-list scans per command.
        self._intent_index: dict[tuple[bool, str], list[Intent]] = {}

        self._custom_shortcuts: dict[str, str] = {}  # phrase → action_type
        self.last_target_app: str = ""
        self.current_domain: str = "desktop"

        # ── Website shortcuts cache ───────────────────────────────────────────
        self._ws_cache_loaded: bool = False
        self._ws_sites: list[dict] = []

    # ── Website Shortcuts Cache ───────────────────────────────────────────────

    async def warm_website_shortcuts(self) -> None:
        """
        Pre-load website shortcuts from Supabase at startup so no DB hit occurs
        during the voice command pipeline. Called once from main.py _background_init.
        """
        try:
            from app.core.supabase_client import supabase_admin, sb_run
            from app.config import settings as _gs
            import json as _json

            if supabase_admin is None:
                return

            # First try the in-memory crm_sites (already restored from DB by settings loader)
            _sites_raw = getattr(_gs, "crm_sites", None)
            if _sites_raw:
                try:
                    _sites = _json.loads(_sites_raw)
                    if _sites:
                        self._ws_sites = _sites
                        self._ws_cache_loaded = True
                        logger.info(f"✅ Website shortcuts pre-warmed: {len(_sites)} site(s) from in-memory settings")
                        return
                except Exception as e:
                    logger.error(f"[{__name__}] {type(e).__name__}: {e}")
                    pass

            # Fallback: fetch directly from DB
            _res = await sb_run(
                lambda: supabase_admin.table("settings").select("crm_sites,crm_url,crm_keywords").order("updated_at", desc=True).limit(1).execute()
            )
            if _res.data:
                _row = _res.data[0]
                _db_raw = _row.get("crm_sites")
                if _db_raw:
                    try:
                        _db_sites = _json.loads(_db_raw)
                        if _db_sites:
                            self._ws_sites = _db_sites
                            _gs.crm_sites = _db_raw
                    except Exception as e:
                        logger.error(f"[{__name__}] {type(e).__name__}: {e}")
                        pass

            self._ws_cache_loaded = True
            logger.info(f"✅ Website shortcuts pre-warmed: {len(self._ws_sites)} site(s) from Supabase")
        except Exception as e:
            logger.warning(f"⚠️ Could not pre-warm website shortcuts: {e}")
            self._ws_cache_loaded = True  # Don't retry on every command

    # ── Intent Registration ───────────────────────────────────────────────────

    def register(self, intent: Intent) -> None:
        self._intents.append(intent)
        # ── Update pre-indexed buckets ────────────────────────────────────────
        bucket_key = (intent.is_fallback, intent.domain)
        self._intent_index.setdefault(bucket_key, []).append(intent)
        logger.debug(f"Registered intent: {intent.name} ({len(intent.patterns)} patterns)")

    def add_custom_shortcut(self, phrase: str, action_type: str) -> None:
        self._custom_shortcuts[phrase.lower().strip()] = action_type

    # ── Main Entry Point ──────────────────────────────────────────────────────

    async def parse_and_execute(self, text: str) -> dict[str, Any]:
        """
        Main entry point.
        Returns a dict with: intent, parameters, result, status, duration_ms.
        """
        text = text.strip()

        # Apply spelling correction off the event loop (SymSpell is CPU-bound).
        # Skip for short commands (≤3 words): app names and simple commands like
        # "open acesoft" are rarely misspelled and spellcheck adds 200–500ms.
        if len(text.split()) > 3:
            try:
                from app.services.spelling_service import spelling_corrector
                corrected_text = await asyncio.to_thread(spelling_corrector.correct, text)
                if corrected_text != text.lower():
                    logger.info(f"Spellcheck: corrected '{text}' -> '{corrected_text}'")
                    text = corrected_text
            except Exception as e:
                logger.warning(f"Failed to run spellcheck: {e}")

        start = time.perf_counter()

        # 1. Check for conversational pending actions
        if hasattr(self, "_pending_action") and self._pending_action:
            pending = self._pending_action
            self._pending_action = None

            if pending.get("intent") == "set_filename":
                if text.lower() in ("cancel", "stop", "nevermind", "abort"):
                    intent_name = "cancel_dialog"
                    params = {"app_name": pending["params"].get("app_name", "")}
                else:
                    intent_name = "set_filename"
                    matched, extracted = self._get_intent("set_filename").match(text)
                    extracted_text = extracted.get("text") if matched and extracted.get("text") else text
                    params = {"text": extracted_text, "app_name": pending["params"].get("app_name", "")}
                return await self._execute_intent(intent_name, params, text, start)

            elif pending.get("intent") == "omni_search_disambiguate":
                params = pending["params"]
                t_lower = text.lower()

                if ("file" in t_lower or "first" in t_lower) and params.get("files"):
                    if len(params["files"]) == 1:
                        from automation.desktop.file_operations import FileOperations
                        FileOperations()._launch_and_focus(params["files"][0], params["query"])
                        return {"intent": "omni_search_disambiguate", "status": "success", "result": f"Opened file {params['files'][0]}", "duration_ms": int((time.perf_counter() - start) * 1000)}
                    else:
                        from pathlib import Path
                        opts = " or ".join(f"{i+1} for {Path(f).name}" for i, f in enumerate(params["files"]))
                        self._pending_action = {"intent": "omni_search_file_select", "params": params}
                        return {"intent": "omni_search_disambiguate", "status": "success", "result": f"I found multiple files. Say {opts}.", "duration_ms": int((time.perf_counter() - start) * 1000)}
                elif ("folder" in t_lower or "directory" in t_lower) and params.get("folders"):
                    if len(params["folders"]) == 1:
                        from automation.desktop.file_operations import FileOperations
                        FileOperations()._launch_and_focus_folder(params["folders"][0], params["query"])
                        return {"intent": "omni_search_disambiguate", "status": "success", "result": f"Opened folder {params['folders'][0]}", "duration_ms": int((time.perf_counter() - start) * 1000)}
                    else:
                        from pathlib import Path
                        opts = " or ".join(f"{i+1} for {Path(f).parent.name}" for i, f in enumerate(params["folders"]))
                        self._pending_action = {"intent": "omni_search_folder_select", "params": params}
                        return {"intent": "omni_search_disambiguate", "status": "success", "result": f"I found multiple folders. Say {opts}.", "duration_ms": int((time.perf_counter() - start) * 1000)}
                elif ("app" in t_lower or "application" in t_lower) and params.get("apps"):
                    from automation.desktop.app_controller import AppController
                    res = await AppController().open_application(params["apps"][0])
                    return {"intent": "omni_search_disambiguate", "status": "success", "result": res, "duration_ms": int((time.perf_counter() - start) * 1000)}
                elif "google" in t_lower or "web" in t_lower or "browser" in t_lower or "online" in t_lower:
                    from automation.browser.browser_controller import BrowserController
                    res = await BrowserController().search_google(params["query"])
                    return {"intent": "omni_search_disambiguate", "status": "success", "result": res, "duration_ms": int((time.perf_counter() - start) * 1000)}
                else:
                    return {"intent": "omni_search_disambiguate", "status": "failed", "result": "I didn't understand your choice. Search cancelled.", "duration_ms": int((time.perf_counter() - start) * 1000)}

            elif pending.get("intent") in ("omni_search_file_select", "omni_search_folder_select"):
                params = pending["params"]
                is_file = pending["intent"] == "omni_search_file_select"
                items = params["files"] if is_file else params["folders"]

                t_lower = text.lower()
                m = re.search(r'\b(1|2|3|one|two|three|first|second|third)\b', t_lower)

                if m:
                    choice = m.group(1)
                    idx = {"1":0, "one":0, "first":0, "2":1, "two":1, "second":1, "3":2, "three":2, "third":2}.get(choice, 0)
                    if idx < len(items):
                        from automation.desktop.file_operations import FileOperations
                        if is_file:
                            FileOperations()._launch_and_focus(items[idx], params["query"])
                        else:
                            FileOperations()._launch_and_focus_folder(items[idx], params["query"])
                        return {"intent": pending["intent"], "status": "success", "result": f"Opened {items[idx]}", "duration_ms": int((time.perf_counter() - start) * 1000)}
                elif "cancel" in t_lower or "stop" in t_lower or "nevermind" in t_lower:
                    return {"intent": pending["intent"], "status": "failed", "result": "Search cancelled.", "duration_ms": int((time.perf_counter() - start) * 1000)}
                elif "google" in t_lower or "web" in t_lower or "browser" in t_lower or "online" in t_lower:
                    from automation.browser.browser_controller import BrowserController
                    res = await BrowserController().search_google(params["query"])
                    return {"intent": "omni_search_disambiguate", "status": "success", "result": res, "duration_ms": int((time.perf_counter() - start) * 1000)}

                return {"intent": pending["intent"], "status": "failed", "result": "Invalid selection. Search cancelled.", "duration_ms": int((time.perf_counter() - start) * 1000)}

            elif pending.get("intent") == "confirm_search_app":
                t_lower = text.lower()
                positive = ["yes", "execute", "yeah", "yep", "sure", "ok", "okay", "search", "go ahead", "do it"]
                if any(w in t_lower for w in positive) and "no" not in t_lower:
                    app_to_search = pending["params"]["app_name"]
                    from automation.browser.browser_controller import BrowserController
                    res = await BrowserController().search_google(app_to_search)
                    return {"intent": "search_google", "status": "success", "result": res, "duration_ms": int((time.perf_counter() - start) * 1000)}
                else:
                    return {"intent": "confirm_search_app", "status": "success", "result": "Okay, search cancelled.", "duration_ms": int((time.perf_counter() - start) * 1000)}
        # 0.5a. Check website shortcuts — uses pre-warmed in-memory cache (no DB hit)
        try:
            import json as _json
            from app.config import settings as _gs

            # Reload cache if it was invalidated or never loaded
            if not self._ws_cache_loaded:
                _sites_raw = getattr(_gs, "crm_sites", None)
                if _sites_raw:
                    try:
                        self._ws_sites = _json.loads(_sites_raw)
                    except Exception as e:
                        logger.error(f"[{__name__}] {type(e).__name__}: {e}")
                        pass
                self._ws_cache_loaded = True
                
            _sites = self._ws_sites

            _text_lower = text.lower().strip()
            _text_lower_no_spaces = _text_lower.replace(" ", "")
            _nav_verbs = ["open", "launch", "go to", "goto", "navigate to", "start", "visit"]
            _has_nav_verb = any(_text_lower.startswith(v) for v in _nav_verbs)
            
            _matched_site_url: str | None = None
            _matched_routes: dict | None = None
            for _site in _sites:
                _kws = [k.strip().lower() for k in _site.get("keywords", "").split(",") if k.strip()]
                for _kw in _kws:
                    _kw_no_spaces = _kw.replace(" ", "")
                    # Match if exact (or very close), OR if it has a navigation verb and contains the keyword
                    if _kw_no_spaces in _text_lower_no_spaces:
                        if _has_nav_verb or len(_text_lower_no_spaces) <= len(_kw_no_spaces) + 8:
                            _matched_site_url = _site.get("url", "")
                            _matched_routes = _site.get("routes", {})
                            break
                if _matched_site_url:
                    break

            if _matched_site_url:
                logger.info(f"Website shortcut matched: '{text}' → {_matched_site_url}")
                from automation.browser.crm_workflows import CRMMacros
                from automation.browser.browser_engine import BrowserEngine
                _mac = CRMMacros(BrowserEngine())
                _nav_result = await _mac.open_crm(text, target_url=_matched_site_url, dynamic_routes=_matched_routes)
                return {
                    "intent": "open_website_shortcut",
                    "parameters": {"url": _matched_site_url},
                    "result": _nav_result,
                    "status": "success",
                    "duration_ms": int((time.perf_counter() - start) * 1000),
                    "is_fallback": False,
                }
        except Exception as _ws_err:
            logger.debug(f"Website shortcut check failed: {_ws_err}")

        # 0.5b. Check if the full text perfectly matches a known compound-aware intent FIRST
        initial_intent, initial_params = self._regex_match(text)
        skip_split = False
        if initial_intent in ["search_youtube", "search_google", "open_website"]:
            skip_split = True

        # 1. Attempt to split into compound commands (e.g., "open notepad and type hello")
        parts = [text]
        if not skip_split:
            if re.search(r'(?i)\s+(?:and|then)\s+', text):
                parts = re.split(r'(?i)\s+(?:and|then)\s+', text)
            else:
                run_on_match = re.match(r"^(open\s+.+?)\s+(type\s+.+|write\s+.+|close\s+.+|maximize\s+.+|minimize\s+.+|create\s+.+)$", text, re.IGNORECASE)
                if run_on_match:
                    parts = [run_on_match.group(1), run_on_match.group(2)]

        if len(parts) > 1:
            valid_intents = []
            for part in parts:
                part = part.strip()
                i_name, params = self._regex_match(part)
                if not i_name:
                    i_name, params = self._fuzzy_match(part)
                if i_name:
                    valid_intents.append((i_name, params))
                else:
                    break

            if len(valid_intents) == len(parts):
                results = []
                # Compound commands stay sequential (step 2 may depend on step 1)
                for i_name, params in valid_intents:
                    try:
                        res_dict = await self._execute_intent(i_name, params, text, start)
                        results.append(str(res_dict.get("result", "")))
                        if res_dict.get("status") == "failed":
                            break
                    except Exception as e:
                        logger.error(f"Handler '{i_name}' raised: {e}")
                        results.append(f"Failed '{i_name}': {e}")
                        break

                duration_ms = int((time.perf_counter() - start) * 1000)
                return {
                    "intent": "compound",
                    "parameters": {"commands": [i for i, _ in valid_intents]},
                    "status": "success" if not results[-1].startswith("Failed") else "failed",
                    "result": " & ".join(results),
                    "duration_ms": duration_ms,
                }

        # 2. Check custom shortcuts first (exact match)
        lower = text.lower()
        if lower in self._custom_shortcuts:
            action = self._custom_shortcuts[lower]
            intent_name = action
            params: dict[str, Any] = {}
            self._pending_action = None
        else:
            intent_name = None
            params = {}
            llm_routed = False

            # Layer 0.9: Implicit Web Click Intercept
            # Prioritize active screen context. If a short phrase exactly or partially
            # matches a visible button/link on the page, click it INSTANTLY.
            if not intent_name and len(text.split()) <= 5:
                try:
                    from automation.browser.browser_controller import BrowserController
                    bc = BrowserController()
                    if bc.engine._context is not None:
                        page = await bc._ensure_page()
                        if page:
                            import re as _re
                            _locators = [
                                # 1. Exact Matches
                                page.get_by_role("button", name=_re.compile(f"^{_re.escape(text)}$", _re.IGNORECASE)),
                                page.get_by_role("link", name=_re.compile(f"^{_re.escape(text)}$", _re.IGNORECASE)),
                                page.get_by_text(text, exact=True),
                                # 2. Partial Matches
                                page.get_by_role("button", name=_re.compile(_re.escape(text), _re.IGNORECASE)),
                                page.get_by_role("link", name=_re.compile(_re.escape(text), _re.IGNORECASE)),
                                page.get_by_text(text, exact=False)
                            ]
                            for _loc in _locators:
                                try:
                                    count = await _loc.count()
                                    for i in range(count):
                                        element = _loc.nth(i)
                                        if await element.is_visible():
                                            await element.click(timeout=1000)
                                            return {
                                                "intent": "implicit_browser_click",
                                                "parameters": {"text": text},
                                                "status": "success",
                                                "result": f"Clicked '{text}' on webpage.",
                                                "duration_ms": int((time.perf_counter() - start) * 1000),
                                                "is_fallback": True,
                                            }
                                except Exception as _e:
                                    logger.debug(f"Implicit click locator failed, trying next: {_e}")
                            
                            # 3. JavaScript Fuzzy Token Match (for colloquial terms like "nov 25 excel" -> "NOVEMBER_2025")
                            _stop_words = {"open", "click", "press", "hit", "the", "a", "an", "on", "file", "app", "link", "button", "document", "excel", "word", "powerpoint", "go", "to", "my", "show", "me", "move", "switch", "navigate", "change", "tab"}
                            _target_words = [w.lower() for w in text.split() if w.lower() not in _stop_words]
                            if _target_words:
                                _js_script = """
                                (targetWords) => {
                                    const elements = Array.from(document.querySelectorAll("a, button, [role='button'], [role='link'], [role='menuitem'], [role='row'], [role='tab']"));
                                    let bestEl = null;
                                    let bestScore = 0;
                                    for (const el of elements) {
                                        const style = window.getComputedStyle(el);
                                        if (style.display === 'none' || style.visibility === 'hidden' || el.offsetWidth === 0) continue;
                                        
                                        const text = el.innerText ? el.innerText.toLowerCase() : '';
                                        if (!text) continue;
                                        
                                        let score = 0;
                                        for (const w of targetWords) {
                                            if (text.includes(w)) score++;
                                        }
                                        if (score > bestScore) {
                                            bestScore = score;
                                            bestEl = el;
                                        }
                                    }
                                    if (bestEl && bestScore >= Math.max(1, targetWords.length - 1)) {
                                        bestEl.click();
                                        return true;
                                    }
                                    return false;
                                }
                                """
                                try:
                                    _clicked = False
                                    for _frame in page.frames:
                                        try:
                                            if await _frame.evaluate(_js_script, _target_words):
                                                _clicked = True
                                                break
                                        except Exception:
                                            pass
                                            
                                    if _clicked:
                                        return {
                                            "intent": "implicit_browser_click",
                                            "parameters": {"text": text},
                                            "status": "success",
                                            "result": f"Clicked closest match for '{text}' via fuzzy logic.",
                                            "duration_ms": int((time.perf_counter() - start) * 1000),
                                            "is_fallback": True,
                                        }
                                except Exception as _e:
                                    logger.debug(f"Implicit click JS fuzzy match failed: {_e}")
                            
                            # Explicitly fail generic commands if not found, to prevent LLM hallucinations
                            _lower = text.lower()
                            if _lower in ["sign in", "login", "log in", "log out", "logout", "sign out", "submit"] or _lower.startswith("sign in") or _lower.startswith("log in"):
                                return {
                                    "intent": "implicit_browser_click",
                                    "parameters": {"text": text},
                                    "status": "failed",
                                    "result": f"Unable to find '{text}' on the current webpage.",
                                    "duration_ms": int((time.perf_counter() - start) * 1000),
                                    "is_fallback": True,
                                }
                except Exception as _e:
                    logger.debug(f"Implicit web click intercept failed: {_e}")

            # Layer 0.95: Implicit Web Type Intercept (Single Credential)
            if not intent_name:
                import re as _re
                _cred_match = _re.match(r"^(email|username|password)\s+(.+)$", text, _re.IGNORECASE)
                if _cred_match:
                    try:
                        from automation.browser.browser_controller import BrowserController
                        bc = BrowserController()
                        if bc.engine._context is not None:
                            page = await bc._ensure_page()
                            if page:
                                _field_type = _cred_match.group(1).lower()
                                _val = _cred_match.group(2).strip()
                                
                                if _field_type in ["email", "username"]:
                                    _loc = page.locator("input[type='email'], input[name*='email' i], input[placeholder*='email' i], input[name*='user' i]").first
                                else:
                                    _loc = page.locator("input[type='password'], input[name*='pass' i], input[placeholder*='pass' i]").first
                                
                                if await _loc.count() > 0:
                                    await _loc.fill(_val)
                                    await _loc.press("Enter")
                                    return {
                                        "intent": "implicit_browser_type",
                                        "parameters": {"field": _field_type, "value": _val},
                                        "status": "success",
                                        "result": f"Filled {_field_type} and submitted.",
                                        "duration_ms": int((time.perf_counter() - start) * 1000),
                                        "is_fallback": True,
                                    }
                    except Exception as _e:
                        logger.debug(f"Implicit web type intercept failed: {_e}")

            # Layer 0.96: Implicit Web Type Intercept (Pure Numbers / OTP)
            if not intent_name:
                _digits_only = text.replace(" ", "").replace("-", "")
                if _digits_only.isdigit() and len(_digits_only) >= 4:
                    try:
                        from automation.browser.browser_controller import BrowserController
                        bc = BrowserController()
                        if bc.engine._context is not None:
                            page = await bc._ensure_page()
                            if page:
                                # Playwright types into the active DOM element, ignoring OS focus.
                                # Delay added to allow React/Angular inputs to auto-advance focus.
                                await page.keyboard.type(_digits_only, delay=50)
                                return {
                                    "intent": "implicit_browser_type_otp",
                                    "parameters": {"value": _digits_only},
                                    "status": "success",
                                    "result": f"Typed numeric code '{_digits_only}' into active field.",
                                    "duration_ms": int((time.perf_counter() - start) * 1000),
                                    "is_fallback": True,
                                }
                    except Exception as _e:
                        logger.debug(f"Implicit web type OTP intercept failed: {_e}")
                    
                    # If browser fails or is not active, route to desktop type_text
                    intent_name = "type_text"
                    params = {"text": _digits_only}

            # Layer 1: Native regex matching (uses pre-indexed buckets)
            if not intent_name:
                intent_name, params = self._regex_match(text)

            # Layer 1.5: Fuzzy fallback
            if not intent_name:
                intent_name, params = self._fuzzy_match(text)

            # Layer 2: Semantic fallback (FastEmbed — offloaded to thread)
            if not intent_name:
                intent_name, params = await self._semantic_match(text)

            # 5. Pronoun detection: force LLM context resolution for pronouns
            if not llm_routed:
                has_pronouns = False
                if intent_name:
                    for val in params.values():
                        if isinstance(val, str) and re.fullmatch(r'(?i)(it|this|that|them|here)', val.strip()):
                            has_pronouns = True
                            break
                else:
                    has_pronouns = bool(re.search(r'\b(it|this|that|them|here)\b', text, re.IGNORECASE))

                from app.services.llm.llm_service import llm_service
                if has_pronouns and llm_service.is_ready:
                    intent_name = None
                    params = {}
                    logger.info("Pronouns detected needing resolution. Bypassing native regex to allow LLM context resolution.")

            # 4. Handle pending disambiguation if no new regex matched
            if not intent_name and getattr(self, "_pending_action", None):
                action = self._pending_action
                intent_name = action["intent"]
                params = action["params"]
                params["disambiguation"] = text
                self._pending_action = None
            else:
                self._pending_action = None
                if not intent_name:
                    intent_name, params = self._fuzzy_match(text)
                if not intent_name:
                    intent_name, params = await self._semantic_match(text)

            # Layer 3: LLM fallback — ONLY when ALL local layers failed
            from app.services.llm.llm_service import llm_service
            if not intent_name and llm_service.is_ready:
                llm_result = await llm_service.classify_intent(text, self.list_intents())
                if llm_result:
                    intent_name = llm_result.get("intent")
                    if intent_name:
                        llm_routed = True
                    params.update(llm_result.get("params", {}))

        if not intent_name:
            # Dynamic browser automation fallback
            try:
                from automation.browser.browser_controller import BrowserController
                bc = BrowserController()
                if bc.engine._context is not None:
                    from automation.browser.browser_controller import VoiceBrowserCommands
                    browser_cmd = VoiceBrowserCommands()
                    browser_res = await asyncio.wait_for(browser_cmd.execute(text), timeout=20.0)
                    if browser_res and not browser_res.startswith("Command not recognized"):
                        return {
                            "intent": "dynamic_browser_command_fallback",
                            "parameters": {"text": text},
                            "status": "success" if "Failed" not in browser_res else "failed",
                            "result": browser_res,
                            "duration_ms": int((time.perf_counter() - start) * 1000),
                        }
            except Exception as browser_e:
                logger.debug(f"Dynamic browser fallback failed: {browser_e}")

            from app.services.llm.llm_service import llm_service
            if llm_service.is_ready and llm_service._mode == "always_on":
                intent_name = "ask_llm"
                params = {"question": text}
            else:
                return {
                    "intent": None,
                    "parameters": {},
                    "status": "failed",
                    "result": f"Sorry, I didn't understand: '{text}'",
                    "duration_ms": int((time.perf_counter() - start) * 1000),
                }

        res_dict = await self._execute_intent(intent_name, params, text, start)
        if locals().get("llm_routed", False):
            res_dict["routed_by_llm"] = True
        return res_dict

    # ── Intent Execution ──────────────────────────────────────────────────────

    async def _execute_intent(self, intent_name: str, params: dict, text: str, start: float) -> dict[str, Any]:
        intent = self._get_intent(intent_name)
        if not intent:
            return {"intent": intent_name, "parameters": params, "status": "failed",
                    "result": "Intent handler not found", "duration_ms": int((time.perf_counter() - start) * 1000)}

        app_target = params.get("app") or params.get("app_name")
        if app_target:
            self.last_target_app = app_target

        if intent_name in ("dont_save", "save_file", "cancel_dialog", "submit", "type_text", "set_filename") and not params.get("app_name"):
            if getattr(self, "last_target_app", ""):
                params["app_name"] = self.last_target_app

        if "text" not in params:
            params["text"] = text

        try:
            result = await intent.handler(**params)
            duration_ms = int((time.perf_counter() - start) * 1000)

            if isinstance(result, str):
                if result.startswith("MULTIPLE_MATCHES:"):
                    self._pending_action = {"intent": intent_name, "params": params}
                    result = result.replace("MULTIPLE_MATCHES:", "").strip()
                elif result.startswith("PENDING_FILENAME:"):
                    self._pending_action = {"intent": "set_filename", "params": {"app_name": params.get("app_name", "")}}
                    result = result.replace("PENDING_FILENAME:", "").strip()
                elif result.startswith("PENDING_SEARCH_APP:"):
                    app_to_search = result.replace("PENDING_SEARCH_APP:", "").strip()
                    self._pending_action = {"intent": "confirm_search_app", "params": {"app_name": app_to_search}}
                    result = f"I can't find the application {app_to_search}. Should I search for it on the web?"

            from app.services.llm.llm_service import llm_service
            if llm_service.is_ready and intent_name not in ("ask_llm", "ask_and_type"):
                llm_service.add_to_history("user", text)
                llm_service.add_to_history("assistant", str(result))

            if intent.domain != "global":
                self.current_domain = intent.domain

            return {
                "intent": intent_name,
                "parameters": params,
                "status": "success",
                "result": result,
                "duration_ms": duration_ms,
            }
        except Exception as e:
            error_type = type(e).__name__
            if error_type in ("AppNotFound", "AutomationError", "FileNotFoundError"):
                logger.warning(f"OS-level handler '{intent_name}' failed with {error_type}. Falling back to Browser Agent.")
                try:
                    from automation.browser.browser_controller import VoiceBrowserCommands
                    browser_cmd = VoiceBrowserCommands()
                    browser_res = await asyncio.wait_for(browser_cmd.execute(text), timeout=20.0)
                    if browser_res and not browser_res.startswith("Command not recognized"):
                        return {
                            "intent": "dynamic_browser_command_fallback",
                            "parameters": {"text": text},
                            "status": "success" if "Failed" not in browser_res else "failed",
                            "result": browser_res,
                            "duration_ms": int((time.perf_counter() - start) * 1000),
                        }
                except Exception as browser_e:
                    logger.debug(f"Browser fallback also failed: {browser_e}")

            error_type = type(e).__name__
            error_str = str(e)

            if "BrowserType.launch_persistent_context" in error_str or "locked" in error_str.lower():
                user_msg = "The web browser failed to open because it is locked by another process. Please try again."
            elif "object has no attribute" in error_str or "NoneType" in error_str:
                user_msg = "I encountered a temporary software error while executing this. Please try again."
            elif "net::ERR_" in error_str or "Timeout" in error_type:
                user_msg = "Network connection failed or timed out while trying to reach the website."
            elif "not found" in error_str.lower():
                user_msg = "I couldn't find the requested application or element."
            else:
                user_msg = f"Sorry, I couldn't complete that action. ({error_type})"

            logger.error(f"Handler '{intent_name}' raised: {e}")
            return {
                "intent": intent_name,
                "parameters": params,
                "status": "failed",
                "result": user_msg,
                "duration_ms": int((time.perf_counter() - start) * 1000),
            }

    # ── Regex Matching (Pre-indexed) ──────────────────────────────────────────

    def _regex_match(self, text: str) -> tuple[str | None, dict]:
        """
        Match text against registered intents using the pre-built index.

        Priority order (matches the original 6-pass logic, now O(N/6) avg):
          1. Current-domain, non-fallback
          2. Global, non-fallback
          3. Other-domain, non-fallback
          4. Current-domain, fallback
          5. Global, fallback
          6. Other-domain, fallback
        """
        other_domains = set(self._intent_index.keys()) - {
            (False, self.current_domain), (False, "global"),
            (True,  self.current_domain), (True,  "global"),
        }
        priority_keys = [
            (False, self.current_domain),
            (False, "global"),
            *[(False, d) for _, d in other_domains if not _],   # other non-fallback
            (True,  self.current_domain),
            (True,  "global"),
            *[(True,  d) for _, d in other_domains if _],       # other fallback
        ]
        # Simpler, correct ordering:
        buckets_ordered = [
            (False, self.current_domain),
            (False, "global"),
        ]
        # Add remaining non-fallback domains
        for key in self._intent_index:
            if not key[0] and key[1] not in (self.current_domain, "global"):
                if key not in buckets_ordered:
                    buckets_ordered.append(key)
        # Add fallback domains in same order
        buckets_ordered.append((True, self.current_domain))
        buckets_ordered.append((True, "global"))
        for key in self._intent_index:
            if key[0] and key[1] not in (self.current_domain, "global"):
                if key not in buckets_ordered:
                    buckets_ordered.append(key)

        for bucket_key in buckets_ordered:
            for intent in self._intent_index.get(bucket_key, []):
                matched, params = intent.match(text)
                if matched:
                    return intent.name, params

        return None, {}

    # ── Fuzzy Matching ────────────────────────────────────────────────────────

    def _fuzzy_match(self, text: str, threshold: int = 85) -> tuple[str | None, dict]:
        """Match against examples using rapidfuzz. Returns best intent above threshold."""
        if not _RAPIDFUZZ_AVAILABLE:
            return None, {}

        candidates: list[tuple[str, str]] = []
        for intent in self._intents:
            if len(intent.param_names) == 0:
                for example in intent.examples:
                    candidates.append((example, intent.name))

        if not candidates:
            return None, {}

        examples_only = [c[0] for c in candidates]
        result = process.extractOne(text, examples_only, scorer=fuzz.QRatio)

        if result and result[1] >= threshold:
            matched_example = result[0]
            intent_name = next(c[1] for c in candidates if c[0] == matched_example)
            logger.debug(f"Fuzzy matched '{text}' → '{intent_name}' (score={result[1]})")
            return intent_name, {}

        return None, {}

    # ── Semantic Matching ─────────────────────────────────────────────────────

    async def _semantic_match(self, text: str) -> tuple[str | None, dict[str, Any]]:
        """Layer 2: FastEmbed Semantic Routing — offloaded to thread pool."""
        from app.services.semantic_router import semantic_router
        if not semantic_router._is_ready:
            await asyncio.to_thread(semantic_router.initialize, self._intents)

        intent_name, score = await asyncio.to_thread(semantic_router.semantic_match, text, 0.82)
        if intent_name:
            return intent_name, {}
        return None, {}

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _get_intent(self, name: str) -> Intent | None:
        return next((i for i in self._intents if i.name == name), None)

    def list_intents(self) -> list[dict]:
        return [
            {
                "name": i.name,
                "description": i.description,
                "examples": i.examples,
                "param_names": i.param_names,
            }
            for i in self._intents
        ]


# Singleton
command_service = CommandService()