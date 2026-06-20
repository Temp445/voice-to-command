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


def apply_caps_modifier(text: str) -> str:
    """
    Parse phrases like 'reset@123 S caps' or 'S capital reset@123' and capitalize
    the named letter in the adjacent word.
    
    Supported patterns:
      - "<word> <letter> caps"           e.g. "reset@123 s caps"    -> "reSet@123"
      - "<word> <letter> capital"        e.g. "reset@123 s capital"  -> "reSet@123"
      - "<word> with <letter> caps"      e.g. "reset@123 with s caps"
      - "<letter> caps <word>"           e.g. "s caps reset@123"     -> "reSet@123"
    """
    def _capitalize_char_in_word(word: str, char: str) -> str:
        char_lower = char.lower()
        idx = word.lower().find(char_lower)
        if idx >= 0:
            return word[:idx] + word[idx].upper() + word[idx + 1:]
        return word

    # Pattern: <word> [with] <letter> (caps|capital)
    def repl_word_first(m: re.Match) -> str:
        word, char = m.group(1), m.group(2)
        return _capitalize_char_in_word(word, char)

    text = re.sub(
        r'(\S+)\s+(?:with\s+)?([a-zA-Z])\s+(?:caps|capital)\b',
        repl_word_first,
        text,
        flags=re.IGNORECASE
    )

    # Pattern: <letter> (caps|capital) <word>
    def repl_letter_first(m: re.Match) -> str:
        char, word = m.group(1), m.group(2)
        return _capitalize_char_in_word(word, char)

    text = re.sub(
        r'([a-zA-Z])\s+(?:caps|capital)\s+(\S+)',
        repl_letter_first,
        text,
        flags=re.IGNORECASE
    )

    return text


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
        text = apply_caps_modifier(text)

        if not self._initialized or not self.sym_spell:
            return text

        # Step 2: Check if the entire command is a data/credential command.
        # If ANY token looks like a credential, skip lowercasing the whole string —
        # instead, correct only the non-credential tokens (command verbs/nouns) and
        # leave credential tokens exactly as-is.
        words = text.split()
        if not words:
            return text

        corrected_words = []
        for word in words:
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
