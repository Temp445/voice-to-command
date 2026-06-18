"""
ACE Voice Controller — Command Service
Pure rule-based NLU: regex pattern matching + rapidfuzz fuzzy fallback.
No LLM dependency.
"""

import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable
try:
    from rapidfuzz import process, fuzz
    _RAPIDFUZZ_AVAILABLE = True
except ImportError:
    _RAPIDFUZZ_AVAILABLE = False
    logger.warning("rapidfuzz not installed — fuzzy command matching disabled. Install with: pip install rapidfuzz")
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


class CommandService:
    """
    Parses raw text into an intent + parameters, then executes the handler.
    Uses regex first, rapidfuzz fuzzy matching as fallback.
    """

    def __init__(self):
        self._intents: list[Intent] = []
        self._custom_shortcuts: dict[str, str] = {}  # phrase → action_type
        self.last_target_app: str = ""
        self.current_domain: str = "desktop"
        # In-memory workflow cache — loaded once on startup, refreshed on change
        self._workflows_cache: list[dict] = []

    async def refresh_workflows_cache(self) -> None:
        """Fetch all workflows from Supabase once and store in memory.
        Call this at startup and after any workflow create/update/delete.
        """
        try:
            from app.core.supabase_client import supabase_admin, sb_run
            if supabase_admin is None:
                return
            res = await sb_run(lambda: supabase_admin.table("workflows").select("*").execute())
            self._workflows_cache = res.data or []
            logger.info(f"✅ Workflows cache refreshed: {len(self._workflows_cache)} macros ready")
        except Exception as e:
            logger.warning(f"⚠️ Could not refresh workflows cache: {e}")

    def refresh_in_background(self) -> None:
        """Fire-and-forget cache refresh — call after any workflow change."""
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.refresh_workflows_cache())
        except RuntimeError:
            pass  # No running loop — cache will be refreshed on next request

    def register(self, intent: Intent) -> None:
        self._intents.append(intent)
        logger.debug(f"Registered intent: {intent.name} ({len(intent.patterns)} patterns)")

    def add_custom_shortcut(self, phrase: str, action_type: str) -> None:
        self._custom_shortcuts[phrase.lower().strip()] = action_type

    async def parse_and_execute(self, text: str) -> dict[str, Any]:
        """
        Main entry point.
        Returns a dict with: intent, parameters, result, status, duration_ms.
        """
        text = text.strip()
        
        # Apply spelling correction on the input text before routing
        try:
            from app.services.spelling_service import spelling_corrector
            corrected_text = spelling_corrector.correct(text)
            if corrected_text != text.lower():
                logger.info(f"Spellcheck: corrected '{text}' -> '{corrected_text}'")
                text = corrected_text
        except Exception as e:
            logger.warning(f"Failed to run spellcheck: {e}")

        start = time.perf_counter()

        # 0. Check for user-defined Macros/Workflows — read from in-memory cache (no DB hit)
        try:
            if self._workflows_cache:
                for wf in self._workflows_cache:
                    trigger_phrase = wf.get("trigger_phrase")
                    if trigger_phrase and trigger_phrase.lower() in text.lower():
                        logger.info(f"Matched workflow macro: {wf.get('name')}")
                        results = []
                        import asyncio
                        steps = wf.get("steps", [])
                        for step in steps:
                            action = step.get("action", "")
                            if step.get("delay_ms", 0):
                                await asyncio.sleep(step["delay_ms"] / 1000)
                            if "macro_loop" not in action:
                                r = await self.parse_and_execute(action)
                                results.append(r.get("result", ""))

                        return {
                            "intent": "execute_workflow",
                            "parameters": {"name": wf.get("name")},
                            "result": f"Executed macro '{wf.get('name')}'. Steps: {len(results)}",
                            "status": "success",
                            "duration_ms": (time.perf_counter() - start) * 1000,
                            "is_fallback": False
                        }
        except Exception as e:
            logger.error(f"Failed to check macros: {e}")

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
                    
                # Skip normal classification and go straight to execution
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
                        self._pending_action = {
                            "intent": "omni_search_file_select",
                            "params": params
                        }
                        return {"intent": "omni_search_disambiguate", "status": "success", "result": f"I found multiple files. Say {opts}.", "duration_ms": int((time.perf_counter() - start) * 1000)}
                elif ("folder" in t_lower or "directory" in t_lower) and params.get("folders"):
                    if len(params["folders"]) == 1:
                        from automation.desktop.file_operations import FileOperations
                        FileOperations()._launch_and_focus_folder(params["folders"][0], params["query"])
                        return {"intent": "omni_search_disambiguate", "status": "success", "result": f"Opened folder {params['folders'][0]}", "duration_ms": int((time.perf_counter() - start) * 1000)}
                    else:
                        from pathlib import Path
                        opts = " or ".join(f"{i+1} for {Path(f).parent.name}" for i, f in enumerate(params["folders"]))
                        self._pending_action = {
                            "intent": "omni_search_folder_select",
                            "params": params
                        }
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
                
                # Escape hatches if the user changes their mind
                elif "cancel" in t_lower or "stop" in t_lower or "nevermind" in t_lower:
                    return {"intent": pending["intent"], "status": "failed", "result": "Search cancelled.", "duration_ms": int((time.perf_counter() - start) * 1000)}
                elif "google" in t_lower or "web" in t_lower or "browser" in t_lower or "online" in t_lower:
                    from automation.browser.browser_controller import BrowserController
                    res = await BrowserController().search_google(params["query"])
                    return {"intent": "omni_search_disambiguate", "status": "success", "result": res, "duration_ms": int((time.perf_counter() - start) * 1000)}
                
                return {"intent": pending["intent"], "status": "failed", "result": "Invalid selection. Search cancelled.", "duration_ms": int((time.perf_counter() - start) * 1000)}

        # 0.5a. Check website shortcuts — user-defined keywords that open a URL.
        # This MUST run before open_app regex so "open acesoft" hits the website,
        # not the application handler.
        try:
            from app.config import settings as _gs
            import json as _json

            # ── Build the sites list ──────────────────────────────────────────
            # Tier 1: in-memory crm_sites (set at startup or on settings PATCH)
            _sites: list = []
            _sites_raw = getattr(_gs, "crm_sites", None)
            if _sites_raw:
                try:
                    _sites = _json.loads(_sites_raw)
                except Exception:
                    pass

            # Tier 2: If in-memory has only 1 entry (the default), try fetching
            # the latest crm_sites value from Supabase.  We cache the result on
            # the command_service instance to avoid a DB round-trip every command.
            if len(_sites) <= 1 and not getattr(self, "_ws_cache_loaded", False):
                try:
                    from app.core.supabase_client import supabase_admin, sb_run
                    if supabase_admin is not None:
                        _res = await sb_run(
                            lambda: supabase_admin.table("settings").select("crm_url,crm_keywords").order("updated_at", desc=True).limit(1).execute()
                        )
                        if _res.data:
                            _row = _res.data[0]
                            # crm_sites column may not exist yet — fall back to crm_url/crm_keywords
                            _db_raw = _row.get("crm_sites")
                            if _db_raw:
                                try:
                                    _db_sites = _json.loads(_db_raw)
                                    if _db_sites:
                                        _sites = _db_sites
                                        _gs.crm_sites = _db_raw
                                except Exception:
                                    pass
                        self._ws_cache_loaded = True
                        logger.debug(f"Website shortcuts loaded from DB: {len(_sites)} site(s)")
                except Exception as _db_err:
                    logger.debug(f"Could not load website shortcuts from DB: {_db_err}")
                    self._ws_cache_loaded = True  # Don't retry every command


            # ── Match keywords ────────────────────────────────────────────────
            _text_lower = text.lower()
            _matched_site_url: str | None = None
            for _site in _sites:
                _kws = [k.strip().lower() for k in _site.get("keywords", "").split(",") if k.strip()]
                if any(_kw and _kw in _text_lower for _kw in _kws):
                    _matched_site_url = _site.get("url", "")
                    break

            if _matched_site_url:
                logger.info(f"Website shortcut matched: '{text}' → {_matched_site_url}")
                from automation.browser.crm_workflows import CRMMacros
                from automation.browser.browser_engine import BrowserEngine
                _mac = CRMMacros(BrowserEngine())
                _nav_result = await _mac.open_crm(text, target_url=_matched_site_url)
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
                # Handle run-on sentences WITHOUT conjunctions like "open notepad type hello"
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
                    break  # If any part fails to match an intent, fall back to single command logic

            # Only execute as compound if ALL parts match valid independent intents
            if len(valid_intents) == len(parts):
                results = []
                for i_name, params in valid_intents:
                    try:
                        # Use _execute_intent to ensure state tracking and auto-injection works for each sub-command
                        res_dict = await self._execute_intent(i_name, params, text, start)
                        results.append(str(res_dict.get("result", "")))
                        if res_dict.get("status") == "failed":
                            break
                    except Exception as e:
                        logger.error(f"Handler '{i_name}' raised: {e}")
                        results.append(f"Failed '{i_name}': {e}")
                        break  # Stop sequential execution if one fails

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

            # Layer 1: Native regex matching
            intent_name, params = self._regex_match(text)

            # Layer 1.5: Fuzzy fallback
            if not intent_name:
                intent_name, params = self._fuzzy_match(text)
                
            # Layer 2: Semantic fallback (FastEmbed)
            if not intent_name:
                intent_name, params = await self._semantic_match(text)

            # 5. Pronoun detection: If any extracted parameter is exactly a pronoun, force LLM context resolution.
            # Only do this if it wasn't ALREADY routed by the LLM.
            if not llm_routed:
                has_pronouns = False
                if intent_name:
                    for val in params.values():
                        if isinstance(val, str) and re.fullmatch(r'(?i)(it|this|that|them|here)', val.strip()):
                            has_pronouns = True
                            break
                else:
                    # If no regex matched, we might still want LLM to catch "close it" if it didn't even match regex
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
                # Clear pending action since we either got a new command or no pending action exists
                self._pending_action = None
                # 6. Fuzzy fallback (Layer 1.5) if no regex match
                if not intent_name:
                    intent_name, params = self._fuzzy_match(text)
                    
                # 7. Semantic fallback (Layer 2) if fuzzy match also failed
                if not intent_name:
                    intent_name, params = await self._semantic_match(text)

            # 6. LLM fallback (Layer 3) — classify intent via AI ONLY when local layers failed
            from app.services.llm.llm_service import llm_service
            if not intent_name and llm_service.is_ready:
                llm_result = await llm_service.classify_intent(text, self.list_intents())
                if llm_result:
                    intent_name = llm_result.get("intent")
                    if intent_name:
                        llm_routed = True
                    # Merge any parameters the LLM contextually extracted
                    params.update(llm_result.get("params", {}))

        if not intent_name:
            # If still no match after all layers, check if there is an active browser session
            # to run the dynamic browser automation fallback.
            try:
                from automation.browser.browser_controller import BrowserController
                bc = BrowserController()
                if bc.engine._context is not None:
                    from automation.browser.browser_controller import VoiceBrowserCommands
                    browser_cmd = VoiceBrowserCommands()
                    browser_res = await browser_cmd.execute(text)
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

            # If still no match after all layers, route to conversational AI in always_on mode
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

        # 7. Always-on mode: route every matched intent through LLM for richer response
        from app.services.llm.llm_service import llm_service
        # Context is now added AFTER execution to ensure we pair it with the exact system result.

        res_dict = await self._execute_intent(intent_name, params, text, start)
        if locals().get("llm_routed", False):
            res_dict["routed_by_llm"] = True
        return res_dict

    async def _execute_intent(self, intent_name: str, params: dict, text: str, start: float) -> dict[str, Any]:
        # Execute handler
        intent = self._get_intent(intent_name)
        if not intent:
            return {"intent": intent_name, "parameters": params, "status": "failed",
                    "result": "Intent handler not found", "duration_ms": int((time.perf_counter() - start) * 1000)}

        # Track the last targeted application for focus restoration in follow-up commands
        app_target = params.get("app") or params.get("app_name")
        if app_target:
            self.last_target_app = app_target

        # Auto-inject last target app for dialog commands if missing (solves Web UI focus stealing)
        if intent_name in ("dont_save", "save_file", "cancel_dialog", "submit", "type_text", "set_filename") and not params.get("app_name"):
            if getattr(self, "last_target_app", ""):
                params["app_name"] = self.last_target_app

        # Inject raw text so handlers can access the original utterance (e.g., to catch "in new tab" if LLM stripped it)
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
                
            # Record context for LLM history if successful
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
                    browser_res = await browser_cmd.execute(text)
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
            
            # User-friendly error translations
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

    def _regex_match(self, text: str) -> tuple[str | None, dict]:
        # Priority 1: Specific intents matching the current continuity domain
        for intent in self._intents:
            if not intent.is_fallback and intent.domain == self.current_domain:
                matched, params = intent.match(text)
                if matched:
                    return intent.name, params
                    
        # Priority 2: Specific global intents
        for intent in self._intents:
            if not intent.is_fallback and intent.domain == "global":
                matched, params = intent.match(text)
                if matched:
                    return intent.name, params
                    
        # Priority 3: Specific intents in other domains
        for intent in self._intents:
            if not intent.is_fallback and intent.domain not in (self.current_domain, "global"):
                matched, params = intent.match(text)
                if matched:
                    return intent.name, params
                    
        # Priority 4: Fallback intents matching the current continuity domain
        for intent in self._intents:
            if intent.is_fallback and intent.domain == self.current_domain:
                matched, params = intent.match(text)
                if matched:
                    return intent.name, params
                    
        # Priority 5: Fallback global intents
        for intent in self._intents:
            if intent.is_fallback and intent.domain == "global":
                matched, params = intent.match(text)
                if matched:
                    return intent.name, params
                    
        # Priority 6: Fallback intents in other domains
        for intent in self._intents:
            if intent.is_fallback and intent.domain not in (self.current_domain, "global"):
                matched, params = intent.match(text)
                if matched:
                    return intent.name, params
                    
        return None, {}

    def _fuzzy_match(self, text: str, threshold: int = 85) -> tuple[str | None, dict]:
        """Match against examples using rapidfuzz. Returns best intent above threshold."""
        if not _RAPIDFUZZ_AVAILABLE:
            return None, {}

        candidates: list[tuple[str, str]] = []  # (example, intent_name)
        for intent in self._intents:
            # Disable fuzzy matching for intents that require parameters, 
            # because fuzzy matching cannot extract arguments. They must go to LLM.
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

    async def _semantic_match(self, text: str) -> tuple[str | None, dict[str, Any]]:
        """Layer 2: FastEmbed Semantic Routing"""
        from app.services.semantic_router import semantic_router
        import asyncio
        if not semantic_router._is_ready:
            await asyncio.to_thread(semantic_router.initialize, self._intents)
            
        intent_name, score = await asyncio.to_thread(semantic_router.semantic_match, text, 0.82)
        if intent_name:
            # Semantic matching doesn't extract regex groups, so we return empty params
            return intent_name, {}
        return None, {}

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
