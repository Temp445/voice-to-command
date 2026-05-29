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

        # 1. Attempt to split into compound commands (e.g., "open notepad and type hello")
        parts = re.split(r'(?i)\s+(?:and|then)\s+', text)
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
                    intent = self._get_intent(i_name)
                    if not intent:
                        continue
                    try:
                        res = await intent.handler(**params)
                        results.append(str(res))
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
            # 3. Regex pattern matching (new commands override pending state)
            intent_name, params = self._regex_match(text)

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
            logger.warning(f"No intent matched for: '{text}'")
            return {
                "intent": None,
                "parameters": {},
                "status": "failed",
                "result": f"Sorry, I didn't understand: '{text}'",
                "duration_ms": int((time.perf_counter() - start) * 1000),
            }
        # 5. Execute handler
        intent = self._get_intent(intent_name)
        if not intent:
            return {"intent": intent_name, "parameters": params, "status": "failed",
                    "result": "Intent handler not found", "duration_ms": int((time.perf_counter() - start) * 1000)}

        try:
            result = await intent.handler(**params)
            duration_ms = int((time.perf_counter() - start) * 1000)
            
            if isinstance(result, str) and result.startswith("MULTIPLE_MATCHES:"):
                self._pending_action = {"intent": intent_name, "params": params}
                result = result.replace("MULTIPLE_MATCHES:", "").strip()
                
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
            }
            for i in self._intents
        ]


# Singleton
command_service = CommandService()
