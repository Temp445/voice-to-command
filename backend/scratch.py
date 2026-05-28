import re

text = "open Notepad and type hello."
parts = re.split(r'(?i)\s+(?:and|then)\s+', text)
print("Parts:", parts)

# simulate regex match
import sys
sys.path.append(r"e:\Nivin_Sync\ACE\Voice\Voice_Controller_v1\backend")
from app.services.command_service import command_service
from app.services.intent_registry import register_all_intents

register_all_intents()

for part in parts:
    i_name, params = command_service._regex_match(part)
    print(f"Match for '{part}': {i_name}, {params}")
