import re

pattern = r"^(?:cancel|escape|(?:close|hide)\s+(?:the\s+)?(?:popup|overlay|modal|dialog|video|window|ad|card|box|banner|sidebar|side\s*bar|menu|drawer|panel)|dismiss|press\s+escape|close\s+it)(?:\s+.*)?$"
rx = re.compile(pattern, re.IGNORECASE)

tests = [
    "close the sidebar",
    "close sidebar",
    "hide the sidebar",
    "close the menu",
    "close popup",
    "cancel the request",
    "cancel",
    "escape",
]

for t in tests:
    m = rx.match(t)
    print(f"{t!r:25} -> {'Match' if m else 'No Match'}")
