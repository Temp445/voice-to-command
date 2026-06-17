"""
ACE Voice Controller — Window Manager
Manage window state using pywinauto.
"""

import sys
import os

if sys.platform == "win32":
    try:
        import pywinauto
        from pywinauto import Desktop
    except ImportError:
        pass
from loguru import logger
from app.core.exceptions import AutomationError


class WindowManager:
    """Enumerate and control windows using pywinauto."""

    def _get_active_window(self):
        if sys.platform != "win32":
            raise AutomationError("Active window detection is only supported on Windows.")
            
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
        if sys.platform != "win32":
            return None
            
        title_substring = self._resolve_title_alias(title_substring).lower()
        filler_words = {"the", "a", "an", "my", "this", "file", "folder", "app", "application", "document"}
        search_words = [w for w in title_substring.split() if w not in filler_words]
        
        # 1. Try to match by automated browser Process PIDs first
        import psutil
        ace_pids = set()
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                name = proc.info['name']
                if name and name.lower() in ['chrome.exe', 'msedge.exe', 'firefox.exe', 'chrome', 'firefox']:
                    cmdline = proc.info.get('cmdline')
                    if cmdline:
                        cmd_str = " ".join(cmdline)
                        if 'ACE' in cmd_str and ('BrowserProfile' in cmd_str or '9222' in cmd_str):
                            ace_pids.add(proc.info['pid'])
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
                
        # 2. Enumerate visible windows
        try:
            # First pass: try to find a visible window belonging to one of the ACE PIDs
            if ace_pids:
                for win in Desktop(backend="win32").windows():
                    try:
                        if not win.is_visible() or not win.window_text():
                            continue
                        if win.process_id() in ace_pids:
                            logger.info(f"Found automated browser window matching PID {win.process_id()}: '{win.window_text()}'")
                            return win
                    except Exception:
                        continue
            
            # Second pass: fallback to title substring matching
            for win in Desktop(backend="win32").windows():
                try:
                    if not win.is_visible() or not win.window_text():
                        continue
                    win_text = win.window_text().lower()
                    if win_text and all(word in win_text for word in search_words):
                        return win
                except Exception:
                    continue
        except NameError:
            pass
        return None

    def minimize_by_title(self, title_substring: str) -> bool:
        if sys.platform == "darwin":
            # Stub for Mac
            logger.info("Mac minimize not fully supported yet.")
            return False
            
        win = self._find_window_by_title(title_substring)
        if win:
            win.minimize()
            logger.info(f"Minimized window matching: {title_substring}")
            return True
        return False

    def maximize_by_title(self, title_substring: str) -> bool:
        if sys.platform == "darwin":
            logger.info("Mac maximize not fully supported yet.")
            return False
            
        win = self._find_window_by_title(title_substring)
        if win:
            import ctypes
            hwnd = win.handle
            ctypes.windll.user32.ShowWindow(hwnd, 3)
            ctypes.windll.user32.PostMessageW(hwnd, 0x0112, 0xF030, 0)
            logger.info(f"Maximized window matching: {title_substring}")
            return True
        return False

    def focus_by_title(self, title_substring: str) -> bool:
        if sys.platform == "darwin":
            title_substring = self._resolve_title_alias(title_substring)
            os.system(f"osascript -e 'tell application \"{title_substring}\" to activate'")
            logger.info(f"Sent activate signal to {title_substring} on Mac.")
            return True
            
        win = self._find_window_by_title(title_substring)
        if win:
            import ctypes
            try:
                user32 = ctypes.windll.user32
                hwnd = win.handle
                
                # 1. Temporarily disable foreground lock timeout
                timeout = ctypes.c_uint()
                user32.SystemParametersInfoW(0x2000, 0, ctypes.byref(timeout), 0)
                user32.SystemParametersInfoW(0x2001, 0, ctypes.c_void_p(0), 0x02)
                
                # 2. Minimize and then maximize (this forces the OS to rebuild the Z-order and focus)
                user32.ShowWindow(hwnd, 6) # SW_MINIMIZE
                user32.ShowWindow(hwnd, 3) # SW_SHOWMAXIMIZED
                user32.PostMessageW(hwnd, 0x0112, 0xF030, 0) # WM_SYSCOMMAND, SC_MAXIMIZE
                
                # 3. Use undocumented SwitchToThisWindow to force activation
                user32.SwitchToThisWindow(hwnd, True)
                
                # 4. Try BringWindowToTop and SetForegroundWindow
                user32.BringWindowToTop(hwnd)
                user32.SetForegroundWindow(hwnd)
                
                # 5. Use AttachThreadInput and Alt-key hijacking
                foreground_hwnd = user32.GetForegroundWindow()
                if hwnd != foreground_hwnd:
                    foreground_thread = user32.GetWindowThreadProcessId(foreground_hwnd, None)
                    current_thread = ctypes.windll.kernel32.GetCurrentThreadId()
                    
                    if foreground_thread != current_thread:
                        # Press/release Alt key to grab foreground permission
                        user32.keybd_event(0x12, 0, 0, 0)
                        user32.keybd_event(0x12, 0, 2, 0)
                        
                        user32.AttachThreadInput(current_thread, foreground_thread, True)
                        user32.SetForegroundWindow(hwnd)
                        user32.SetFocus(hwnd)
                        user32.AttachThreadInput(current_thread, foreground_thread, False)
                    else:
                        user32.SetForegroundWindow(hwnd)
                else:
                    user32.SetForegroundWindow(hwnd)
                    
                # Restore original foreground lock timeout
                user32.SystemParametersInfoW(0x2001, 0, ctypes.c_void_p(timeout.value), 0x02)
                
                logger.info(f"Focused and maximized window matching: {title_substring}")
                return True
            except Exception as e:
                logger.warning(f"Could not focus {title_substring}: {e}")
        return False

    def minimize_active(self) -> None:
        if sys.platform != "win32": return
        win = self._get_active_window()
        win.minimize()
        logger.info("Window minimized")

    def maximize_active(self) -> None:
        if sys.platform != "win32": return
        win = self._get_active_window()
        win.maximize()
        logger.info("Window maximized")

    def close_active(self) -> None:
        if sys.platform != "win32": return
        win = self._get_active_window()
        win.close()
        logger.info("Window closed")

    def restore_active(self) -> None:
        if sys.platform != "win32": return
        win = self._get_active_window()
        win.restore()
        logger.info("Window restored")

    def close_windows_by_title(self, title_substring: str) -> int:
        if sys.platform == "darwin":
            os.system(f"osascript -e 'tell application \"{title_substring}\" to quit'")
            return 1
            
        title_substring = self._resolve_title_alias(title_substring).lower()
        # Remove common filler words that the user might say
        filler_words = {"the", "a", "an", "my", "this", "file", "folder", "app", "application", "document"}
        search_words = [w for w in title_substring.split() if w not in filler_words]
        closed_count = 0
        try:
            for win in Desktop(backend="uia").windows():
                try:
                    win_text = win.window_text().lower()
                    if win_text and all(word in win_text for word in search_words):
                        win.close()
                        closed_count += 1
                except Exception:
                    continue
        except NameError:
            pass
            
        if closed_count > 0:
            logger.info(f"Closed {closed_count} window(s) matching: {title_substring}")
        return closed_count

    def close_all_workspaces(self, exclude_titles: list[str] = None) -> int:
        """
        Safely closes all top-level windows by sending graceful close signals.
        This ensures apps prompt to save unsaved work instead of data loss.
        """
        if sys.platform != "win32":
            logger.info("close_all_workspaces not natively supported on Mac.")
            return 0
            
        exclude_titles = [t.lower() for t in (exclude_titles or [])]
        # Always exclude essential desktop shell components
        system_excludes = ["program manager", "taskbar", "settings", "ace voice", "action center"]
        
        closed_count = 0
        try:
            for win in Desktop(backend="win32").windows():
                try:
                    if not win.is_visible() or not win.window_text():
                        continue
                        
                    win_text = win.window_text().lower()
                    
                    # Check exclusions
                    if any(ext in win_text for ext in system_excludes + exclude_titles):
                        continue
                    
                    # Close gracefully
                    win.close()
                    closed_count += 1
                except Exception:
                    continue
        except NameError:
            pass
                
        logger.info(f"Gracefully closed {closed_count} workspace windows.")
        return closed_count

    def close_window_by_title(self, title_substring: str) -> bool:
        return self.close_windows_by_title(title_substring) > 0

    def force_focus_by_title(self, title_substring: str) -> None:
        """Asynchronously wait for a window with the given title and force it to foreground."""
        if sys.platform == "darwin":
            os.system(f"osascript -e 'tell application \"{title_substring}\" to activate'")
            return
            
        import threading, time
        def _focus():
            time.sleep(1.0)
            try:
                self.focus_by_title(title_substring)
                win = self._find_window_by_title(title_substring)
                if win:
                    try:
                        import ctypes
                        ctypes.windll.user32.ShowWindow(win.handle, 3)
                        ctypes.windll.user32.PostMessageW(win.handle, 0x0112, 0xF030, 0)
                    except Exception:
                        pass
            except Exception:
                pass
        threading.Thread(target=_focus, daemon=True).start()

    def force_focus_by_exe(self, exe_path: str) -> None:
        """Asynchronously wait for a process by exe path and force its window to foreground."""
        if sys.platform != "win32": return
        
        import threading, time
        def _focus():
            time.sleep(1.5)
            try:
                app = pywinauto.Application(backend="uia").connect(path=exe_path, timeout=3)
                top = app.top_window()
                top.set_focus()
                try:
                    top.maximize()
                except Exception:
                    pass
            except Exception:
                pass
        threading.Thread(target=_focus, daemon=True).start()

    def list_windows(self) -> list[dict]:
        """Return all visible top-level windows."""
        if sys.platform != "win32": return []
        windows = []
        try:
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
        except NameError:
            pass
        return windows
