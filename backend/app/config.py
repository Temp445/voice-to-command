"""
ACE Voice Controller — Backend Configuration
Loads settings from environment variables via pydantic-settings.
"""

from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

# Resolve .env path — works whether you run from project root or backend/
_ROOT = Path(__file__).resolve().parent.parent.parent  # Voice_Controller_v1/
_ENV_FILE = _ROOT / ".env" if (_ROOT / ".env").exists() else Path(".env")


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

    # --- Security ---
    secret_key: str = Field(default="ace-voice-controller-default-dev-secret-key-32x")
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7  # 7 days

    # --- Supabase ---
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""

    # --- Database (local SQLite fallback) ---
    database_url: str = "sqlite+aiosqlite:///./ace_local.db"

    # --- Voice ---
    wake_word: str = "alexa"  # Must match OWW model: hey_jarvis, alexa, hey_mycroft, hey_rhasspy
    whisper_model: str = "base"  # tiny | base | small | medium

    # --- TTS ---
    tts_provider: str = "piper"  # piper | gtts
    gtts_api_key: str = ""
    piper_voice: str = "en_US-lessac-medium"
    piper_models_dir: str = "voice/tts/models"

    # --- Automation ---
    browser_type: str = "chromium"  # chromium | firefox | webkit
    browser_animations_enabled: bool = True
    enable_desktop_overlay: bool = True

    # --- Logging ---
    log_level: str = "INFO"
    log_file: str = "logs/ace.log"

    # --- CRM Integration ---
    crm_url: str = "https://crm.acesoftcloud.in/"
    crm_keywords: str = "open my crm, open crm, open ace crm"

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


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()


settings = get_settings()
