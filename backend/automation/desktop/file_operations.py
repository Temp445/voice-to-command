"""File operations, clipboard, power management."""

import os
import subprocess
import datetime
from pathlib import Path


class FileOperations:
    def open_folder(self, path: str) -> str:
        """Open a folder in Windows Explorer by path or fuzzy name."""
        import re
        # Strip common filler words spoken naturally ("the", "my", "a", "an")
        clean = re.sub(r"^\s*(the|my|a|an)\s+", "", path.strip(), flags=re.IGNORECASE).strip()
        key = clean.lower()

        # Well-known aliases — use Windows Shell URIs to guarantee correct resolution
        # even if the user moved their Downloads/Documents to another drive or OneDrive.
        aliases = {
            # Downloads
            "downloads":        "shell:Downloads",
            "download":         "shell:Downloads",
            "download folder":  "shell:Downloads",
            # Documents
            "documents":        "shell:Personal",
            "document":         "shell:Personal",
            "docs":             "shell:Personal",
            # Desktop
            "desktop":          "shell:Desktop",
            # Pictures
            "pictures":         "shell:My Pictures",
            "photos":           "shell:My Pictures",
            "photo":            "shell:My Pictures",
            # Music
            "music":            "shell:My Music",
            # Videos
            "videos":           "shell:My Video",
            "video":            "shell:My Video",
            # Home
            "home":             "shell:Profile",
        }
        if key in aliases:
            resolved_shell = aliases[key]
            subprocess.Popen(["explorer", resolved_shell])
            return f"Opened {key.title()} folder"

        # Absolute path
        candidate = Path(clean)
        if candidate.is_absolute() and candidate.exists():
            subprocess.Popen(["explorer", str(candidate)])
            return f"Opened folder: {candidate}"

        # Exact folder-name match first (case-insensitive) under home
        for folder in home.iterdir():
            if folder.is_dir() and folder.name.lower() == key:
                subprocess.Popen(["explorer", str(folder)])
                return f"Opened folder: {folder.name}"

        # Starts-with match under home (e.g. "down" → "Downloads")
        for folder in sorted(home.iterdir()):
            if folder.is_dir() and folder.name.lower().startswith(key):
                subprocess.Popen(["explorer", str(folder)])
                return f"Opened folder: {folder.name}"

        # Substring match under home then C:/ and D:/
        search_roots = [home, Path("C:/"), Path("D:/") if Path("D:/").exists() else None]
        for root in search_roots:
            if root is None:
                continue
            try:
                for folder in sorted(root.iterdir()):
                    if folder.is_dir() and key in folder.name.lower():
                        subprocess.Popen(["explorer", str(folder)])
                        return f"Opened folder: {folder.name}"
            except PermissionError:
                continue

        return f"Folder '{clean}' not found. Try specifying the full path."

    def create_folder(self, folder_name: str) -> str:
        """Create a folder. Defaults to Desktop if no absolute path is given."""
        folder_name = folder_name.strip("'\" ")
        
        # If it's just a folder name without path separators, put it on Desktop
        if "\\" not in folder_name and "/" not in folder_name:
            target_path = Path.home() / "Desktop" / folder_name
        else:
            target_path = Path(folder_name)
            
        if target_path.exists():
            return f"Folder already exists: {target_path}"
            
        try:
            target_path.mkdir(parents=True, exist_ok=True)
            return f"Created folder: {target_path}"
        except Exception as e:
            return f"Failed to create folder: {str(e)}"
