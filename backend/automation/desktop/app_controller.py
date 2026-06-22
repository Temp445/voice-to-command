"""
ACE Voice Controller — Desktop App Controller
Open, close, and manage desktop applications.
Uses the dynamic AppScanner for discovery; falls back to a minimal static
registry for built-in Windows tools that are never "installed" in the normal sense.
"""

import asyncio
import os
import shutil
import string
import subprocess
import sys
import warnings
from pathlib import Path

# Suppress pywinauto warning for apps that don't have a standard GUI message loop
warnings.filterwarnings('ignore', category=RuntimeWarning, message='.*Application is not loaded correctly.*')

import psutil
if sys.platform == "win32":
    try:
        import pywinauto
    except ImportError:
        pass
from loguru import logger

from app.core.exceptions import AppNotFound, AutomationError


# ─── Minimal static fallback for built-in Windows tools ──────────────────────
# Only keep things that are NOT discoverable via the scanner (UWP URIs, system utils).
_BUILTIN_REGISTRY: dict[str, list[str]] = {
    "notepad":       ["notepad.exe"],
    "calculator":    ["calc.exe"],
    "paint":         ["mspaint.exe"],
    "settings":      ["ms-settings:"],
    "task manager":  ["Taskmgr.exe"],
    "control panel": ["control.exe"],
    "explorer":      ["explorer.exe"],
    "cmd":           ["cmd.exe"],
    "powershell":    ["powershell.exe"],
    "terminal":      ["wt.exe", "cmd.exe"],
    "word":          ["WINWORD.EXE"],
    "excel":         ["EXCEL.EXE"],
    "powerpoint":    ["POWERPNT.EXE"],
}


# ─── AppController ────────────────────────────────────────────────────────────

class AppController:
    """Controls opening, closing, and managing applications."""

    def __init__(self):
        if sys.platform != "win32":
            logger.warning(
                "AppController is designed for Windows. "
                "Some features may not work properly on this platform."
            )

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _resolve_candidates(self, key: str) -> list[str]:
        """
        Return a list of candidate executable paths/names for a given app key.
        Resolution order:
          1. Dynamic scanner (fuzzy)
          2. Static builtin registry (exact + substring)
          3. Raw name as-is (pass-through)
        """
        from automation.desktop.app_scanner import get_scanner
        scanner = get_scanner()

        candidates: list[str] = []

        # 1. Dynamic scanner lookup
        entry = scanner.find(key)
        if entry:
            candidates.append(entry.path)
            logger.debug(f"AppScanner matched '{key}' → '{entry.path}' (source: {entry.source})")
            return candidates   # scanner match is authoritative

        # 2. Static builtin registry
        if key in _BUILTIN_REGISTRY:
            candidates.extend(_BUILTIN_REGISTRY[key])
            return candidates

        # Substring fallback in builtin
        for reg_key, reg_exes in _BUILTIN_REGISTRY.items():
            if key in reg_key or reg_key in key:
                candidates.extend(reg_exes)
                logger.debug(f"Builtin fuzzy matched '{key}' → '{reg_key}'")
                return candidates

        # 3. Pass-through — maybe it's a raw exe name or in PATH
        candidates.append(key)
        return candidates

    @staticmethod
    def _launch(exe: str) -> bool:
        """
        Try to launch an executable. Returns True on success.
        Uses native Windows OS launching first for maximum reliability.
        """
        exe = exe.replace("{user}", os.environ.get("USERNAME", ""))

        if exe.startswith("ms-"):
            subprocess.Popen(f"start {exe}", shell=True)
            return True

        # Resolve to absolute path
        if Path(exe).is_absolute() and Path(exe).exists():
            abs_exe = exe
        else:
            abs_exe = shutil.which(exe)

        if not abs_exe and sys.platform != "darwin":
            return False
            
        if sys.platform == "darwin":
            # On Mac, just try to use 'open -a' with the raw exe name or path
            import subprocess
            app_name = Path(exe).stem if Path(exe).is_absolute() else exe
            subprocess.Popen(["open", "-a", app_name], shell=False)
            logger.info(f"Launched on Mac: {app_name}")
            return True

        if "chrome.exe" in abs_exe.lower():
            import subprocess
            subprocess.Popen([abs_exe, "--remote-debugging-port=9222", "--start-maximized"], shell=False, creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)
            logger.info(f"Launched Chrome with CDP: {abs_exe}")
            return True

        # Native OS launch (automatically focuses window on Windows)
        try:
            import subprocess
            if abs_exe.lower().endswith(".exe"):
                subprocess.Popen([abs_exe], shell=False, creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)
            else:
                subprocess.Popen(f'start "" "{abs_exe}"', shell=True)
        except Exception as e:
            logger.error(f"Failed to launch: {e}")
            return False

        logger.info(f"Launched: {abs_exe}")
        return True

    def navigate_file_dialog(self, folder_path: str) -> bool:
        """
        Scans for an open File Dialog. If found, forces it to foreground and navigates it.
        """
        if sys.platform != "win32":
            logger.debug("navigate_file_dialog is not natively supported on Mac.")
            return False
            
        try:
            from pywinauto import Desktop
            import pyautogui
            import time

            dialog_titles = ["Open", "Save As", "Select file", "Choose File to Upload", "File Upload"]
            
            target_win = None
            for win in Desktop(backend="win32").windows():
                try:
                    if win.is_visible() and win.window_text() in dialog_titles:
                        target_win = win
                        break
                except Exception as e:
                    logger.error(f"[{__name__}] {type(e).__name__}: {e}")
                    continue
                    
            if target_win:
                title = target_win.window_text()
                logger.info(f"[navigate_file_dialog] Found file dialog '{title}'. Forcing focus and navigating to {folder_path}")
                
                # Force the dialog to the foreground
                target_win.set_focus()
                time.sleep(0.2)
                
                # Alt+N focuses the "File name" input box in standard Windows file dialogs
                pyautogui.hotkey('alt', 'n')
                time.sleep(0.1)
                pyautogui.typewrite(str(folder_path))
                time.sleep(0.1)
                pyautogui.press('enter')
                
                # Move focus back to the file list so arrow keys work immediately
                time.sleep(0.1)
                pyautogui.hotkey('shift', 'tab')
                pyautogui.hotkey('shift', 'tab')
                
                return True
                
        except Exception as e:
            logger.debug(f"Failed to check/navigate file dialog: {e}")
            
        return False

    # ── Public API ────────────────────────────────────────────────────────────

    async def open_application(self, app_name: str) -> str:
        """Launch an application by friendly name."""
        clean = app_name.strip().rstrip(string.punctuation).strip()
        key = clean.lower()

        # Intercept common folders to handle native File Dialog navigation
        common_folders = {
            "pictures": Path.home() / "Pictures",
            "downloads": Path.home() / "Downloads",
            "documents": Path.home() / "Documents",
            "desktop": Path.home() / "Desktop",
            "music": Path.home() / "Music",
            "videos": Path.home() / "Videos",
        }
        
        if key in common_folders:
            folder_path = common_folders[key]
            if folder_path.exists():
                # Attempt to navigate an active file dialog first
                if self.navigate_file_dialog(folder_path):
                    return f"Navigated dialog to {key.title()}"
                
                # If no dialog is active, fallback to opening a new Explorer window
                try:
                    import subprocess
                    subprocess.Popen(f'start "" "{folder_path}"', shell=True)
                    return f"Opened {key.title()} folder"
                except Exception as e:
                    logger.error(f"Failed to open folder {folder_path}: {e}")

        candidates = self._resolve_candidates(key)

        for exe in candidates:
            try:
                if self._launch(exe):
                    from automation.desktop.window_manager import WindowManager
                    if not exe.startswith("ms-"):
                        WindowManager().force_focus_by_exe(exe)
                    # Wait for the app to spawn and steal focus so subsequent typing commands don't miss
                    await asyncio.sleep(2.0)
                    return f"Opening {clean}"
            except Exception as e:
                logger.warning(f"Failed to launch '{exe}': {e}")
                continue

        raise AppNotFound(clean)

    async def close_application(self, app_name: str, force: bool = False) -> str:
        """Terminate a running application by name."""
        from automation.desktop.app_scanner import get_scanner
        scanner = get_scanner()

        clean = app_name.strip().rstrip(string.punctuation).strip()
        key = clean.lower()
        killed: list[str] = []

        # 1. Try to close by specific window title FIRST
        from automation.desktop.window_manager import WindowManager
        wm = WindowManager()
        closed_count = wm.close_windows_by_title(key)
        if closed_count > 0 and not force:
            await asyncio.sleep(0.6)
            return f"Closed {closed_count} window(s) matching '{clean}'"

        # Collect candidate exe names for global kill fallback
        exe_names: list[str] = []
        entry = scanner.find(key)
        if entry:
            exe_names.append(entry.exe_name.lower())

        builtin = _BUILTIN_REGISTRY.get(key, [])
        for b in builtin:
            exe_names.append(Path(b).name.lower())

        if not exe_names:
            exe_names = [clean.lower() + ".exe", clean.lower()]

        if sys.platform == "darwin":
            for exe in set(exe_names):
                try:
                    cmd = ["pkill", "-f", exe.replace(".exe", "")]
                    if force:
                        cmd.insert(1, "-9")
                    result = subprocess.run(cmd, capture_output=True, text=True)
                    if result.returncode == 0:
                        killed.append(exe)
                except Exception as e:
                    logger.error(f"[{__name__}] {type(e).__name__}: {e}")
                    pass
        else:
            # 1. Close via native Windows taskkill
            for exe in set(exe_names):
                try:
                    cmd = ["taskkill", "/IM", exe]
                    if force:
                        cmd.insert(1, "/F")
                    result = subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        creationflags=subprocess.CREATE_NO_WINDOW
                    )
                    if result.returncode == 0 or "SUCCESS" in result.stdout:
                        killed.append(exe)
                except Exception as e:
                    logger.error(f"[{__name__}] {type(e).__name__}: {e}")
                    pass

        # 2. Pywinauto fallback for graceful close (if taskkill missed it)
        if not killed and sys.platform == "win32":
            for exe in set(exe_names):
                try:
                    app = pywinauto.Application(backend="uia").connect(path=exe)
                    for win in app.windows():
                        win.close()  # Graceful close
                    killed.append(exe)
                except Exception as e:
                    logger.error(f"[{__name__}] {type(e).__name__}: {e}")
                    pass

        if killed:
            # Wait briefly to let the OS process the close signal
            await asyncio.sleep(0.6)
            
            # Check if any of the killed executables are still running
            still_alive = False
            for exe in set(killed):
                for proc in psutil.process_iter(["name"]):
                    if (proc.info["name"] or "").lower() == exe.lower():
                        still_alive = True
                        break
                if still_alive:
                    break

            unique = set(k.replace(".exe", "").title() for k in killed)
            app_names = ", ".join(unique)

            if still_alive and not force:
                return f"{app_names} has unsaved changes. Please say 'Save'. 'Don't Save'. Or 'Cancel'."
            return f"Closed {app_names}"
            
        raise AppNotFound(clean)

    async def close_heavy_applications(self, threshold_mb: int = 500) -> str:
        """Finds and terminates non-critical processes exceeding the memory threshold."""
        whitelist = {
            "explorer.exe", "svchost.exe", "smss.exe", "csrss.exe",
            "wininit.exe", "services.exe", "lsass.exe", "winlogon.exe",
            "dwm.exe", "spoolsv.exe", "system", "system idle process",
            "registry", "memory compression", "taskmgr.exe", "searchapp.exe",
            "startmenuexperiencehost.exe", "ctfmon.exe", "conhost.exe",
            "python.exe", "node.exe", "code.exe",
        }

        killed_apps: list[str] = []
        total_freed = 0
        threshold_bytes = threshold_mb * 1024 * 1024

        for proc in psutil.process_iter(["pid", "name", "memory_info"]):
            try:
                name = proc.info["name"]
                if not name or name.lower() in whitelist:
                    continue
                mem = proc.info["memory_info"].rss
                if mem > threshold_bytes:
                    proc.kill()
                    killed_apps.append(name)
                    total_freed += mem
                    logger.info(
                        f"Killed heavy process: {name} (PID {proc.info['pid']}) "
                        f"— freed {mem / 1_048_576:.1f} MB"
                    )
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass

        if not killed_apps:
            return f"No non-critical applications exceeding {threshold_mb} MB found."

        unique = list({n.lower().replace(".exe", "") for n in killed_apps})
        freed_mb = total_freed / 1_048_576
        freed_str = f"{total_freed / 1_073_741_824:.2f} GB" if freed_mb > 1024 else f"{freed_mb:.0f} MB"
        return f"Freed {freed_str} of memory by closing: {', '.join(unique).title()}."

    async def run_terminal_command(self, cmd: str) -> str:
        """Execute a shell command and return its output."""
        try:
            result = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(result.communicate(), timeout=15.0)
            output = (stdout or b"").decode().strip()
            error  = (stderr or b"").decode().strip()

            if result.returncode != 0 and error:
                return f"Command failed: {error[:200]}"
            return output[:500] if output else "Command executed successfully"
        except asyncio.TimeoutError:
            return "Command timed out after 15 seconds"
        except Exception as e:
            raise AutomationError(f"Terminal command failed: {e}")
