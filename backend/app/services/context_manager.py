"""
Context Manager for tracking entities across conversational turns.
"""

class ContextManager:
    def __init__(self):
        self.last_app: str = ""
        self.last_project_path: str = ""
        self.last_dev_server_url: str = ""
        
    def get_system_prompt_injection(self) -> str:
        """Returns a string describing the current physical state of the machine for the LLM."""
        lines = []
        if self.last_app:
            lines.append(f"- Active Application: {self.last_app}")
        if self.last_project_path:
            lines.append(f"- Active Project Path: {self.last_project_path}")
        if self.last_dev_server_url:
            lines.append(f"- Active Dev Server URL: {self.last_dev_server_url}")
            
        if not lines:
            return ""
            
        return "\nCURRENT MACHINE STATE:\n" + "\n".join(lines) + "\n"

# Singleton
context_manager = ContextManager()
