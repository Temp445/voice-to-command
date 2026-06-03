import re
import os

path = r"e:\Nivin_Sync\ACE\Voice\Voice_Controller_v1\backend\app\services\intent_registry.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

content = content.replace(
    "from automation.browser.browser_controller import BrowserController",
    "from automation.browser.browser_controller import BrowserController as BrowserController"
)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)
print("Patched intent_registry.py")
