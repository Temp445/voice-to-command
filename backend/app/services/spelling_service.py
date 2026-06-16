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
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
            
        try:
            import symspellpy
            from symspellpy import SymSpell, Verbosity
            
            self.sym_spell = SymSpell(max_dictionary_edit_distance=2, prefix_length=7)
            
            # Locate default English frequency dictionary packaged with symspellpy
            symspell_dir = os.path.dirname(symspellpy.__file__)
            dictionary_path = os.path.join(symspell_dir, "frequency_dictionary_en_82_765.txt")
            
            if not self.sym_spell.load_dictionary(dictionary_path, term_index=0, count_index=1):
                logger.warning("Failed to load SymSpell default dictionary.")
                
            # Load the bigram dictionary for compound lookup helper support if needed
            bigram_path = os.path.join(symspell_dir, "frequency_bigramdictionary_en_243_342.txt")
            if os.path.exists(bigram_path):
                self.sym_spell.load_bigram_dictionary(bigram_path, term_index=0, count_index=2)
                
            # 1. Custom Vocabulary: Ensure these common app/automation terms are preserved
            # and have high frequencies so typos are corrected to them.
            self.custom_vocabulary = {
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
            
            for word, freq in self.custom_vocabulary.items():
                self.sym_spell.create_dictionary_entry(word, freq)
                
            # 2. Hard Mappings: Direct replacements for homophones/phonetic confusions
            # where both words are valid in English, but only one makes sense in our command context.
            self.hard_mappings = {
                "trail": "trial",
                "com": "crm",
                "notbad": "notepad",
                "clik": "click",
                "opne": "open",
                "pla": "play",
                "pau": "pause",
            }
            
            self._initialized = True
            logger.info("✅ CommandSpellingCorrector service initialized successfully.")
            
        except ImportError:
            logger.warning("⚠️ symspellpy not installed. Spelling correction will be disabled.")
            self.sym_spell = None
            self._initialized = False

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
            # If this token looks like a credential, emit it unchanged (preserving case)
            if _is_credential_like(word):
                corrected_words.append(word)
                continue

            word_lower = word.lower()

            # Apply hard mappings
            if word_lower in self.hard_mappings:
                corrected_words.append(self.hard_mappings[word_lower])
                continue

            # Preserve known custom vocabulary words
            if word_lower in self.custom_vocabulary:
                corrected_words.append(word_lower)
                continue

            # Query SymSpell for closest suggestions
            try:
                from symspellpy import Verbosity
                suggestions = self.sym_spell.lookup(word_lower, Verbosity.CLOSEST, max_edit_distance=2)
                if suggestions:
                    corrected_words.append(suggestions[0].term)
                else:
                    corrected_words.append(word_lower)
            except Exception as e:
                logger.debug(f"SymSpell lookup failed for '{word}': {e}")
                corrected_words.append(word_lower)

        return " ".join(corrected_words)


# Global singleton instance
spelling_corrector = CommandSpellingCorrector()
