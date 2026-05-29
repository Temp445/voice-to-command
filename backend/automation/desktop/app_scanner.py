"""
ACE Voice Controller — Dynamic Application Scanner
Discovers installed applications from multiple Windows sources:
  - Start Menu shortcuts (.lnk)
  - Desktop shortcuts (.lnk)
  - Windows Registry (Uninstall keys)
  - Program Files directories
  - Running processes (psutil)

Results are stored in a local JSON cache for instant lookup.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import winreg
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

import psutil
from loguru import logger
from rapidfuzz import fuzz, process as fuzz_process


# ─── Data Model ──────────────────────────────────────────────────────────────

@dataclass
class AppEntry:
    name: str           # Friendly display name (e.g. "Google Chrome")
    exe_name: str       # Basename of exe (e.g. "chrome.exe")
    path: str           # Absolute path to executable
    source: str         # Where it was discovered: start_menu / registry / programs / process / desktop


# ─── Paths ───────────────────────────────────────────────────────────────────

CACHE_PATH = Path(__file__).resolve().parent.parent.parent / "app_cache.json"

# Executables that are system internals and should never appear in results
_SYSTEM_EXE_BLACKLIST = {
    "svchost.exe", "smss.exe", "csrss.exe", "wininit.exe", "services.exe",
    "lsass.exe", "winlogon.exe", "dwm.exe", "spoolsv.exe", "system",
    "registry", "memory compression", "taskmgr.exe", "searchapp.exe",
    "startmenuexperiencehost.exe", "ctfmon.exe", "conhost.exe", "runtimebroker.exe",
    "backgroundtaskhost.exe", "sihost.exe", "fontdrvhost.exe", "dllhost.exe",
    "wudfhost.exe", "audiodg.exe", "sedsvc.exe", "securityhealthservice.exe",
    "msiexec.exe", "consent.exe", "splwow64.exe",
}

# Friendly name cleanup: strip common installer/updater suffixes
_NAME_CLEANUP_RE = re.compile(
    r"\s*[\(\[].*?[\)\]]"         # strip bracketed text like (Beta), [64-bit]
    r"|\s+[-–]\s+\w+$"            # strip trailing "- Company" style suffixes
    r"|\s+\d+(\.\d+)+$",          # strip trailing version numbers
    re.IGNORECASE,
)


def _clean_name(raw: str) -> str:
    """Strip noise from a display name and return a canonical lowercase key."""
    cleaned = _NAME_CLEANUP_RE.sub("", raw).strip()
    return cleaned.lower()


def _resolve_lnk(lnk_path: Path) -> Optional[str]:
    """Resolve a Windows .lnk shortcut to its target executable path."""
    try:
        import win32com.client  # type: ignore
        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortcut(str(lnk_path))
        target = shortcut.TargetPath
        if target and Path(target).suffix.lower() == ".exe" and Path(target).exists():
            return target
    except Exception:
        pass
    return None


# ─── Scanner ─────────────────────────────────────────────────────────────────

class AppScanner:
    """Discovers installed Windows apps and stores results in a JSON cache."""

    def __init__(self):
        self.apps: dict[str, AppEntry] = {}   # key → AppEntry

    # ── Public API ────────────────────────────────────────────────────────────

    async def scan_and_cache(self) -> None:
        """Run full discovery in a thread pool (non-blocking) then persist."""
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._scan_all)
        self.save_cache()
        logger.info(f"🔍 App discovery complete: {len(self.apps)} apps found and cached.")

    def load_cache(self) -> bool:
        """Load previously saved cache. Returns True if cache was loaded."""
        if not CACHE_PATH.exists():
            return False
        try:
            raw = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
            self.apps = {k: AppEntry(**v) for k, v in raw.items()}
            logger.info(f"📋 Loaded {len(self.apps)} apps from cache ({CACHE_PATH.name})")
            return True
        except Exception as e:
            logger.warning(f"Failed to load app cache: {e}")
            return False

    def save_cache(self) -> None:
        """Persist the current app registry to disk."""
        try:
            CACHE_PATH.write_text(
                json.dumps({k: asdict(v) for k, v in self.apps.items()}, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            logger.warning(f"Failed to save app cache: {e}")

    def find(self, query: str, threshold: int = 70) -> Optional[AppEntry]:
        """
        Fuzzy-find an app by name. Returns the best match above threshold,
        or None if no match is found.
        """
        if not self.apps:
            return None

        q = query.lower().strip()

        # 1. Exact key match
        if q in self.apps:
            return self.apps[q]

        # 2. Substring containment check (fast path)
        for key, entry in self.apps.items():
            if q in key or key in q:
                return entry

        # 3. RapidFuzz token_sort_ratio fuzzy match
        keys = list(self.apps.keys())
        result = fuzz_process.extractOne(q, keys, scorer=fuzz.token_sort_ratio)
        if result and result[1] >= threshold:
            return self.apps[result[0]]

        return None

    def all_apps(self) -> list[dict]:
        """Return all discovered apps as a serialisable list."""
        return [asdict(e) for e in self.apps.values()]

    # ── Private Scan Methods ──────────────────────────────────────────────────

    def _scan_all(self) -> None:
        """Run all scanners synchronously (called in thread pool)."""
        self._scan_start_menu()
        self._scan_desktop()
        self._scan_registry()
        self._scan_program_files()
        self._scan_running_processes()

    def _add(self, display_name: str, exe_path: str, source: str) -> None:
        """Add an entry if the path is a valid .exe and not blacklisted."""
        p = Path(exe_path)
        exe_name = p.name
        if exe_name.lower() in _SYSTEM_EXE_BLACKLIST:
            return
        if p.suffix.lower() != ".exe":
            return

        key = _clean_name(display_name)
        if not key:
            key = _clean_name(exe_name.replace(".exe", ""))

        if key and key not in self.apps:
            self.apps[key] = AppEntry(
                name=display_name,
                exe_name=exe_name,
                path=str(p),
                source=source,
            )

    def _scan_lnk_folder(self, folder: Path, source: str) -> None:
        """Recursively scan a folder for .lnk shortcuts."""
        if not folder.exists():
            return
        for lnk in folder.rglob("*.lnk"):
            try:
                target = _resolve_lnk(lnk)
                if target:
                    display_name = lnk.stem  # filename without extension
                    self._add(display_name, target, source)
            except Exception:
                pass

    def _scan_start_menu(self) -> None:
        appdata = os.environ.get("APPDATA", "")
        programdata = os.environ.get("PROGRAMDATA", "C:\\ProgramData")
        user_sm = Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
        sys_sm = Path(programdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
        self._scan_lnk_folder(user_sm, "start_menu")
        self._scan_lnk_folder(sys_sm, "start_menu")
        logger.debug(f"Start menu scan done. Total so far: {len(self.apps)}")

    def _scan_desktop(self) -> None:
        userprofile = os.environ.get("USERPROFILE", "")
        user_desktop = Path(userprofile) / "Desktop"
        public_desktop = Path("C:/Users/Public/Desktop")
        self._scan_lnk_folder(user_desktop, "desktop")
        self._scan_lnk_folder(public_desktop, "desktop")
        logger.debug(f"Desktop scan done. Total so far: {len(self.apps)}")

    def _scan_registry(self) -> None:
        reg_paths = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_CURRENT_USER,  r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        ]
        for hive, subkey in reg_paths:
            try:
                with winreg.OpenKey(hive, subkey) as key:
                    i = 0
                    while True:
                        try:
                            sub_name = winreg.EnumKey(key, i)
                            i += 1
                            try:
                                with winreg.OpenKey(key, sub_name) as sub:
                                    try:
                                        display_name = winreg.QueryValueEx(sub, "DisplayName")[0]
                                        install_loc  = winreg.QueryValueEx(sub, "InstallLocation")[0]
                                        # Try to find the main exe inside the install location
                                        if install_loc and Path(install_loc).is_dir():
                                            exes = list(Path(install_loc).glob("*.exe"))
                                            if exes:
                                                # Pick the exe whose name is closest to the display name
                                                best = min(exes, key=lambda e: len(e.name))
                                                self._add(display_name, str(best), "registry")
                                    except FileNotFoundError:
                                        pass
                            except Exception:
                                pass
                        except OSError:
                            break
            except Exception as e:
                logger.debug(f"Registry scan error ({subkey}): {e}")
        logger.debug(f"Registry scan done. Total so far: {len(self.apps)}")

    def _scan_program_files(self) -> None:
        dirs = [
            Path("C:/Program Files"),
            Path("C:/Program Files (x86)"),
        ]
        for base in dirs:
            if not base.exists():
                continue
            for app_dir in base.iterdir():
                if not app_dir.is_dir():
                    continue
                # Only look one level deep for the main exe
                exes = [f for f in app_dir.glob("*.exe") if f.name.lower() not in _SYSTEM_EXE_BLACKLIST]
                if exes:
                    # Use the folder name as the display name
                    display = app_dir.name
                    # Prefer exe whose name is closest to the folder name
                    best = min(
                        exes,
                        key=lambda e: -fuzz.token_sort_ratio(e.stem.lower(), display.lower()),
                    )
                    self._add(display, str(best), "program_files")
        logger.debug(f"Program Files scan done. Total so far: {len(self.apps)}")

    def _scan_running_processes(self) -> None:
        for proc in psutil.process_iter(["name", "exe"]):
            try:
                exe_path = proc.info.get("exe")
                name = proc.info.get("name", "")
                if exe_path and name and name.lower() not in _SYSTEM_EXE_BLACKLIST:
                    if Path(exe_path).exists():
                        display = Path(exe_path).stem  # raw exe name as display
                        self._add(display, exe_path, "process")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        logger.debug(f"Process scan done. Total so far: {len(self.apps)}")


# ─── Module-level singleton (shared across the app) ───────────────────────────

_scanner: Optional[AppScanner] = None


def get_scanner() -> AppScanner:
    """Return the module-level AppScanner singleton."""
    global _scanner
    if _scanner is None:
        _scanner = AppScanner()
    return _scanner
