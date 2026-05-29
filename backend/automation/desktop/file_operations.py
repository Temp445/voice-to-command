"""File operations, clipboard, power management."""

import os
import subprocess
import datetime
from pathlib import Path


class FileOperations:
    def open_folder(self, path: str, disambiguation: str | None = None) -> str:
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

        # 3. Dynamic search via FileIndexer
        from automation.desktop.file_indexer import get_indexer
        from rapidfuzz import fuzz, process
        
        indexer = get_indexer()
        results = indexer.search(key, is_folder=True, limit=20)
        
        if not results:
            return f"Folder '{clean}' not found. Try specifying the full path."

        # If only 1 result, just open it
        if len(results) == 1:
            folder_path = results[0]["path"]
            subprocess.Popen(["explorer", folder_path])
            return f"Opened folder: {results[0]['name']}"
            
        # Exact name match
        exact_matches = [r for r in results if r["name"].lower() == key]
        if len(exact_matches) == 1:
            folder_path = exact_matches[0]["path"]
            subprocess.Popen(["explorer", folder_path])
            return f"Opened folder: {exact_matches[0]['name']}"
            
        if len(exact_matches) > 1:
            if disambiguation:
                # Check if user said a number (e.g. "press 1", "one", "1")
                import re
                # We can also map word numbers to integers if needed, but digits are safest
                num_match = re.search(r'\b(\d+)\b', disambiguation)
                if num_match:
                    idx = int(num_match.group(1)) - 1
                    if 0 <= idx < len(exact_matches):
                        matched_folder = exact_matches[idx]
                        subprocess.Popen(["explorer", matched_folder["path"]])
                        parent_name = Path(matched_folder["path"]).parent.name
                        return f"Opened folder: {matched_folder['name']} in {parent_name}"
                        
                # User provided disambiguation text, e.g., "Projects" or "Backups"
                choices = [Path(r["path"]).parent.name for r in exact_matches]
                best_match = process.extractOne(disambiguation, choices, scorer=fuzz.WRatio)
                if best_match and best_match[1] > 60:
                    matched_folder = exact_matches[choices.index(best_match[0])]
                    subprocess.Popen(["explorer", matched_folder["path"]])
                    return f"Opened folder: {matched_folder['name']} in {best_match[0]}"
            
            # Need disambiguation
            top_matches = exact_matches[:3] # Limit to top 3 so voice isn't too long
            opts = " or ".join(f"{i+1} for {Path(r['path']).parent.name} ({r['path']})" for i, r in enumerate(top_matches))
            return f"MULTIPLE_MATCHES: I found multiple {clean} folders. Say {opts}."
            
        # Fallback to fuzzy match
        choices = [r["name"] for r in results]
        best_match = process.extractOne(key, choices, scorer=fuzz.WRatio)
        
        if best_match and best_match[1] >= 80:
            matched_folder = next(r for r in results if r["name"] == best_match[0])
            subprocess.Popen(["explorer", matched_folder["path"]])
            return f"Opened folder: {matched_folder['name']}"
            
        return f"Folder '{clean}' not found."

    def search_file(self, file_name: str) -> str:
        """Search for a file using FileIndexer and open it."""
        from automation.desktop.file_indexer import get_indexer
        import os
        
        indexer = get_indexer()
        results = indexer.search(file_name, is_folder=False, limit=5)
        
        if not results:
            return f"Could not find any file named {file_name}"
            
        if len(results) == 1:
            file_path = results[0]["path"]
            try:
                os.startfile(file_path)
                return f"Opened {results[0]['name']}"
            except Exception as e:
                return f"Found {results[0]['name']} but failed to open it: {e}"
            
        # If multiple, open the first one (we could add disambiguation here later)
        file_path = results[0]["path"]
        try:
            os.startfile(file_path)
            return f"Found multiple files named {file_name}. Opened the most likely one."
        except Exception as e:
            return f"Found multiple files but failed to open: {e}"

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
