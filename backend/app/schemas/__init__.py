"""
ACE Voice Controller — Pydantic Schemas (Request / Response models)
"""

from datetime import datetime
from typing import Any
from pydantic import BaseModel, EmailStr, Field


# ─── Auth ────────────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    display_name: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    email: str


# ─── Settings ────────────────────────────────────────────────────────────────

class SettingsUpdate(BaseModel):
    wake_word: str | None = None
    whisper_model: str | None = None
    stt_provider: str | None = None
    stt_noise_cancellation: bool | None = None
    active_mode_timeout: int | None = None
    tts_provider: str | None = None
    gtts_api_key: str | None = None       # raw; encrypted before storage
    piper_voice: str | None = None
    theme: str | None = None
    browser_type: str | None = None
    startup_on_boot: bool | None = None
    minimize_to_tray: bool | None = None
    browser_animations_enabled: bool | None = None
    enable_desktop_overlay: bool | None = None
    crm_url: str | None = None
    crm_keywords: str | None = None
    # LLM
    llm_enabled: bool | None = None
    llm_provider: str | None = None
    llm_model: str | None = None
    llm_api_key: str | None = None        # raw; encrypted before storage
    llm_temperature: float | None = None
    llm_mode: str | None = None           # "fallback" | "always_on"


class SettingsResponse(BaseModel):
    wake_word: str
    whisper_model: str
    stt_provider: str
    stt_noise_cancellation: bool
    active_mode_timeout: int
    tts_provider: str
    piper_voice: str
    theme: str
    browser_type: str
    startup_on_boot: bool
    minimize_to_tray: bool
    browser_animations_enabled: bool
    enable_desktop_overlay: bool
    gtts_configured: bool   # True if API key is set
    crm_url: str
    crm_keywords: str
    # LLM
    llm_enabled: bool
    llm_provider: str
    llm_model: str
    llm_configured: bool    # True if API key is set
    llm_temperature: float
    llm_mode: str


# ─── Commands ────────────────────────────────────────────────────────────────

class ExecuteCommandRequest(BaseModel):
    id: str | None = None
    text: str = Field(min_length=1)
    source: str = "text"   # text | voice


class CommandResultResponse(BaseModel):
    id: str
    raw_text: str
    intent: str | None
    parameters: dict[str, Any] | None
    status: str
    result: str | None
    duration_ms: int | None
    executed_at: datetime

    class Config:
        from_attributes = True


# ─── Workflows ───────────────────────────────────────────────────────────────

class WorkflowStep(BaseModel):
    action: str
    parameters: dict[str, Any] = {}
    delay_ms: int = 0


class WorkflowCreate(BaseModel):
    name: str = Field(min_length=1)
    description: str | None = None
    trigger_phrase: str | None = None
    steps: list[WorkflowStep] = []


class WorkflowResponse(BaseModel):
    id: str
    name: str
    description: str | None
    trigger_phrase: str | None
    steps: list[dict]
    is_active: bool
    run_count: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ─── Voice ───────────────────────────────────────────────────────────────────

class TranscriptEvent(BaseModel):
    text: str
    is_final: bool = False
    confidence: float | None = None


class TTSRequest(BaseModel):
    text: str
    provider: str | None = None   # override active provider
    piper_voice: str | None = None


class VoiceStatusResponse(BaseModel):
    wake_word_active: bool
    listening: bool
    tts_provider: str
    whisper_model: str
    pipeline_state: str   # idle | listening | processing | speaking


# ─── Automation Log ──────────────────────────────────────────────────────────

class AutomationLogResponse(BaseModel):
    id: str
    action: str
    target: str | None
    status: str
    details: str | None
    level: str
    created_at: datetime

    class Config:
        from_attributes = True


# ─── LLM / AI Chat ───────────────────────────────────────────────────────────

class LLMChatRequest(BaseModel):
    message: str = Field(min_length=1)
    stream: bool = False


class LLMChatResponse(BaseModel):
    reply: str
    provider: str
    model: str


class LLMStatusResponse(BaseModel):
    enabled: bool
    provider: str
    model: str
    mode: str
    ready: bool
    history_length: int


class LLMProviderInfo(BaseModel):
    id: str
    name: str
    models: list[str]
