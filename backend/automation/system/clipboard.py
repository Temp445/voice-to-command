"""Clipboard and screenshot utilities."""

import subprocess
import datetime
from pathlib import Path
import pyautogui


class ClipboardManager:
    def screenshot(self) -> str:
        """Take a screenshot and save it to the desktop."""
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        path = Path.home() / "Desktop" / f"screenshot_{ts}.png"

        # Use PyAutoGUI to capture screenshot
        pyautogui.screenshot(str(path))
        return str(path)
