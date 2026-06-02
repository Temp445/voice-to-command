"""
ACE Voice Controller - Context State Service
Maintains active conversational and system context across multiple commands.
"""

from typing import Any, Dict, Optional
import threading

class ContextStateService:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(ContextStateService, cls).__new__(cls)
                cls._instance._state = {
                    "last_created_file": None,
                    "active_project_path": None,
                    "last_active_window": None,
                }
        return cls._instance

    def set(self, key: str, value: Any) -> None:
        """Set a context variable."""
        self._state[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        """Get a context variable."""
        return self._state.get(key, default)

    def get_all(self) -> Dict[str, Any]:
        """Get the full context state dictionary."""
        return self._state.copy()

    def clear(self) -> None:
        """Clear the context state."""
        self._state = {
            "last_created_file": None,
            "active_project_path": None,
            "last_active_window": None,
        }

    def get_project_path(self, name: str) -> Optional[str]:
        """Looks up a project path from projects.json based on fuzzy name."""
        import json
        from pathlib import Path
        try:
            projects_file = Path(__file__).resolve().parent.parent.parent.parent / "projects.json"
            if not projects_file.exists():
                return None
            with open(projects_file, "r") as f:
                projects = json.load(f)
            
            name = name.lower().strip()
            # Exact match
            if name in projects:
                return projects[name]
                
            # Partial match
            for k, v in projects.items():
                if name in k or k in name:
                    return v
            return None
        except Exception:
            return None

def get_context() -> ContextStateService:
    return ContextStateService()
