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
    "vs code":      ["code.exe", r"D:\Users\{user}\AppData\Local\Programs\Microsoft VS Code\Code.exe", r"C:\Users\{user}\AppData\Local\Programs\Microsoft VS Code\Code.exe", r"C:\Program Files\Microsoft VS Code\Code.exe"],
    "vscode":       ["code.exe", r"D:\Users\{user}\AppData\Local\Programs\Microsoft VS Code\Code.exe", r"C:\Users\{user}\AppData\Local\Programs\Microsoft VS Code\Code.exe"],
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
        import string
        # Strip trailing punctuation Whisper often adds (e.g. "Chrome." → "Chrome")
        clean_name = app_name.strip().rstrip(string.punctuation).strip()
        key = clean_name.lower()

        executables = APP_REGISTRY.get(key)
        # Fuzzy fallback: check if key is a substring of any registry entry
        if not executables:
            for reg_key, reg_exes in APP_REGISTRY.items():
                if key in reg_key or reg_key in key:
                    executables = reg_exes
                    logger.debug(f"Fuzzy matched '{key}' → '{reg_key}'")
                    break
        if not executables:
            executables = [clean_name]

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
                        return f"Opening {clean_name}"
                    
            except Exception as e:
                logger.warning(f"Failed to launch '{exe}': {e}")
                continue

        raise AppNotFound(clean_name)

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

    async def close_heavy_applications(self, threshold_mb: int = 500) -> str:
        """Finds and terminates non-critical processes exceeding the memory threshold."""
        # Whitelist of critical Windows processes, your IDE, and the ACE infrastructure
        whitelist = [
            "explorer.exe", "svchost.exe", "smss.exe", "csrss.exe", 
            "wininit.exe", "services.exe", "lsass.exe", "winlogon.exe", 
            "dwm.exe", "spoolsv.exe", "system", "system idle process", 
            "registry", "memory compression", "taskmgr.exe", "searchapp.exe",
            "startmenuexperiencehost.exe", "ctfmon.exe", "conhost.exe",
            # Development and ACE processes
            "python.exe", "node.exe", "code.exe"
        ]

        killed_apps = []
        total_freed_bytes = 0
        threshold_bytes = threshold_mb * 1024 * 1024

        for proc in psutil.process_iter(["pid", "name", "memory_info"]):
            try:
                proc_name = proc.info["name"]
                if not proc_name:
                    continue

                proc_name_lower = proc_name.lower()
                
                # Check whitelist
                if any(proc_name_lower == w for w in whitelist):
                    continue
                
                mem_bytes = proc.info["memory_info"].rss
                if mem_bytes > threshold_bytes:
                    proc.kill()
                    killed_apps.append(proc_name)
                    total_freed_bytes += mem_bytes
                    logger.info(f"Killed heavy process: {proc_name} (PID: {proc.info['pid']}) - Freed {mem_bytes / (1024*1024):.2f} MB")
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass

        if not killed_apps:
            return f"No non-critical applications exceeding {threshold_mb} MB were found."

        # Simplify the killed apps list (e.g. 5x chrome.exe -> chrome.exe)
        unique_killed = list(set([name.lower().replace('.exe', '') for name in killed_apps]))
        freed_gb = total_freed_bytes / (1024 * 1024 * 1024)
        freed_mb = total_freed_bytes / (1024 * 1024)
        
        if freed_gb > 1.0:
            freed_str = f"{freed_gb:.2f} GB"
        else:
            freed_str = f"{freed_mb:.0f} MB"

        return f"Freed {freed_str} of memory by closing: {', '.join(unique_killed).title()}."

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
