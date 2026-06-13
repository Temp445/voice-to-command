"""Clipboard and screenshot utilities."""

import subprocess
import datetime
from pathlib import Path
import pyautogui
import pyperclip


class ClipboardManager:
    def screenshot(self) -> str:
        """Take a screenshot and save it to the desktop."""
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        path = Path.home() / "Desktop" / f"screenshot_{ts}.png"

        # Use PyAutoGUI to capture screenshot
        pyautogui.screenshot(str(path))
        return str(path)

    def read_text(self) -> str:
        """Read text from the clipboard."""
        try:
            content = pyperclip.paste()
            return content if content else "Clipboard is empty."
        except Exception as e:
            return f"Failed to read clipboard: {e}"

    def write_text(self, text: str) -> str:
        """Write text to the clipboard."""
        try:
            pyperclip.copy(text)
            return "Copied to clipboard."
        except Exception as e:
            return f"Failed to copy to clipboard: {e}"

    def clear(self) -> str:
        """Clear the clipboard."""
        try:
            pyperclip.copy('')
            return "Clipboard cleared."
        except Exception as e:
            return f"Failed to clear clipboard: {e}"
