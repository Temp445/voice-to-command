"""
ACE Voice Controller — Backend Configuration
Loads settings from environment variables via pydantic-settings.
"""

from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, model_validator

import sys
import os

if getattr(sys, 'frozen', False):
    # Running in PyInstaller bundle. Base paths off the executable location.
    _ROOT = Path(sys.executable).parent
    # Data files are placed in _internal starting in Pyinstaller 6.0 for onedir mode
    _DATA_ROOT = Path(sys._MEIPASS)
else:
    # Resolve .env path — works whether you run from project root or backend/
    _ROOT = Path(__file__).resolve().parent.parent.parent  # Voice_Controller_v1/
    _DATA_ROOT = _ROOT


# Robustly find .env file
_env_paths = [
    _ROOT / ".env",               # Prod (next to exe) or Dev (project root)
    _DATA_ROOT / ".env",          # Bundled .env in _MEIPASS
    Path(".env"),                 # Current working directory
    Path(__file__).resolve().parent.parent.parent / ".env", # Hard fallback to project root
    Path("..") / ".env",          # CWD is backend/
    Path("../../..") / ".env",    # CWD is backend/dist/ace-backend/
]

_ENV_FILE = next((p for p in _env_paths if p.exists()), Path(".env"))

# --- AppData Directory for Production Files ---
if sys.platform == "win32":
    appdata_base = os.getenv("LOCALAPPDATA") or os.getenv("APPDATA") or str(Path.home())
    _APPDATA_DIR = Path(appdata_base) / "ACEVoiceController"
else:
    _APPDATA_DIR = Path.home() / ".config" / "ACEVoiceController"

_APPDATA_DIR.mkdir(parents=True, exist_ok=True)
(_APPDATA_DIR / "logs").mkdir(parents=True, exist_ok=True)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- App ---
    app_name: str = "ACE Voice Controller"
    app_version: str = "1.0.0"
    debug: bool = False
    backend_host: str = "127.0.0.1"
    backend_port: int = 8000
    owner_user_id: str | None = None

    # --- Security ---
    secret_key: str = Field(default="ace-voice-controller-default-dev-secret-key-32x")
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7  # 7 days

    # --- Supabase ---
    supabase_url: str = ""
    supabase_publishable_key: str = ""
    supabase_service_key: str = ""

    # --- Voice ---
    wake_word: str = "alexa"  # Must match OWW model: hey_jarvis, alexa, hey_mycroft, hey_rhasspy
    stt_provider: str = "whisper" # whisper | google | elevenlabs
    whisper_model: str = "small"  # tiny | base | small | medium
    active_mode_timeout: int = 120  # Seconds to stay awake after wake word
    require_wake_word_always: bool = True
    elevenlabs_api_key: str = ""
    deepgram_api_key: str = ""


    # --- TTS ---
    tts_provider: str = "piper"  # piper | gtts
    piper_voice: str = "en_US-lessac-medium"
    piper_models_dir: str = "voice/tts/models"

    # --- Automation ---
    browser_type: str = "chromium"  # chromium | firefox | webkit
    browser_animations_enabled: bool = True
    enable_desktop_overlay: bool = True

    # --- Logging ---
    log_level: str = "INFO"
    log_file: str = str(_APPDATA_DIR / "logs" / "ace.log")

    # --- CRM Integration ---
    crm_url: str = ""
    crm_keywords: str = ""
    crm_sites: str = "[]"  # JSON array, empty by default — users add their own

    # --- LLM Providers ---
    # Set whichever provider you want to use. Only one is active at a time.
    llm_provider: str = ""              # groq | openai | gemini | claude | deepseek
    llm_model: str = ""                 # e.g. llama-3.3-70b-versatile, gpt-4o-mini
    llm_mode: str = "fallback"          # fallback | always_on
    llm_temperature: float = 0.7
    groq_api_key: str = ""
    openai_api_key: str = ""
    google_api_key: str = ""
    anthropic_api_key: str = ""
    deepseek_api_key: str = ""

    @model_validator(mode="after")
    def validate_security(self) -> "Settings":
        if not self.debug and self.secret_key == "ace-voice-controller-default-dev-secret-key-32x":
            raise ValueError("FATAL: Default secret_key detected in production. You MUST change SECRET_KEY in your .env file.")
        return self


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()


settings = get_settings()
