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
        import ctypes
        try:
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            if not hwnd:
                raise ValueError("No foreground window found.")
            app = pywinauto.Application(backend="uia").connect(handle=hwnd)
            return app.window(handle=hwnd)
        except Exception as e:
            raise AutomationError(f"Could not get active window: {e}")

    def _resolve_title_alias(self, title: str) -> str:
        aliases = {
            "vscode": "visual studio code",
            "vs code": "visual studio code",
            "chrome": "google chrome",
            "edge": "microsoft edge",
        }
        return aliases.get(title.lower().strip(), title.lower().strip())

    def _find_window_by_title(self, title_substring: str):
        title_substring = self._resolve_title_alias(title_substring).replace("the ", "").strip()
        for win in Desktop(backend="uia").windows():
            try:
                title = win.window_text()
                if title and title_substring in title.lower():
                    return win
            except Exception:
                continue
        return None

    def minimize_by_title(self, title_substring: str) -> bool:
        win = self._find_window_by_title(title_substring)
        if win:
            win.minimize()
            logger.info(f"Minimized window matching: {title_substring}")
            return True
        return False

    def maximize_by_title(self, title_substring: str) -> bool:
        win = self._find_window_by_title(title_substring)
        if win:
            win.maximize()
            logger.info(f"Maximized window matching: {title_substring}")
            return True
        return False

    def focus_by_title(self, title_substring: str) -> bool:
        win = self._find_window_by_title(title_substring)
        if win:
            try:
                # Connect to the app's process to ensure we focus the active top-level window (e.g., a modal dialog)
                app = pywinauto.Application(backend="uia").connect(process=win.process_id())
                top_win = app.top_window()
                top_win.set_focus()
                logger.info(f"Focused top window of application matching: {title_substring}")
                return True
            except Exception as e:
                logger.warning(f"Could not focus {title_substring}: {e}")
        return False

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

    def close_window_by_title(self, title_substring: str) -> bool:
        title_substring = self._resolve_title_alias(title_substring)
        for win in Desktop(backend="uia").windows():
            try:
                title = win.window_text()
                if title and title_substring in title.lower():
                    win.close()
                    logger.info(f"Closed window matching: {title_substring}")
                    return True
            except Exception:
                continue
        return False

    def force_focus_by_title(self, title_substring: str) -> None:
        """Asynchronously wait for a window with the given title and force it to foreground."""
        import threading, time
        def _focus():
            time.sleep(1.0)
            try:
                lower_title = self._resolve_title_alias(title_substring)
                for win in Desktop(backend="uia").windows():
                    title = win.window_text()
                    if title and lower_title in title.lower():
                        win.set_focus()
                        break
            except Exception:
                pass
        threading.Thread(target=_focus, daemon=True).start()

    def force_focus_by_exe(self, exe_path: str) -> None:
        """Asynchronously wait for a process by exe path and force its window to foreground."""
        import threading, time
        def _focus():
            time.sleep(1.5)
            try:
                app = pywinauto.Application(backend="uia").connect(path=exe_path, timeout=3)
                app.top_window().set_focus()
            except Exception:
                pass
        threading.Thread(target=_focus, daemon=True).start()

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
