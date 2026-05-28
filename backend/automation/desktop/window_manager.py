"""
ACE Voice Controller — Window Manager
Manage window state using pywinauto.
"""

import pywinauto
from pywinauto import Desktop
from loguru import logger
from app.core.exceptions import AutomationError


class WindowManager:
    """Enumerate and control windows using pywinauto."""

    def _get_active_window(self):
        try:
            return Desktop(backend="uia").get_active()
        except Exception as e:
            raise AutomationError(f"Could not get active window: {e}")

    def minimize_active(self) -> None:
        win = self._get_active_window()
        win.minimize()
        logger.info("Window minimized")

    def maximize_active(self) -> None:
        win = self._get_active_window()
        win.maximize()
        logger.info("Window maximized")

    def close_active(self) -> None:
        win = self._get_active_window()
        win.close()
        logger.info("Window closed")

    def restore_active(self) -> None:
        win = self._get_active_window()
        win.restore()
        logger.info("Window restored")

    def list_windows(self) -> list[dict]:
        """Return all visible top-level windows."""
        windows = []
        for win in Desktop(backend="uia").windows():
            try:
                title = win.window_text()
                if title.strip():
                    windows.append({
                        "title": title,
                        "class": win.class_name(),
                    })
            except Exception:
                continue
        return windows
