import os
import re
from loguru import logger


def _is_credential_like(word: str) -> bool:
    """
    Returns True if a word looks like a credential, token, email, or password
    that should NOT be spelling-corrected (case must be preserved).
    """
    # Contains @ (email address or password with @)
    if '@' in word:
        return True
    # Mixed case (e.g., reSet@123, MyPass) — user intentionally specified casing
    if any(c.isupper() for c in word) and any(c.islower() for c in word):
        # Exclude simple Title Case words at the start of sentences
        if word.istitle():
            pass
        else:
            return True
    # Contains special characters typical in passwords
    if any(c in word for c in ['!', '#', '$', '%', '^', '&', '*', '(', ')', '_', '+', '=', '/', '\\', '.', '~']):
        return True
    # All digits or alphanumeric short codes (like "123", "abc123")
    if re.match(r'^[a-zA-Z0-9]{4,}$', word) and re.search(r'\d', word):
        return True
    return False

def apply_caps_modifier(text: str, wrap_preserve: bool = False) -> str:
    """
    Parse phrases like 'reset@123 S caps' or 'niven33456@gmail.com N small'
    and capitalize or lowercase the named letter in the target word.
    
    Supported patterns:
      - "<word> <letter> caps/small"       e.g. "reset@123 s caps"    -> "reSet@123"
      - "<word> <letter> capital"          e.g. "reset@123 s capital"  -> "reSet@123"
      - "<word> with <letter> caps/small"  e.g. "reset@123 with s caps"
      - "<letter> caps/small <word>"       e.g. "s caps reset@123"     -> "reSet@123"
      - "<phrase> <letter> caps/small"     e.g. "reset at 123 R caps"  -> "Reset at 123"
    """
    # 1. Normalize joined words like "Rcaps", "nsmall", "Nsmall", "rcaps", "Rcapital" -> "R caps"
    text = re.sub(r'\b([a-zA-Z])(caps|capital|small|lowercase|lower)\b', r'\1 \2', text, flags=re.IGNORECASE)

    # 2. Tokenize by whitespace
    words = text.split()
    if not words:
        return text

    i = 0
    while i < len(words):
        is_modifier = False
        char = ""
        action = "" # "upper" or "lower"
        mod_start_idx = -1
        mod_end_idx = -1
        
        # Look for: [with] <letter> caps/small
        if i < len(words) - 1:
            w_curr = words[i].lower().strip(".,!?;:")
            w_next = words[i+1].lower().strip(".,!?;:")
            
            is_up = w_next in ("caps", "capital", "upper", "uppercase")
            is_down = w_next in ("small", "lowercase", "lower")
            
            if len(w_curr) == 1 and w_curr.isalpha() and (is_up or is_down):
                is_modifier = True
                char = w_curr
                action = "upper" if is_up else "lower"
                mod_start_idx = i
                mod_end_idx = i + 1
                if i > 0 and words[i-1].lower().strip(".,!?;:") == "with":
                    mod_start_idx = i - 1
            elif w_curr == "with" and i < len(words) - 2:
                w_mid = words[i+1].lower().strip(".,!?;:")
                w_last = words[i+2].lower().strip(".,!?;:")
                is_up = w_last in ("caps", "capital", "upper", "uppercase")
                is_down = w_last in ("small", "lowercase", "lower")
                if len(w_mid) == 1 and w_mid.isalpha() and (is_up or is_down):
                    is_modifier = True
                    char = w_mid
                    action = "upper" if is_up else "lower"
                    mod_start_idx = i
                    mod_end_idx = i + 2
                    
        # Look for: caps/small <letter>
        if not is_modifier and i < len(words) - 1:
            w_curr = words[i].lower().strip(".,!?;:")
            w_next = words[i+1].lower().strip(".,!?;:")
            is_up = w_curr in ("caps", "capital", "upper", "uppercase")
            is_down = w_curr in ("small", "lowercase", "lower")
            if (is_up or is_down) and len(w_next) == 1 and w_next.isalpha():
                is_modifier = True
                char = w_next
                action = "upper" if is_up else "lower"
                mod_start_idx = i
                mod_end_idx = i + 1

        if is_modifier:
            target_word_idx = -1
            
            # First, check adjacent words (standard behavior)
            idx_before = mod_start_idx - 1
            if idx_before >= 0:
                w_before = words[idx_before]
                if w_before.startswith("__PRESERVE_CASE__") and w_before.endswith("__"):
                    w_before = w_before[len("__PRESERVE_CASE__"):-2]
                clean_before = w_before.lower().strip(".,!?;:")
                if char in clean_before:
                    target_word_idx = idx_before
            
            if target_word_idx == -1:
                idx_after = mod_end_idx + 1
                if idx_after < len(words):
                    w_after = words[idx_after]
                    if w_after.startswith("__PRESERVE_CASE__") and w_after.endswith("__"):
                        w_after = w_after[len("__PRESERVE_CASE__"):-2]
                    clean_after = w_after.lower().strip(".,!?;:")
                    if char in clean_after:
                        target_word_idx = idx_after
            
            # Second, search backwards for the nearest word containing target letter
            if target_word_idx == -1:
                for idx in range(mod_start_idx - 1, -1, -1):
                    w_check = words[idx]
                    if w_check.startswith("__PRESERVE_CASE__") and w_check.endswith("__"):
                        w_check = w_check[len("__PRESERVE_CASE__"):-2]
                    clean_w = w_check.lower().strip(".,!?;:")
                    if char in clean_w:
                        target_word_idx = idx
                        break
                        
            # Third, search forwards for the nearest word containing target letter
            if target_word_idx == -1:
                for idx in range(mod_end_idx + 1, len(words)):
                    w_check = words[idx]
                    if w_check.startswith("__PRESERVE_CASE__") and w_check.endswith("__"):
                        w_check = w_check[len("__PRESERVE_CASE__"):-2]
                    clean_w = w_check.lower().strip(".,!?;:")
                    if char in clean_w:
                        target_word_idx = idx
                        break
            
            # Apply capitalization/lowercasing if a target word was found
            if target_word_idx != -1:
                word = words[target_word_idx]
                is_already_wrapped = word.startswith("__PRESERVE_CASE__") and word.endswith("__")
                if is_already_wrapped:
                    word = word[len("__PRESERVE_CASE__"):-2]
                
                char_lower = char.lower()
                idx_in_word = word.lower().find(char_lower)
                if idx_in_word >= 0:
                    repl_char = word[idx_in_word].upper() if action == "upper" else word[idx_in_word].lower()
                    word = word[:idx_in_word] + repl_char + word[idx_in_word + 1:]
                
                if wrap_preserve or is_already_wrapped:
                    words[target_word_idx] = f"__PRESERVE_CASE__{word}__"
                else:
                    words[target_word_idx] = word
                # Remove the modifier tokens from the list since we applied it
                del words[mod_start_idx : mod_end_idx + 1]
                continue
            
            # If no target word was found, keep the modifier tokens intact
            # so they can be processed contextually (e.g. against existing page input values)
            i = mod_end_idx + 1
            continue
            
        i += 1

    return " ".join(words)



class CommandSpellingCorrector:
    """
    Spelling correction service for user commands.
    Combines SymSpell (symmetric delete spelling correction) for fast edit-distance corrections
    with custom vocabulary and hard mappings to resolve context-specific voice errors
    (e.g., 'trail' -> 'trial', 'com' -> 'crm', 'notbad' -> 'notepad').

    Credentials (email, passwords, tokens) are ALWAYS skipped — their exact casing is preserved.

    Optimization: The heavy SymSpell dictionary load (~200–400ms) runs in a background
    daemon thread started at instantiation. The module import is now near-instant.
    correct() gracefully skips correction if the dictionary hasn't finished loading yet.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
            cls._instance._loading = False
        return cls._instance

    def __init__(self):
        if self._initialized or self._loading:
            return
        # Mark as loading immediately so __init__ is never re-entered
        self._loading = True
        self.sym_spell = None
        self.custom_vocabulary: dict = {}
        self.hard_mappings: dict = {}
        # Start the heavy dictionary load in a background daemon thread so the
        # module import is instant and the async event loop is never blocked.
        import threading
        threading.Thread(target=self._load, daemon=True, name="SymSpellLoader").start()

    def _load(self) -> None:
        """Run the full SymSpell initialisation in a background thread."""
        import time
        t0 = time.perf_counter()
        try:
            import symspellpy
            from symspellpy import SymSpell

            sym_spell = SymSpell(max_dictionary_edit_distance=2, prefix_length=7)

            # Locate default English frequency dictionary packaged with symspellpy
            symspell_dir = os.path.dirname(symspellpy.__file__)
            dictionary_path = os.path.join(symspell_dir, "frequency_dictionary_en_82_765.txt")

            if not sym_spell.load_dictionary(dictionary_path, term_index=0, count_index=1):
                logger.warning("Failed to load SymSpell default dictionary.")

            # Load the bigram dictionary for compound lookup helper support if needed
            bigram_path = os.path.join(symspell_dir, "frequency_bigramdictionary_en_243_342.txt")
            if os.path.exists(bigram_path):
                sym_spell.load_bigram_dictionary(bigram_path, term_index=0, count_index=2)

            # 1. Custom Vocabulary: Ensure these common app/automation terms are preserved
            # and have high frequencies so typos are corrected to them.
            custom_vocabulary = {
                "crm": 1000000000,
                "open": 900000000,
                "click": 800000000,
                "double": 700000000,
                "right": 700000000,
                "trial": 950000000,  # High frequency to bias towards 'trial' over 'trail'
                "notepad": 600000000,
                "spotify": 600000000,
                "chrome": 600000000,
                "youtube": 600000000,
                "scroll": 500000000,
                "cancel": 500000000,
                "website": 500000000,
                "browser": 500000000,
                "minimize": 500000000,
                "maximize": 500000000,
                "close": 500000000,
            }

            for word, freq in custom_vocabulary.items():
                sym_spell.create_dictionary_entry(word, freq)

            # 2. Hard Mappings: Direct replacements for homophones/phonetic confusions
            # where both words are valid in English, but only one makes sense in our command context.
            hard_mappings = {
                "trail": "trial",
                "com": "crm",
                "notbad": "notepad",
                "clik": "click",
                "opne": "open",
                "pla": "play",
                "pau": "pause",
                "serum": "crm",
                "video": "window",
            }

            # Atomically publish results — correct() checks _initialized before use
            self.sym_spell = sym_spell
            self.custom_vocabulary = custom_vocabulary
            self.hard_mappings = hard_mappings
            self._initialized = True
            elapsed = (time.perf_counter() - t0) * 1000
            logger.info(f"✅ CommandSpellingCorrector ready ({elapsed:.0f}ms, loaded in background thread)")

        except ImportError:
            logger.warning("⚠️ symspellpy not installed. Spelling correction will be disabled.")
            self.sym_spell = None
            self._initialized = False
        finally:
            self._loading = False

    def correct(self, text: str) -> str:
        """
        Correct spelling errors in a user command string.

        Pipeline:
          1. Apply caps-modifier first (e.g. "s caps" annotations) on the original text.
          2. Skip SymSpell correction entirely if the entire command looks like
             a credential/data-fill command (contains @, mixed case, or special chars).
          3. Otherwise correct word-by-word, skipping individual credential-like tokens.

        Returns the corrected string (casing preserved for credentials).
        """
        if not text:
            return text

        # Step 1: Resolve caps-modifier annotations BEFORE anything else.
        # This allows users to say "password reSet@123 s caps" to mean "reSet@123"
        text = apply_caps_modifier(text, wrap_preserve=True)

        if not self._initialized or not self.sym_spell:
            # Strip preserve wrapper if corrector not ready
            return re.sub(r'__PRESERVE_CASE__(.*?)__', r'\1', text)

        # Step 2: Check if the entire command is a data/credential command.
        # If ANY token looks like a credential, skip lowercasing the whole string —
        # instead, correct only the non-credential tokens (command verbs/nouns) and
        # leave credential tokens exactly as-is.
        words = text.split()
        if not words:
            return text

        corrected_words = []
        for word in words:
            # If this word was explicitly modified by a casing modifier, bypass correction and preserve exact casing
            if word.startswith("__PRESERVE_CASE__") and word.endswith("__"):
                unwrapped = word[len("__PRESERVE_CASE__"):-2]
                corrected_words.append(unwrapped)
                continue

            # If this token consists entirely of punctuation/non-alphanumeric characters, preserve it as-is
            if not re.search(r'[a-zA-Z0-9]', word):
                corrected_words.append(word)
                continue

            # If this token contains any digits, preserve it as-is (e.g. "4", "10", "2026", "L-2025-0026")
            if re.search(r'\d', word):
                corrected_words.append(word)
                continue

            # If this token looks like a credential, emit it unchanged (preserving case)
            if _is_credential_like(word):
                corrected_words.append(word)
                continue

            # Separate leading/trailing punctuation from the core word
            m = re.match(r'^([^a-zA-Z0-9]*)(.*?)([^a-zA-Z0-9]*)$', word)
            if m:
                prefix, core, suffix = m.groups()
            else:
                prefix, core, suffix = "", word, ""

            if not core:
                corrected_words.append(word)
                continue

            core_lower = core.lower()

            # Apply hard mappings
            if core_lower in self.hard_mappings:
                corrected_words.append(prefix + self.hard_mappings[core_lower] + suffix)
                continue

            # Preserve known custom vocabulary words
            if core_lower in self.custom_vocabulary:
                corrected_words.append(prefix + core_lower + suffix)
                continue

            # Query SymSpell for closest suggestions
            try:
                from symspellpy import Verbosity
                suggestions = self.sym_spell.lookup(core_lower, Verbosity.CLOSEST, max_edit_distance=2)
                if suggestions:
                    corrected_words.append(prefix + suggestions[0].term + suffix)
                else:
                    corrected_words.append(prefix + core_lower + suffix)
            except Exception as e:
                logger.debug(f"SymSpell lookup failed for '{word}': {e}")
                corrected_words.append(prefix + core_lower + suffix)

        return " ".join(corrected_words)


# Global singleton instance
spelling_corrector = CommandSpellingCorrector()
