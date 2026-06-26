import re

def _normalize_voice_credential(raw: str) -> str:
    import re as _re

    # Pre-process multi-word symbol expressions
    raw = _re.sub(r'\bat the rate of\b', 'at', raw, flags=_re.IGNORECASE)
    raw = _re.sub(r'\bat the rate\b', 'at', raw, flags=_re.IGNORECASE)
    raw = _re.sub(r'\bshift two\b', 'at', raw, flags=_re.IGNORECASE)
    raw = _re.sub(r'\bshift 2\b', 'at', raw, flags=_re.IGNORECASE)
    raw = _re.sub(r'\bexclamation (?:mark|point)\b', 'exclamation', raw, flags=_re.IGNORECASE)
    raw = _re.sub(r'\bquestion mark\b', 'question', raw, flags=_re.IGNORECASE)
    raw = _re.sub(r'\bhash\s*tag\b', 'hash', raw, flags=_re.IGNORECASE)

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
    _NOISE = {'yes', 'end', 'stop', 'done', 'ok', 'okay', 'confirm', 'case', 'please'}

    tokens = raw.split()
    result = []
    i = 0
    all_caps_mode = False
    caps_next = False

    while i < len(tokens):
        raw_tok = tokens[i]
        tok = raw_tok.lower().strip(".,!?;:'\"-")

        if tok in ('caps', 'cap', 'upper', 'uppercase'):
            caps_next = True
            i += 1
            continue

        if tok == 'all' and i + 1 < len(tokens) and tokens[i + 1].lower().strip('.,') in ('caps', 'cap', 'upper'):
            all_caps_mode = True
            i += 2
            continue

        if tok in ('no', 'lower', 'lowercase', 'normal'):
            all_caps_mode = False
            caps_next = False
            i += 1
            continue

        remaining_real = [t.lower().strip(".,!?;:") for t in tokens[i:]]
        if all(t in _NOISE or t in ('caps', 'cap', 'all', 'upper') for t in remaining_real):
            break

        if tok in _SYMBOLS:
            ch = _SYMBOLS[tok]
            result.append(ch.upper() if all_caps_mode else ch)
            caps_next = False
            i += 1
            continue

        if tok in _TENS:
            tens_str = _TENS[tok]
            if tok == 'hundred':
                result.append(tens_str)
                i += 1
                continue
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

        if tok in _ONES:
            result.append(_ONES[tok])
            caps_next = False
            i += 1
            continue

        word = raw_tok.strip(".,!?;:")
        if all_caps_mode:
            word = word.upper()
        elif caps_next:
            word = word[0].upper() + word[1:] if word else word
            caps_next = False
        result.append(word)
        i += 1

    return ''.join(result)

def test(text):
    norm = _normalize_voice_credential(text)
    if "@" in norm or "gmail" in norm or ".com" in norm:
        norm = re.sub(r'\s+', '', norm)
    print(f"INPUT:  {text!r}")
    print(f"OUTPUT: {norm!r}")
    print("-" * 40)

test("nivin3456@gmail.com")
test("nivin thirty four fifty six at gmail dot com")
test("nivin three four five six at gmail dot com")
test("reSet@123")
test("reSet at one two three")
test("reSet at 1 2 3")
test("reSet at 123")
test("reSet shift two 123")
test("reSet shift 2 123")
test("reSet at the rate 123")
test("reSet at the rate one two three")
