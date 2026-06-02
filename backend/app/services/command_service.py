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
        start = time.perf_counter()

        # 0. Check for user-defined Macros/Workflows in the database
        try:
            from app.database import AsyncSessionLocal
            from app.models import Workflow
            from sqlalchemy import select
            async with AsyncSessionLocal() as session:
                result = await session.execute(select(Workflow))
                workflows = result.scalars().all()
                for wf in workflows:
                    if wf.trigger_phrase.lower() in text.lower():
                        logger.info(f"Matched workflow macro: {wf.name}")
                        results = []
                        import asyncio
                        for step in wf.steps:
                            action = step.get("action", "")
                            if step.get("delay_ms", 0):
                                await asyncio.sleep(step["delay_ms"] / 1000)
                            # Recursively call parse_and_execute to run the macro action
                            # Setting a flag to prevent infinite macro loops
                            if "macro_loop" not in action:
                                r = await self.parse_and_execute(action)
                                results.append(r.get("result", ""))
                        
                        return {
                            "intent": "execute_workflow",
                            "parameters": {"name": wf.name},
                            "result": f"Executed macro '{wf.name}'. Steps: {len(results)}",
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

        # 0.5. Check if the full text perfectly matches a known compound-aware intent FIRST
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
            # 3. Native regex matching
            intent_name, params = self._regex_match(text)

            # 4. Pronoun detection: If any extracted parameter is exactly a pronoun, force LLM context resolution.
            from app.services.llm.llm_service import llm_service
            has_pronouns = False
            if intent_name:
                for val in params.values():
                    if isinstance(val, str) and re.fullmatch(r'(?i)(it|this|that|them|here)', val.strip()):
                        has_pronouns = True
                        break
            else:
                # If no regex matched, we might still want LLM to catch "close it" if it didn't even match regex
                has_pronouns = bool(re.search(r'\b(it|this|that|them|here)\b', text, re.IGNORECASE))
            
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
                
                # 5. Fuzzy fallback if no regex match
                if not intent_name:
                    intent_name, params = self._fuzzy_match(text)

        if not intent_name:
            # 6. LLM fallback — classify intent via AI when all else fails
            from app.services.llm.llm_service import llm_service
            if llm_service.is_ready and llm_service._mode == "fallback":
                llm_result = await llm_service.classify_intent(text, self.list_intents())
                if llm_result:
                    intent_name = llm_result.get("intent")
                    # Merge any parameters the LLM contextually extracted
                    params.update(llm_result.get("params", {}))
                
                if not intent_name:
                    # Try the dynamic Browser NLP mapper before conversational LLM
                    from automation.ace_browser.ace_browser_controller import ACEVoiceBrowserCommands
                    browser_cmd = ACEVoiceBrowserCommands()
                    browser_res = await browser_cmd.execute(text)
                    if browser_res and not browser_res.startswith("Command not recognized"):
                        return {
                            "intent": "dynamic_browser_command",
                            "parameters": {"text": text},
                            "status": "success" if "Failed" not in browser_res else "failed",
                            "result": browser_res,
                            "duration_ms": int((time.perf_counter() - start) * 1000),
                        }
                    
                    # Still no match — route to ask_llm for a conversational response
                    intent_name = "ask_llm"
                    params = {"question": text}

        if not intent_name:
            # Try the dynamic Browser NLP mapper before giving up
            from automation.ace_browser.ace_browser_controller import ACEVoiceBrowserCommands
            browser_cmd = ACEVoiceBrowserCommands()
            browser_res = await browser_cmd.execute(text)
            if browser_res and not browser_res.startswith("Command not recognized"):
                return {
                    "intent": "dynamic_browser_command",
                    "parameters": {"text": text},
                    "status": "success" if "Failed" not in browser_res else "failed",
                    "result": browser_res,
                    "duration_ms": int((time.perf_counter() - start) * 1000),
                }

            logger.warning(f"No intent matched for: '{text}'")
            # If LLM is in always_on mode but couldn't classify, still try ask_llm
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

        return await self._execute_intent(intent_name, params, text, start)

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
                
            return {
                "intent": intent_name,
                "parameters": params,
                "status": "success",
                "result": result,
                "duration_ms": duration_ms,
            }
        except Exception as e:
            logger.error(f"Handler '{intent_name}' raised: {e}")
            return {
                "intent": intent_name,
                "parameters": params,
                "status": "failed",
                "result": str(e),
                "duration_ms": int((time.perf_counter() - start) * 1000),
            }

    def _regex_match(self, text: str) -> tuple[str | None, dict]:
        for intent in self._intents:
            matched, params = intent.match(text)
            if matched:
                return intent.name, params
        return None, {}

    def _fuzzy_match(self, text: str, threshold: int = 75) -> tuple[str | None, dict]:
        """Match against examples using rapidfuzz. Returns best intent above threshold."""
        if not _RAPIDFUZZ_AVAILABLE:
            return None, {}

        candidates: list[tuple[str, str]] = []  # (example, intent_name)
        for intent in self._intents:
            for example in intent.examples:
                candidates.append((example, intent.name))

        if not candidates:
            return None, {}

        examples_only = [c[0] for c in candidates]
        result = process.extractOne(text, examples_only, scorer=fuzz.WRatio)

        if result and result[1] >= threshold:
            matched_example = result[0]
            intent_name = next(c[1] for c in candidates if c[0] == matched_example)
            logger.debug(f"Fuzzy matched '{text}' → '{intent_name}' (score={result[1]})")
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
