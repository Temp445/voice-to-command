"""File operations, clipboard, power management."""

import os
import subprocess
import datetime
from pathlib import Path


class FileOperations:
    def _launch_and_focus_folder(self, path: str, title: str) -> None:
        subprocess.Popen(["explorer", path])
        from automation.desktop.window_manager import WindowManager
        WindowManager().force_focus_by_title(title)

    def _launch_and_focus_file(self, path: str) -> None:
        os.startfile(path)
        from automation.desktop.window_manager import WindowManager
        WindowManager().force_focus_by_title(Path(path).name)

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
            self._launch_and_focus_folder(resolved_shell, key)
            return f"Opened {key.title()} folder"

        # Absolute path
        candidate = Path(clean)
        if candidate.is_absolute() and candidate.exists():
            self._launch_and_focus_folder(str(candidate), candidate.name)
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
            self._launch_and_focus_folder(folder_path, results[0]['name'])
            return f"Opened folder: {results[0]['name']}"
            
        # Exact name match
        exact_matches = [r for r in results if r["name"].lower() == key]
        if len(exact_matches) == 1:
            folder_path = exact_matches[0]["path"]
            self._launch_and_focus_folder(folder_path, exact_matches[0]['name'])
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
                        self._launch_and_focus_folder(matched_folder["path"], matched_folder["name"])
                        parent_name = Path(matched_folder["path"]).parent.name
                        return f"Opened folder: {matched_folder['name']} in {parent_name}"
                        
                # User provided disambiguation text, e.g., "Projects" or "Backups"
                choices = [Path(r["path"]).parent.name for r in exact_matches]
                best_match = process.extractOne(disambiguation, choices, scorer=fuzz.WRatio)
                if best_match and best_match[1] > 60:
                    matched_folder = exact_matches[choices.index(best_match[0])]
                    self._launch_and_focus_folder(matched_folder["path"], matched_folder["name"])
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
            self._launch_and_focus_folder(matched_folder["path"], matched_folder["name"])
            return f"Opened folder: {matched_folder['name']}"
            
        return f"Folder '{clean}' not found."

    def search_file(self, file_name: str) -> str:
        """Search for a file using FileIndexer and open it."""
        from automation.desktop.file_indexer import get_indexer
        import os
        from pathlib import Path
        
        indexer = get_indexer()
        results = indexer.search(file_name, is_folder=False, limit=5)
        
        if not results:
            # Fallback: Check immediate working directories and common locations
            try:
                base = Path(os.getcwd())
                fallback_dirs = [base, base.parent, base.parent.parent, Path.home() / "Downloads", Path.home() / "Documents", Path.home() / "Desktop"]
                for root_dir in set(fallback_dirs):
                    if not root_dir.exists(): continue
                    for f in os.listdir(str(root_dir)):
                        if file_name.lower() in f.lower() and os.path.isfile(os.path.join(str(root_dir), f)):
                            results.append({"name": f, "path": os.path.join(str(root_dir), f)})
            except Exception:
                pass

        if not results:
            return f"Could not find any file named {file_name}"
            
        # 1. Check for an exact name match (e.g., if user specifically asked for "demo45.txt")
        exact_matches = [r for r in results if r["name"].lower() == file_name.lower()]
        if exact_matches:
            results = exact_matches
            
        # 2. If we only have 1 result now, open it
        if len(results) == 1:
            file_path = results[0]["path"]
            try:
                self._launch_and_focus_file(file_path)
                return f"Opened {results[0]['name']}"
            except Exception as e:
                return f"Found {results[0]['name']} but failed to open it: {e}"
            
        # 3. If multiple results remain, prompt the user to disambiguate
        # Deduplicate paths in case fallback and indexer found the same file
        unique_results = {r["path"]: r for r in results}.values()
        top_matches = list(unique_results)[:4]
        
        if len(top_matches) == 1:
            file_path = top_matches[0]["path"]
            try:
                self._launch_and_focus_file(file_path)
                return f"Opened {top_matches[0]['name']}"
            except Exception as e:
                return f"Found {top_matches[0]['name']} but failed to open it: {e}"

        names = [r["name"] for r in top_matches]
        return f"MULTIPLE_MATCHES: I found multiple files matching '{file_name}': {', '.join(names)}. Which one do you want to open?"

    def create_folder(self, folder_name: str, drive: str | None = None) -> str:
        """Create a folder. Defaults to Desktop if no absolute path is given."""
        folder_name = folder_name.strip("'\" ")
        
        # If a drive is provided, create it there (e.g., E:\demo45)
        if drive:
            target_path = Path(f"{drive.upper()}:\\") / folder_name
        # If it's just a folder name without path separators, put it on Desktop
        elif "\\" not in folder_name and "/" not in folder_name:
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

    def get_recent_files(self, limit: int = 10) -> list[dict]:
        """Fetch the most recently accessed files from Windows Recent folder."""
        try:
            import win32com.client
            shell = win32com.client.Dispatch("WScript.Shell")
            recent_dir = Path(os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Recent"))
            
            if not recent_dir.exists():
                return []
                
            files = []
            seen_paths = set()
            for lnk in recent_dir.glob("*.lnk"):
                try:
                    shortcut = shell.CreateShortcut(str(lnk))
                    target = shortcut.TargetPath
                    if target and Path(target).exists() and Path(target).is_file():
                        if target not in seen_paths:
                            seen_paths.add(target)
                            files.append({
                                "name": Path(target).name,
                                "path": target,
                                "accessed": lnk.stat().st_mtime
                            })
                except Exception:
                    continue
                    
            # Sort by accessed time descending
            files.sort(key=lambda x: x["accessed"], reverse=True)
            return files[:limit]
        except ImportError:
            return []

    def open_latest_downloaded_file(self) -> str:
        """Finds and opens the most recently downloaded file in the user's Downloads folder."""
        try:
            import win32com.client
            shell = win32com.client.Dispatch("WScript.Shell")
            # Resolve the actual Downloads folder location (handles OneDrive/moved folders)
            downloads_path = Path(shell.SpecialFolders("MyDocuments")).parent / "Downloads"
            if not downloads_path.exists():
                downloads_path = Path.home() / "Downloads"
                
            files = [f for f in downloads_path.iterdir() if f.is_file() and not f.name.endswith(".crdownload") and not f.name.endswith(".part")]
            if not files:
                return "Your Downloads folder is empty."
                
            latest_file = max(files, key=lambda f: f.stat().st_mtime)
            self._launch_and_focus_file(str(latest_file))
            return f"Opened the latest download: {latest_file.name}"
        except Exception as e:
            return f"Failed to open the latest download: {str(e)}"
