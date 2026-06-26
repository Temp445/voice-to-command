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
from automation.browser.browser_controller import VoiceBrowserCommands, BrowserController
def _is_chrome_running_fast(port: int = 9222) -> bool:
    """Fast non-blocking check to see if Chrome debugging port is open."""
    import socket
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.02):
            return True
    except OSError:
        return False



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


# ── Voice Credential Normalizer ─────────────────────────────────────────────
def _normalize_voice_credential(raw: str) -> str:
    """
    Convert a voice-dictated credential/password value into its typed form.

    Supported transformations (applied in token order):
      Number words  → digits   : "one two three" → "123"
                                  "twenty one"    → "21"
      Symbol words  → symbols  : "at" → "@",  "dot" → ".",  "dash" → "-"
                                  "hash" → "#",  "exclamation" → "!"
      Caps modifier → case     : "cap word"      → "Word"   (first-letter cap)
                                  "all caps word" → "WORD"   (full uppercase)
      Trailing junk stripped   : "all yes caps", "end", leftover modifiers

    Examples:
      "reset at one two three"         → "reset@123"
      "cap r e cap s e t at one two three" → "ReSet@123"
      "password at hash one two three" → "password@#123"
    """
    import re as _re

    _ONES = {
        'zero': '0', 'oh': '0', 'o': '0',
        'one': '1', 'two': '2', 'three': '3', 'four': '4', 'five': '5',
        'six': '6', 'seven': '7', 'eight': '8', 'nine': '9',
    }
    _TENS = {
        'ten': '10', 'eleven': '11', 'twelve': '12', 'thirteen': '13',
        'fourteen': '14', 'fifteen': '15', 'sixteen': '16', 'seventeen': '17',
        'eighteen': '18', 'nineteen': '19',
        'twenty': '20', 'thirty': '30', 'forty': '40', 'fifty': '50',
        'sixty': '60', 'seventy': '70', 'eighty': '80', 'ninety': '90',
        'hundred': '100',
    }
    _SYMBOLS = {
        'at':           '@',
        'hash':         '#', 'hashtag': '#', 'pound': '#', 'number': '#',
        'dot':          '.', 'period': '.',
        'underscore':   '_', 'under': '_',
        'dash':         '-', 'hyphen': '-', 'minus': '-',
        'exclamation':  '!', 'bang': '!',
        'dollar':       '$',
        'percent':      '%', 'percentage': '%',
        'asterisk':     '*', 'star': '*',
        'plus':         '+',
        'equals':       '=', 'equal': '=',
        'slash':        '/',
        'backslash':    '\\',
        'colon':        ':',
        'semicolon':    ';',
        'question':     '?',
        'caret':        '^', 'hat': '^',
        'tilde':        '~',
        'comma':        ',',
        'apostrophe':   "'", 'quote': "'",
        'open':         '(',  # "open paren"
        'close':        ')',  # "close paren"
    }
    # Trailing dictation noise tokens that should be silently dropped
    # "case" covers "case caps" which is a common STT artifact for capitalization instructions
    _NOISE = {'yes', 'end', 'stop', 'done', 'ok', 'okay', 'confirm', 'case', 'please'}

    tokens = raw.split()
    result: list[str] = []
    i = 0
    all_caps_mode = False
    caps_next = False       # capitalize the NEXT single token

    while i < len(tokens):
        raw_tok = tokens[i]
        tok = raw_tok.lower().strip(".,!?;:'\"-")

        # ── Caps modifiers ────────────────────────────────────────────────────
        if tok in ('caps', 'cap', 'upper', 'uppercase'):
            # Peek: "all caps" → all_caps_mode; plain "caps" → caps_next
            caps_next = True
            i += 1
            continue

        if tok == 'all' and i + 1 < len(tokens) and tokens[i + 1].lower().strip('.,') in ('caps', 'cap', 'upper'):
            all_caps_mode = True
            i += 2  # skip "all" + "caps"
            continue

        if tok in ('no', 'lower', 'lowercase', 'normal'):
            all_caps_mode = False
            caps_next = False
            i += 1
            continue

        # ── Drop pure noise tokens at the END of the sequence ─────────────────
        # Only drop if every remaining token is noise (avoids eating real content)
        remaining_real = [t.lower().strip(".,!?;:") for t in tokens[i:]]
        if all(t in _NOISE or t in ('caps', 'cap', 'all', 'upper') for t in remaining_real):
            break  # discard the tail

        # ── Symbol words ──────────────────────────────────────────────────────
        if tok in _SYMBOLS:
            ch = _SYMBOLS[tok]
            result.append(ch.upper() if all_caps_mode else ch)
            caps_next = False
            i += 1
            continue

        # ── Tens + optional ones (e.g. "twenty one" → "21") ──────────────────
        if tok in _TENS:
            tens_str = _TENS[tok]
            if tok == 'hundred':
                result.append(tens_str)
                i += 1
                continue
            # Look ahead for ones digit
            nxt = tokens[i + 1].lower().strip('.,') if i + 1 < len(tokens) else ''
            if nxt in _ONES:
                combined = str(int(tens_str) + int(_ONES[nxt]))
                result.append(combined)
                i += 2
            else:
                result.append(tens_str)
                i += 1
            caps_next = False
            continue

        # ── Ones digits ───────────────────────────────────────────────────────
        if tok in _ONES:
            result.append(_ONES[tok])
            caps_next = False
            i += 1
            continue

        # ── Regular word ──────────────────────────────────────────────────────
        word = raw_tok.strip(".,!?;:")
        if all_caps_mode:
            word = word.upper()
        elif caps_next:
            word = word[0].upper() + word[1:] if word else word
            caps_next = False
        result.append(word)
        i += 1

    return ''.join(result)


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

        # ── STT Normalization: fix common Whisper gerund / contraction errors ──
        # Whisper often collapses two-word commands into gerund form, e.g.:
        #   "sign in" → "signing"    "log out" → "logging"    "scroll down" → "scrolling"
        # These are applied BEFORE spellcheck and all matching layers so every
        # downstream layer sees the corrected phrase.
        _STT_NORM = {
            # Auth actions
            "signing":      "sign in",
            "signin":       "sign in",
            "signup":       "sign up",
            "signingup":    "sign up",
            "signingout":   "sign out",
            "signout":      "sign out",
            "logging":      "log in",
            "login":        "log in",
            "logout":       "log out",
            # Navigation / page actions
            "refreshing":   "refresh",
            "reloading":    "reload",
            "scrolling":    "scroll",
            "clicking":     "click",
            "pressing":     "press",
            "submitting":   "submit",
            "searching":    "search",
            "opening":      "open",
            "closing":      "close",
        }
        _text_key = text.lower().replace(" ", "")
        if _text_key in _STT_NORM:
            _corrected = _STT_NORM[_text_key]
            logger.info(f"STT normalization: '{text}' → '{_corrected}'")
            text = _corrected
        else:
            # Also handle partial gerund at the start of a longer phrase
            # e.g. "signing in to the portal" → "sign in to the portal"
            import re as _stt_re
            _GERUND_MAP = [
                (r"^signing\s+(?:in|into)\b", "sign in"),
                (r"^signing\s+(?:up)\b",      "sign up"),
                (r"^signing\s+out\b",          "sign out"),
                (r"^logging\s+(?:in|into)\b", "log in"),
                (r"^logging\s+out\b",          "log out"),
            ]
            for _pat, _rep in _GERUND_MAP:
                if _stt_re.match(_pat, text, _stt_re.IGNORECASE):
                    _corrected = _stt_re.sub(_pat, _rep, text, count=1, flags=_stt_re.IGNORECASE)
                    logger.info(f"STT phrase normalization: '{text}' → '{_corrected}'")
                    text = _corrected
                    break

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
            
            _target_noun = _text_lower
            for _v in sorted(_nav_verbs, key=len, reverse=True):
                if _text_lower.startswith(_v):
                    _target_noun = _text_lower[len(_v):].strip()
                    break
            _target_noun_ns = _target_noun.replace(" ", "")

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

            # Fuzzy rescue — catches Whisper mishearing like "crm" → "serum", "payroll" → "pay role"
            # Only runs if exact match failed AND a nav verb was present.
            if not _matched_site_url and _has_nav_verb and _target_noun_ns:
                _all_kws: list[tuple[str, str, dict]] = []  # (kw_no_spaces, url, routes)
                for _site in _sites:
                    for _kw in _site.get("keywords", "").split(","):
                        _kw = _kw.strip().lower()
                        if _kw:
                            _all_kws.append((_kw.replace(" ", ""), _site.get("url", ""), _site.get("routes", {})))
                
                if _all_kws:
                    _kw_strings = [k[0] for k in _all_kws]
                    _matched_kw = None
                    
                    if _RAPIDFUZZ_AVAILABLE:
                        # RapidFuzz is highly resilient to phonetic typos like "serum" vs "crm"
                        _res = process.extractOne(_target_noun_ns, _kw_strings, scorer=fuzz.WRatio)
                        if _res and _res[1] >= 65:  # 65+ is a good fuzzy threshold for misheard single words
                            _matched_kw = _res[0]
                    else:
                        import difflib as _dl
                        _close = _dl.get_close_matches(_target_noun_ns, _kw_strings, n=1, cutoff=0.55)
                        if _close:
                            _matched_kw = _close[0]
                            
                    if _matched_kw:
                        for _k, _u, _r in _all_kws:
                            if _k == _matched_kw:
                                _matched_site_url = _u
                                _matched_routes = _r
                                break
                        logger.info(
                            f"Fuzzy shortcut rescue: '{text}' noun='{_target_noun}' "
                            f"→ matched keyword '{_matched_kw}' → {_matched_site_url}"
                        )

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

            # Layer 0.88: Chrome Native Dialog Intercept
            # ──────────────────────────────────────────────────────────────────
            # Chrome's "Save password?", "Translate?", etc. are native browser UI
            # widgets — NOT in the page DOM. Playwright cannot reach them via
            # get_by_text / get_by_role / page.locator.
            #
            # Solution: detect the intent from voice, bring Chrome to the OS
            # foreground, then send keyboard events via pyautogui (OS-level).
            # Fallback: Playwright CDP keyboard.press() if pyautogui is absent.
            #
            # Chrome password bubble keyboard map:
            #   Enter           → activates the focused "Save" button (default)
            #   Shift+Tab+Enter → moves focus to "Never", then clicks
            #   Escape          → closes the bubble (No thanks / dismiss)
            import re as _d_re
            _d_text = text.lower().strip()
            _chrome_dialog_action: str | None = None

            # PRIORITY 1: Close / Dismiss / No-thanks
            # MUST be checked before "save" because "close the save password popup"
            # contains the substring "save password" and would falsely trigger Enter.
            if _d_re.search(
                r'\bno\s*thanks\b'
                r'|\bdon\'t\s+save\b|\bdont\s+save\b'
                r'|\bnot\s+now\b'
                r'|\b(close|dismiss|skip|cancel|reject|ignore)\b.{0,35}\b(password|save|dialog|popup|notification)\b',
                _d_text
            ):
                _chrome_dialog_action = "no_thanks"

            # PRIORITY 2: Never save
            elif _d_re.search(
                r'\bnever\s+save\b'
                r'|\b(click|press|select|choose)\s+never\b'
                r'|\bnever\b.{0,15}\bpassword\b',
                _d_text
            ):
                _chrome_dialog_action = "never"

            # PRIORITY 3: Save — anchored so "close the save password" does NOT match
            elif _d_re.search(
                r'^\s*(save\s+password|yes\s+save|keep\s+password|save\s+it)\b'
                r'|\b(click|press|select|choose)\s+save\b',
                _d_text
            ):
                _chrome_dialog_action = "save"

            if not intent_name and _chrome_dialog_action:
                try:
                    from automation.browser.browser_engine import BrowserEngine as _BE_d, _run_in_playwright as _rip_d
                    _be_d = _BE_d()
                    if _be_d._context is not None:

                        async def _bring_chrome_front():
                            page = await _be_d.get_active_page()
                            if page:
                                try:
                                    await page.bring_to_front()
                                except Exception:
                                    pass
                            return True

                        await _rip_d(_bring_chrome_front())

                        import time as _t_d
                        _t_d.sleep(0.25)   # Allow Chrome time to take OS focus

                        _dialog_sent = False
                        # ── Primary: OS-level keyboard via pyautogui ──────────
                        try:
                            import pyautogui as _pag
                            _pag.FAILSAFE = False
                            if _chrome_dialog_action == "save":
                                _pag.press("enter")
                            elif _chrome_dialog_action == "never":
                                # Shift+Tab moves focus from Save → Never (leftmost button)
                                _pag.hotkey("shift", "tab")
                                _t_d.sleep(0.1)
                                _pag.press("enter")
                            elif _chrome_dialog_action == "no_thanks":
                                _pag.press("escape")
                            _dialog_sent = True
                        except ImportError:
                            pass  # pyautogui not installed — fall through to CDP

                        # ── Fallback: Playwright CDP keyboard.press() ─────────
                        if not _dialog_sent:
                            async def _do_dialog_keyboard():
                                page = await _be_d.get_active_page()
                                if not page:
                                    return False
                                if _chrome_dialog_action == "save":
                                    await page.keyboard.press("Return")
                                elif _chrome_dialog_action == "never":
                                    await page.keyboard.press("Shift+Tab")
                                    await asyncio.sleep(0.1)
                                    await page.keyboard.press("Return")
                                elif _chrome_dialog_action == "no_thanks":
                                    await page.keyboard.press("Escape")
                                return True

                            _dialog_sent = await _rip_d(_do_dialog_keyboard())

                        if _dialog_sent:
                            _action_labels = {
                                "save":      "Password saved.",
                                "never":     "Never save for this site.",
                                "no_thanks": "Password dialog dismissed.",
                            }
                            logger.info(f"Layer 0.88 Chrome dialog: '{_chrome_dialog_action}'")
                            return {
                                "intent": "chrome_native_dialog",
                                "parameters": {"action": _chrome_dialog_action},
                                "status": "success",
                                "result": _action_labels.get(_chrome_dialog_action, "Dialog action sent."),
                                "duration_ms": int((time.perf_counter() - start) * 1000),
                                "is_fallback": True,
                            }
                except Exception as _de:
                    logger.debug(f"Layer 0.88 Chrome dialog handler failed: {_de}")

            # ── Kick off async page snapshot in background (non-blocking) ─────────
            # This pre-warms the PageContextService cache so Layer 0.85 has data
            # on the NEXT voice command (latency-free pipeline warm-up).
            try:
                from app.services.page_context_service import page_context_service as _pcs
                import asyncio as _asyncio
                _asyncio.ensure_future(
                    _pcs.get_snapshot(),
                    loop=_asyncio.get_event_loop()
                )
            except Exception:

                pass

            # Guard: do not allow early intercepts to hijack explicit auth commands
            _lower_text = text.lower().strip()
            _is_auth_cmd = (
                _lower_text in ["sign in", "login", "log in", "log out", "logout", "sign out", "submit"]
                or _lower_text.startswith("sign in")
                or _lower_text.startswith("log in")
                or _lower_text.startswith("sign out")
                or _lower_text.startswith("log out")
                or _lower_text.startswith("login")
                or _lower_text.startswith("logout")
            )

            # Layer 0.85: Snapshot-based Fast Click (cached DOM — no Playwright round-trip)
            # Reads the pre-warmed PageContextService cache and scores every visible element
            # against the voice query using text-similarity scoring.
            # Falls through to Layer 0.9 if the snapshot is stale/missing or nothing scores.
            if not intent_name and len(text.split()) <= 7 and not _is_auth_cmd:
                try:
                    from app.services.page_context_service import (
                        page_context_service as _pcs,
                        find_best_element as _find_best,
                    )
                    from automation.browser.browser_engine import _run_in_playwright, BrowserEngine
                    _snap = _pcs.get_cached_snapshot()
                    _be = BrowserEngine()
                    if _snap and (_be._context is not None or _is_chrome_running_fast(9222)):
                        _best_el = _find_best(_snap.elements, text, min_score=45)
                        if _best_el:
                            _target_text = _best_el.text or _best_el.name or _best_el.el_id
                            _target_text_snap = _target_text  # capture for closure

                            async def _do_snapshot_click():
                                import re as _re
                                page = await _be.get_active_page()
                                if not page:
                                    return False
                                try:
                                    await page.bring_to_front()
                                except Exception:
                                    pass
                                # Click by exact label using Playwright locators
                                for _loc in [
                                    page.get_by_role("button", name=_re.compile(_re.escape(_target_text_snap), _re.IGNORECASE)),
                                    page.get_by_role("link",   name=_re.compile(_re.escape(_target_text_snap), _re.IGNORECASE)),
                                    page.get_by_text(_target_text_snap, exact=False),
                                ]:
                                    try:
                                        if await _loc.count() > 0:
                                            el = _loc.first
                                            if await el.is_visible():
                                                await el.scroll_into_view_if_needed(timeout=1000)
                                                await el.click(timeout=2000)
                                                try:
                                                    await page.wait_for_load_state("commit", timeout=3000)
                                                except Exception:
                                                    pass
                                                # Invalidate snapshot since page may have changed
                                                _pcs.invalidate()
                                                return True
                                    except Exception:
                                        pass
                                return False

                            _snapped = await _run_in_playwright(_do_snapshot_click())
                            if _snapped:
                                logger.info(f"Layer 0.85 snapshot click: '{text}' → '{_target_text}'")
                                return {
                                    "intent": "implicit_browser_click",
                                    "parameters": {"text": text, "matched_element": _target_text},
                                    "status": "success",
                                    "result": f"Clicked '{_target_text}' on webpage.",
                                    "duration_ms": int((time.perf_counter() - start) * 1000),
                                    "is_fallback": True,
                                }
                except Exception as _e:
                    logger.debug(f"Layer 0.85 snapshot click failed: {_e}")

            # Layer 0.9: Implicit Web Click Intercept
            # Prioritize active screen context. If a short phrase exactly or partially
            # matches a visible button/link on the page, click it INSTANTLY.
            # FIX: All Playwright awaits must run on the dedicated _playwright_loop thread.
            # Calling them on the FastAPI/pipeline loop causes silent cross-loop failures.
            if not intent_name and len(text.split()) <= 5 and not _is_auth_cmd:

                try:
                    from automation.browser.browser_controller import BrowserController
                    from automation.browser.browser_engine import _run_in_playwright
                    bc = BrowserController()
                    if bc.engine._context is not None or _is_chrome_running_fast(9222):
                        import re as _re
                        _click_text = text  # capture for closure
                        _start_ref = start

                        async def _do_implicit_click():
                            page = await bc.engine.get_active_page()
                            if not page:
                                return None

                            # Bring Chrome to front so click has OS-level focus
                            try:
                                await page.bring_to_front()
                            except Exception:
                                pass

                            _locators = [
                                # 1. Exact Matches
                                page.get_by_role("button", name=_re.compile(f"^{_re.escape(_click_text)}$", _re.IGNORECASE)),
                                page.get_by_role("link",   name=_re.compile(f"^{_re.escape(_click_text)}$", _re.IGNORECASE)),
                                page.get_by_text(_click_text, exact=True),
                                # 2. Partial Matches
                                page.get_by_role("button", name=_re.compile(_re.escape(_click_text), _re.IGNORECASE)),
                                page.get_by_role("link",   name=_re.compile(_re.escape(_click_text), _re.IGNORECASE)),
                                page.get_by_text(_click_text, exact=False),
                            ]
                            for _loc in _locators:
                                try:
                                    count = await _loc.count()
                                    for i in range(count):
                                        element = _loc.nth(i)
                                        if await element.is_visible():
                                            await element.scroll_into_view_if_needed(timeout=1000)
                                            await element.click(timeout=2000)
                                            # Wait for navigation to begin (non-blocking if no nav)
                                            try:
                                                await page.wait_for_load_state("commit", timeout=3000)
                                            except Exception:
                                                pass
                                            return "clicked_exact"
                                except Exception as _le:
                                    logger.debug(f"Implicit click locator failed, trying next: {_le}")

                            # 3. JavaScript Fuzzy Token Match — find the best element by text score,
                            # then click via Playwright mouse (not JS .click()) so React SPA events fire.
                            _stop_words = {"open", "click", "press", "hit", "the", "a", "an", "on", "file", "app", "link", "button", "document", "excel", "word", "powerpoint", "go", "to", "my", "show", "me", "move", "switch", "navigate", "change", "tab"}
                            _target_words = [w.lower() for w in _click_text.split() if w.lower() not in _stop_words]
                            if _target_words:
                                # Return bounding rect of best-scoring element instead of clicking in JS
                                _js_find = """
                                (targetWords) => {
                                    const elements = Array.from(document.querySelectorAll("a, button, [role='button'], [role='link'], [role='menuitem'], [role='tab']"));
                                    let bestEl = null;
                                    let bestScore = 0;
                                    for (const el of elements) {
                                        const style = window.getComputedStyle(el);
                                        if (style.display === 'none' || style.visibility === 'hidden' || el.offsetWidth === 0) continue;
                                        const text = el.innerText ? el.innerText.toLowerCase() : '';
                                        if (!text) continue;
                                        let score = 0;
                                        for (const w of targetWords) { if (text.includes(w)) score++; }
                                        if (score > bestScore) { bestScore = score; bestEl = el; }
                                    }
                                    if (bestEl && bestScore >= Math.max(1, targetWords.length - 1)) {
                                        const r = bestEl.getBoundingClientRect();
                                        return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
                                    }
                                    return null;
                                }
                                """
                                try:
                                    for _frame in page.frames:
                                        try:
                                            _pos = await _frame.evaluate(_js_find, _target_words)
                                            if _pos and _pos.get("x") is not None:
                                                # Use Playwright mouse click so React synthetic events fire
                                                await page.mouse.click(_pos["x"], _pos["y"])
                                                try:
                                                    await page.wait_for_load_state("commit", timeout=3000)
                                                except Exception:
                                                    pass
                                                return "clicked_fuzzy"
                                        except Exception:
                                            pass
                                except Exception as _je:
                                    logger.debug(f"Implicit click JS fuzzy match failed: {_je}")

                            # Guard: fail fast for known auth commands to prevent LLM hallucinations
                            _lower = _click_text.lower()
                            if _lower in ["sign in", "login", "log in", "log out", "logout", "sign out", "submit"] or _lower.startswith("sign in") or _lower.startswith("log in"):
                                return "auth_not_found"
                            return None

                        _click_result = await _run_in_playwright(_do_implicit_click())
                        if _click_result == "clicked_exact":
                            return {
                                "intent": "implicit_browser_click",
                                "parameters": {"text": text},
                                "status": "success",
                                "result": f"Clicked '{text}' on webpage.",
                                "duration_ms": int((time.perf_counter() - start) * 1000),
                                "is_fallback": True,
                            }
                        elif _click_result == "clicked_fuzzy":
                            return {
                                "intent": "implicit_browser_click",
                                "parameters": {"text": text},
                                "status": "success",
                                "result": f"Clicked closest match for '{text}' via fuzzy logic.",
                                "duration_ms": int((time.perf_counter() - start) * 1000),
                                "is_fallback": True,
                            }
                        elif _click_result == "auth_not_found":
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

            # Layer 0.94: Bare Email Address Intercept
            # Catches text that IS (or contains) an email address even without "email" prefix.
            # STT often splits "anandhs@acesoft.in" → "anand s@acesoft.in" — we repair that too.
            if not intent_name:
                import re as _re
                _bare_text = text.strip().rstrip(".,!?")
                # Repair STT space before @ (e.g. "anand s@acesoft.in" → "anands@acesoft.in")
                _bare_text_fixed = _re.sub(r'\s+@', '@', _bare_text)
                _bare_text_fixed = _re.sub(r'@\s+', '@', _bare_text_fixed)
                _bare_text_fixed = _re.sub(r'\s+(\.\w{2,})', r'\1', _bare_text_fixed)
                # Detect bare email pattern: word@domain.tld (with no other text, or minimal prefix)
                _email_match = _re.search(r'\b[\w.+-]+@[\w.-]+\.\w{2,}\b', _bare_text_fixed)
                if _email_match:
                    _email_val = _email_match.group(0)
                    try:
                        from automation.browser.browser_controller import BrowserController
                        from automation.browser.browser_engine import _run_in_playwright
                        bc = BrowserController()
                        if bc.engine._context is not None or _is_chrome_running_fast(9222):
                            logger.info(f"Bare email intercept: '{_email_val}' (from '{text}')")

                            async def _do_bare_email():
                                page = await bc.engine.get_active_page()
                                if not page:
                                    return False
                                # Prefer focused input, then email-typed, then any visible text input
                                _loc = page.locator(
                                    "input[type='email'], input[name*='email' i], input[placeholder*='email' i], "
                                    "input[name*='user' i], input[type='text']:visible"
                                ).first
                                if await _loc.count() > 0:
                                    await _loc.fill(_email_val)
                                    return True
                                return False

                            _bare_typed = await _run_in_playwright(_do_bare_email())
                            if _bare_typed:
                                return {
                                    "intent": "implicit_browser_type",
                                    "parameters": {"field": "email", "value": _email_val},
                                    "status": "success",
                                    "result": f"Filled email '{_email_val}'.",
                                    "duration_ms": int((time.perf_counter() - start) * 1000),
                                    "is_fallback": True,
                                }
                    except Exception as _e:
                        logger.debug(f"Bare email intercept failed: {_e}")

            # Layer 0.95: Implicit Web Type Intercept (Single Credential)
            # FIX: Playwright operations run on _playwright_loop thread via _run_in_playwright.
            # Robustness improvements:
            #   - Strips filler words ("uh", "um", "er", "so", "like") that STT inserts
            #   - Tolerates punctuation after field keyword ("Email, user@x.com")
            #   - Repairs STT space errors inside email addresses ("anand s@x.com" → "anands@x.com")
            #   - Accepts command-verb prefixes: "update the password X" → "password X"
            if not intent_name:
                import re as _re
                # Normalize: remove filler words and punctuation between keyword and value
                _cred_text = _re.sub(
                    r'\b(uh|um|er|ah|like|so|well|right|okay|ok)\b[,\s]*', ' ', text, flags=_re.IGNORECASE
                ).strip()
                # Strip command-verb prefix so "update the password X" becomes "password X"
                # Handles: "update/change/set/enter/fill/create/type [the/my/a/your] [new] password [. ] X"
                _cred_text = _re.sub(
                    r'^(?:update|change|set|enter|fill|use|create|make|type|modify|edit)\s+'
                    r'(?:the\s+|my\s+|a\s+|your\s+)?(?:new\s+)?',
                    '', _cred_text, flags=_re.IGNORECASE
                ).strip()
                # Tolerate commas/colons/periods after the field keyword
                _cred_text = _re.sub(
                    r'^(email(?:\s+(?:address|id))?|username|user\s*name|password|pass)\s*[,.:;\s]+',
                    lambda m: m.group(1) + ' ', _cred_text, flags=_re.IGNORECASE
                ).strip()
                _cred_match = _re.match(
                    r'^(email(?:\s+(?:address|id))?|username|user\s*name|password|pass)\s+(.+)$',
                    _cred_text, _re.IGNORECASE
                )
                # Normalise the field type to simple canonical form
                if _cred_match:
                    _raw_field = _cred_match.group(1).lower().replace(' ', '')
                    if _raw_field in ('emailaddress', 'emailid'):
                        _canonical_field = 'email'
                    elif _raw_field in ('username', 'username'):
                        _canonical_field = 'username'
                    elif _raw_field in ('pass',):
                        _canonical_field = 'password'
                    else:
                        _canonical_field = _raw_field
                    try:
                        from automation.browser.browser_controller import BrowserController
                        from automation.browser.browser_engine import _run_in_playwright
                        bc = BrowserController()
                        if bc.engine._context is not None or _is_chrome_running_fast(9222):
                            _field_type = _canonical_field
                            _val = _cred_match.group(2).strip()

                            # Repair STT-induced spaces in email addresses:
                            # "anand s@caseof.in" → "anands@caseof.in"
                            # "user@ domain.com" → "user@domain.com"
                            if _field_type in ("email", "username") and "@" in _val:
                                _val = _re.sub(r'\s+(@)', r'\1', _val)   # space before @
                                _val = _re.sub(r'(@)\s+', r'\1', _val)   # space after @
                                _val = _re.sub(r'\s+(\.\w)', r'\1', _val)  # space before domain dot
                            else:
                                # Apply voice-to-credential normalization for passwords:
                                # converts number words → digits and symbol words → symbols
                                _val_normalized = _normalize_voice_credential(_val)
                                if _val_normalized != _val:
                                    logger.info(f"Password normalized: '{_val}' → '{_val_normalized}'")
                                _val = _val_normalized

                            logger.info(f"Credential intercept: field='{_field_type}' value='{_val}' (from '{text}')")

                            async def _do_implicit_type():
                                page = await bc.engine.get_active_page()
                                if not page:
                                    return False
                                if _field_type in ["email", "username"]:
                                    _loc = page.locator("input[type='email'], input[name*='email' i], input[placeholder*='email' i], input[name*='user' i]").first
                                else:
                                    _loc = page.locator("input[type='password'], input[name*='pass' i], input[placeholder*='pass' i]").first
                                if await _loc.count() > 0:
                                    await _loc.fill(_val)
                                    await _loc.press("Enter")
                                    return True
                                return False

                            _typed = await _run_in_playwright(_do_implicit_type())
                            if _typed:
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
            # FIX: Playwright operations run on _playwright_loop thread via _run_in_playwright.
            if not intent_name:
                _digits_only = text.replace(" ", "").replace("-", "")
                if _digits_only.isdigit() and len(_digits_only) >= 4:
                    try:
                        from automation.browser.browser_controller import BrowserController
                        from automation.browser.browser_engine import _run_in_playwright
                        bc = BrowserController()
                        if bc.engine._context is not None or _is_chrome_running_fast(9222):
                            _otp_val = _digits_only

                            async def _do_implicit_otp():
                                page = await bc.engine.get_active_page()
                                if not page:
                                    return False
                                # Playwright types into the active DOM element, ignoring OS focus.
                                # Delay added to allow React/Angular inputs to auto-advance focus.
                                await page.keyboard.type(_otp_val, delay=50)
                                return True

                            _otp_typed = await _run_in_playwright(_do_implicit_otp())
                            if _otp_typed:
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
                # Layer 3.5: Vision Fallback — Gemini sees the screen and identifies the element
                # Only runs when ALL prior layers (regex, fuzzy, semantic, LLM, dynamic browser) failed.
                # Takes a Playwright browser screenshot, asks Gemini Vision what to do,
                # then executes the action via Playwright.
                _vision_executed = False
                try:
                    from app.services.vision_service import vision_service as _vs
                    from automation.browser.browser_engine import BrowserEngine as _BE, _run_in_playwright as _rip
                    _be_vision = _BE()
                    if _be_vision._context is not None:
                        _vision_action = await _vs.find_and_click_by_voice(text)
                        if _vision_action:
                            _v_action   = _vision_action.get("action", "none")
                            _v_target   = _vision_action.get("target_text", "")
                            _v_value    = _vision_action.get("value", "")
                            _v_target_c = _v_target   # capture for closure
                            _v_value_c  = _v_value
                            _v_action_c = _v_action

                            async def _do_vision_action():
                                import re as _re
                                page = await _be_vision.get_active_page()
                                if not page:
                                    return False
                                try:
                                    await page.bring_to_front()
                                except Exception:
                                    pass

                                if _v_action_c == "click":
                                    for _loc in [
                                        page.get_by_role("button", name=_re.compile(_re.escape(_v_target_c), _re.IGNORECASE)),
                                        page.get_by_role("link",   name=_re.compile(_re.escape(_v_target_c), _re.IGNORECASE)),
                                        page.get_by_text(_v_target_c, exact=False),
                                    ]:
                                        try:
                                            if await _loc.count() > 0:
                                                el = _loc.first
                                                if await el.is_visible():
                                                    await el.scroll_into_view_if_needed(timeout=1000)
                                                    await el.click(timeout=2000)
                                                    try:
                                                        await page.wait_for_load_state("commit", timeout=3000)
                                                    except Exception:
                                                        pass
                                                    return True
                                        except Exception:
                                            pass

                                elif _v_action_c == "type" and _v_value_c:
                                    # Try to fill the identified input field
                                    for _loc in [
                                        page.get_by_placeholder(_re.compile(_re.escape(_v_target_c), _re.IGNORECASE)),
                                        page.get_by_label(_re.compile(_re.escape(_v_target_c), _re.IGNORECASE)),
                                        page.locator(f"input[name*='{_v_target_c.lower()}' i]"),
                                    ]:
                                        try:
                                            if await _loc.count() > 0:
                                                el = _loc.first
                                                if await el.is_visible():
                                                    await el.fill(_v_value_c)
                                                    return True
                                        except Exception:
                                            pass

                                elif _v_action_c == "scroll":
                                    direction = "down" if "down" in text.lower() else "up"
                                    delta = 400 if direction == "down" else -400
                                    await page.mouse.wheel(0, delta)
                                    return True

                                return False

                            _vis_ok = await _rip(_do_vision_action())
                            if _vis_ok:
                                _vision_executed = True
                                from app.services.page_context_service import page_context_service as _pcs_v
                                _pcs_v.invalidate()
                                return {
                                    "intent": "vision_fallback",
                                    "parameters": {"text": text, "action": _v_action, "target": _v_target},
                                    "status": "success",
                                    "result": f"[Vision] {_v_action.capitalize()}ed '{_v_target}' on screen.",
                                    "duration_ms": int((time.perf_counter() - start) * 1000),
                                    "routed_by_vision": True,
                                }
                except Exception as _ve:
                    logger.debug(f"Layer 3.5 vision fallback error: {_ve}")

                if not _vision_executed:
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

            logger.exception(f"Handler '{intent_name}' failed:")
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