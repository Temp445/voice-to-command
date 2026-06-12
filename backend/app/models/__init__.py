"""
ACE Voice Controller — All SQLAlchemy Models
"""

from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import String, Text, Boolean, DateTime, ForeignKey, JSON, Enum as SAEnum, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_uuid() -> str:
    return str(uuid4())


# ─── Enums ──────────────────────────────────────────────────────────────────

class TTSProvider(str, enum.Enum):
    piper = "piper"
    gtts = "gtts"


class CommandStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    success = "success"
    failed = "failed"


class LogLevel(str, enum.Enum):
    info = "info"
    warning = "warning"
    error = "error"
    debug = "debug"


# ─── User ────────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=new_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    supabase_uid: Mapped[str | None] = mapped_column(Uuid(as_uuid=False), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    settings: Mapped["UserSettings"] = relationship("UserSettings", back_populates="user", uselist=False)
    commands: Mapped[list["CommandHistory"]] = relationship("CommandHistory", back_populates="user")
    workflows: Mapped[list["Workflow"]] = relationship("Workflow", back_populates="user")


# ─── UserSettings ────────────────────────────────────────────────────────────

class UserSettings(Base):
    __tablename__ = "settings"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), unique=True, nullable=False)

    # Voice
    wake_word: Mapped[str] = mapped_column(String(100), default="alexa")
    stt_provider: Mapped[str] = mapped_column(String(20), default="whisper")
    stt_noise_cancellation: Mapped[bool] = mapped_column(Boolean, default=True)
    whisper_model: Mapped[str] = mapped_column(String(20), default="base")
    active_mode_timeout: Mapped[int] = mapped_column(default=120)
    require_wake_word_always: Mapped[bool] = mapped_column(Boolean, default=True)

    # TTS
    tts_provider: Mapped[str] = mapped_column(String(20), default="piper")
    piper_voice: Mapped[str] = mapped_column(String(100), default="en_US-lessac-medium")

    # UI
    theme: Mapped[str] = mapped_column(String(20), default="dark")
    sidebar_collapsed: Mapped[bool] = mapped_column(Boolean, default=False)

    # Automation
    browser_type: Mapped[str] = mapped_column(String(20), default="chromium")
    startup_on_boot: Mapped[bool] = mapped_column(Boolean, default=True)
    minimize_to_tray: Mapped[bool] = mapped_column(Boolean, default=True)
    browser_animations_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    enable_desktop_overlay: Mapped[bool] = mapped_column(Boolean, default=True)
    overlay_shortcut: Mapped[str] = mapped_column(String(50), default="Alt+A")
    listen_shortcut: Mapped[str] = mapped_column(String(50), default="Alt+S")

    # CRM Integration
    crm_url: Mapped[str] = mapped_column(String(500), default="https://crm.acesoftcloud.in/")
    crm_keywords: Mapped[str] = mapped_column(String(500), default="open my crm, open crm, open ace crm")

    # LLM / AI Assistant
    llm_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    llm_provider: Mapped[str] = mapped_column(String(30), default="groq")
    llm_model: Mapped[str] = mapped_column(String(100), default="llama-3.3-70b-versatile")
    llm_api_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    llm_temperature: Mapped[float] = mapped_column(default=0.7)
    llm_mode: Mapped[str] = mapped_column(String(20), default="fallback")  # fallback | always_on

    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    user: Mapped["User"] = relationship("User", back_populates="settings")


# ─── CommandHistory ──────────────────────────────────────────────────────────

class CommandHistory(Base):
    __tablename__ = "command_history"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    intent: Mapped[str | None] = mapped_column(String(100), nullable=True)
    parameters: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default=CommandStatus.pending)
    result: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(20), default="voice")  # voice | text
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    duration_ms: Mapped[int | None] = mapped_column(nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="commands")


# ─── Workflow ────────────────────────────────────────────────────────────────

class Workflow(Base):
    __tablename__ = "workflows"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    trigger_phrase: Mapped[str | None] = mapped_column(String(200), nullable=True)
    steps: Mapped[list] = mapped_column(JSON, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    run_count: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    user: Mapped["User"] = relationship("User", back_populates="workflows")


# ─── AutomationLog ───────────────────────────────────────────────────────────

class AutomationLog(Base):
    __tablename__ = "automation_logs"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=new_uuid)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(200), nullable=False)
    target: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default=CommandStatus.success)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    level: Mapped[str] = mapped_column(String(20), default=LogLevel.info)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# ─── Shortcut ────────────────────────────────────────────────────────────────

class Shortcut(Base):
    __tablename__ = "shortcuts"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    trigger_phrase: Mapped[str] = mapped_column(String(200), nullable=False)
    action_type: Mapped[str] = mapped_column(String(50), nullable=False)
    action_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# ─── VoiceProfile ────────────────────────────────────────────────────────────

class VoiceProfile(Base):
    __tablename__ = "voice_profiles"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    tts_provider: Mapped[str] = mapped_column(String(20), default="piper")
    voice_id: Mapped[str] = mapped_column(String(200), nullable=False)
    speed: Mapped[float] = mapped_column(default=1.0)
    pitch: Mapped[float] = mapped_column(default=1.0)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
