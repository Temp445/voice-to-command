import re

# Updated regex patterns for click_text
click_text_patterns = [
    r"(?:click|tap)\s+(?:on\s+)?(?P<text>.+)",
    r"(?:go\s+to|navigate\s+to)\s+(?P<text>[^\.]+)$",
    r"^(?:open|toggle|show|expand|collapse)\s+(?:the\s+)?(?P<text>(?:sidebar|side\s*bar|menu|drawer|panel|tab|modal|dialog|popup|pop-up|dropdown|drop-down|overlay|widget|toolbar|navbar|nav\s*bar|hamburger|navigation).*)$",
    r"^(?P<action>edit|update|change|modify|view|show|inspect)\s+(?:on\s+)?(?:the\s+)?(?P<text>.+)$",
]

compiled = [re.compile(p, re.IGNORECASE) for p in click_text_patterns]

test_phrases = [
    "edit the 6 months installments request",
    "edit 6 months installments request",
    "update the amount",
    "change username",
    "modify settings",
    "view the employee Nivin S request",
    "view the nivin request",
    "show the employee Nivin S request",
    "inspect settings",
]

for phrase in test_phrases:
    matched = False
    for pattern in compiled:
        m = pattern.search(phrase)
        if m:
            print(f"Phrase: '{phrase}' -> Matches pattern: {pattern.pattern}")
            print(f"  Matched groups: {m.groupdict()}")
            matched = True
            break
    if not matched:
        print(f"Phrase: '{phrase}' -> NO MATCH")
