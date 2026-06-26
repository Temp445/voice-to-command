import re

with open("app/services/intent_registry.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if (".click(" in line or ".fill(" in line or ".type(" in line) and "logger" not in line and "def " not in line:
        print(f"Line {i+1}: {line.strip()}")
