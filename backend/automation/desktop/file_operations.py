"""File operations, clipboard, power management."""

import os
import subprocess
import datetime
from pathlib import Path


class FileOperations:
    def open_folder(self, path: str) -> str:
        """Open a folder in Windows Explorer."""
        # Expand common shortcuts
        aliases = {
            "downloads": Path.home() / "Downloads",
            "documents": Path.home() / "Documents",
            "desktop": Path.home() / "Desktop",
            "pictures": Path.home() / "Pictures",
            "music": Path.home() / "Music",
            "videos": Path.home() / "Videos",
        }
        resolved = aliases.get(path.lower(), Path(path))

        if not resolved.exists():
            return f"Folder not found: {resolved}"

        subprocess.Popen(["explorer", str(resolved)])
        return f"Opened folder: {resolved}"

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
