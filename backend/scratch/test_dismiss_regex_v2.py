import re

patterns = [
    r"^(?:cancel|escape|dismiss|press\s+escape|close\s+it)(?:\s+.*)?$",
    r"^(?:close|hide|cancel|dismiss)\s+(?:the\s+)?(?:[\w\s]+\s+)?(?:popup|pop\s*up|overlay|modal|dialog|video|window|ad|card|box|banner|sidebar|side\s*bar|menu|drawer|panel|request|form|details|pane|sheet)(?:\s+.*)?$"
]

rxs = [re.compile(p, re.IGNORECASE) for p in patterns]

tests = [
    "close the request",
    "close the view advance request",
    "close the advance request",
    "close request",
    "close the form",
    "close view advance request",
    "cancel the request",
    "dismiss details"
]

for t in tests:
    matched = any(rx.match(t) for rx in rxs)
    print(f"{t!r:35} -> {'Match' if matched else 'No Match'}")
