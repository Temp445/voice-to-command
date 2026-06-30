"""
ACE Voice Controller — Custom Exception Hierarchy
"""

from fastapi import HTTPException, status


class ACEBaseException(Exception):
    """Base exception for all ACE errors."""
    def __init__(self, message: str, code: str = "ACE_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)


# --- Voice Exceptions ---
class WakeWordError(ACEBaseException):
    """Wake word detector failed."""
    def __init__(self, message: str = "Wake word detection error"):
        super().__init__(message, "WAKE_WORD_ERROR")


class TranscriptionError(ACEBaseException):
    """STT transcription failed."""
    def __init__(self, message: str = "Transcription error"):
        super().__init__(message, "TRANSCRIPTION_ERROR")

class TTSError(ACEBaseException):
    """Text-to-speech synthesis failed."""
    def __init__(self, message: str = "TTS synthesis error"):
        super().__init__(message, "TTS_ERROR")


class TTSProviderNotConfigured(TTSError):
    """TTS provider missing required config (e.g., API key)."""
    def __init__(self, provider: str):
        super().__init__(f"TTS provider '{provider}' is not configured — check API key.")


# --- Command Exceptions ---
class CommandNotFound(ACEBaseException):
    """No matching command intent found."""
    def __init__(self, text: str):
        super().__init__(f"No command matched: '{text}'", "COMMAND_NOT_FOUND")


class CommandExecutionError(ACEBaseException):
    """Command executed but failed."""
    def __init__(self, command: str, reason: str):
        super().__init__(f"Command '{command}' failed: {reason}", "COMMAND_EXEC_ERROR")


# --- Automation Exceptions ---
class AutomationError(ACEBaseException):
    """Desktop automation failure."""
    def __init__(self, message: str = "Automation error"):
        super().__init__(message, "AUTOMATION_ERROR")


class AppNotFound(AutomationError):
    """Target application not found on system."""
    def __init__(self, app_name: str):
        super().__init__(f"Application '{app_name}' not found on this system.")



class BrowserAutomationError(AutomationError):
    """Playwright browser automation failed."""
    def __init__(self, message: str):
        super().__init__(message)


# --- Auth Exceptions ---
class AuthError(HTTPException):
    def __init__(self, detail: str = "Authentication failed"):
        super().__init__(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


class PermissionDenied(HTTPException):
    def __init__(self, detail: str = "Permission denied"):
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)
