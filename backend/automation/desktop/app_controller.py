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
import pywinauto
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

        if not abs_exe:
            return False

        # Native OS launch (automatically focuses window on Windows)
        try:
            os.startfile(abs_exe)
        except AttributeError:
            subprocess.Popen([abs_exe], shell=False)
        except Exception as e:
            logger.error(f"Failed to launch via OS native methods: {e}")
            # Fallback to subprocess if startfile fails for any reason
            subprocess.Popen([abs_exe], shell=False)

        # Force focus to prevent taskbar blinking
        from automation.desktop.window_manager import WindowManager
        WindowManager().force_focus_by_exe(abs_exe)

        logger.info(f"Launched: {abs_exe}")
        return True

    # ── Public API ────────────────────────────────────────────────────────────

    async def open_application(self, app_name: str) -> str:
        """Launch an application by friendly name."""
        clean = app_name.strip().rstrip(string.punctuation).strip()
        key = clean.lower()

        candidates = self._resolve_candidates(key)

        for exe in candidates:
            try:
                if self._launch(exe):
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

        # Collect candidate exe names
        exe_names: list[str] = []
        entry = scanner.find(key)
        if entry:
            exe_names.append(entry.exe_name.lower())

        builtin = _BUILTIN_REGISTRY.get(key, [])
        for b in builtin:
            exe_names.append(Path(b).name.lower())

        if not exe_names:
            exe_names = [clean.lower() + ".exe", clean.lower()]

        # 1. Close via native Windows taskkill
        # taskkill without /F sends a graceful WM_CLOSE signal.
        # This natively triggers the "Save/Don't Save" prompt if there are unsaved changes.
        # If force=True, /F forcefully terminates without saving.
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
            except Exception:
                pass

        # 2. Pywinauto fallback for graceful close (if taskkill missed it)
        if not killed:
            for exe in set(exe_names):
                try:
                    app = pywinauto.Application(backend="uia").connect(path=exe)
                    for win in app.windows():
                        win.close()  # Graceful close
                    killed.append(exe)
                except Exception:
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
                return f"{app_names} has unsaved changes. Please say 'save', 'don't save', or 'cancel'."
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
