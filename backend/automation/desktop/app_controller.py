"""
ACE Voice Controller — Desktop App Controller
Open, close, and manage desktop applications using pywinauto + subprocess.
"""

import asyncio
import subprocess
import sys
from pathlib import Path
import psutil
import pywinauto
from loguru import logger
from app.core.exceptions import AppNotFound, AutomationError


# Map of friendly names → executable paths / process names
APP_REGISTRY: dict[str, list[str]] = {
    "notepad":      ["notepad.exe"],
    "vs code":      ["code.exe", r"C:\Users\{user}\AppData\Local\Programs\Microsoft VS Code\Code.exe", r"C:\Program Files\Microsoft VS Code\Code.exe"],
    "vscode":       ["code.exe"],
    "chrome":       ["chrome.exe", r"C:\Program Files\Google\Chrome\Application\chrome.exe"],
    "firefox":      ["firefox.exe"],
    "edge":         ["msedge.exe", r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe", r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"],
    "microsoft edge":["msedge.exe", r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe", r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"],
    "explorer":     ["explorer.exe"],
    "calculator":   ["calc.exe"],
    "paint":        ["mspaint.exe"],
    "word":         ["WINWORD.EXE"],
    "excel":        ["EXCEL.EXE"],
    "powerpoint":   ["POWERPNT.EXE"],
    "task manager": ["Taskmgr.exe"],
    "control panel":["control.exe"],
    "settings":     ["ms-settings:"],
    "spotify":      ["Spotify.exe"],
    "discord":      ["Discord.exe"],
    "slack":        ["slack.exe"],
    "teams":        ["Teams.exe"],
    "terminal":     ["wt.exe", "cmd.exe"],
    "cmd":          ["cmd.exe"],
    "powershell":   ["powershell.exe"],
}


class AppController:
    """Controls opening, closing, and managing applications."""

    def __init__(self):
        if sys.platform != "win32":
            logger.warning("AppController is designed for Windows. Some features (like pywinauto and os.startfile) may not work properly on this platform.")

    async def open_application(self, app_name: str) -> str:
        """Launch an application by friendly name or executable path."""
        import os
        import shutil
        key = app_name.lower().strip()
        executables = APP_REGISTRY.get(key, [app_name])

        for exe in executables:
            try:
                if exe.startswith("ms-"):
                    # Windows Settings URI
                    subprocess.Popen(f"start {exe}", shell=True)
                    return f"Opened {app_name}"
                else:
                    # Try username substitution
                    exe = exe.replace("{user}", os.environ.get("USERNAME", ""))
                    
                    # Check if it exists as an absolute path or in PATH
                    absolute_exe = exe if Path(exe).is_absolute() and Path(exe).exists() else shutil.which(exe)
                    
                    if absolute_exe:
                        try:
                            # Properly use pywinauto to start and force focus on standard Win32 apps
                            app = pywinauto.Application(backend="uia").start(absolute_exe, timeout=10)
                            try:
                                # Wait a moment for the window to become available and bring to front
                                app.window(active_only=False).set_focus()
                            except Exception:
                                pass # Window might not be ready yet, or is hidden
                        except Exception:
                            # Fallback to os.startfile which handles UWP apps natively
                            try:
                                os.startfile(absolute_exe)
                            except AttributeError:
                                subprocess.Popen([absolute_exe], shell=False)
                        
                        logger.info(f"Launched: {absolute_exe}")
                        return f"Opening {app_name}"
                    
            except Exception as e:
                logger.warning(f"Failed to launch '{exe}': {e}")
                continue

        raise AppNotFound(app_name)

    async def close_application(self, app_name: str) -> str:
        """Terminate a running application by name."""
        key = app_name.lower().strip()
        executables = APP_REGISTRY.get(key, [app_name])
        process_names = [Path(exe).name for exe in executables]

        killed = []

        # 1. Properly use pywinauto to connect and kill gracefully
        for exe_path in executables:
            try:
                # Try connecting by executable path
                app = pywinauto.Application(backend="uia").connect(path=exe_path)
                app.kill()
                killed.append(Path(exe_path).name)
            except Exception:
                pass

        # 2. Fallback to psutil for UWP apps and stubborn processes
        for proc in psutil.process_iter(["name", "pid"]):
            try:
                if proc.info["name"] and proc.info["name"].lower() in [p.lower() for p in process_names]:
                    proc.kill()
                    killed.append(proc.info["name"])
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        if killed:
            return f"Closed: {', '.join(set(killed))}"
        raise AppNotFound(app_name)

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
            error = (stderr or b"").decode().strip()

            if result.returncode != 0 and error:
                return f"Command failed: {error[:200]}"
            return output[:500] if output else "Command executed successfully"
        except asyncio.TimeoutError:
            return "Command timed out after 15 seconds"
        except Exception as e:
            raise AutomationError(f"Terminal command failed: {e}")
