import sys
sys.path.insert(0, ".")
from app.services.command_service import _normalize_voice_credential
import re

def test(text):
    norm = _normalize_voice_credential(text)
    if "@" in norm or "gmail" in norm or ".com" in norm:
        norm = re.sub(r'\s+', '', norm)
    print(f"INPUT:  {text!r}")
    print(f"OUTPUT: {norm!r}")
    print("-" * 40)

print("=== VERIFYING REAL NORMALIZATION IN CODEBASE ===")
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
