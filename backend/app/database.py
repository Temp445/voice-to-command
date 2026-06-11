"""
ACE Voice Controller — Database Engine
Async SQLAlchemy + SQLite (local) with Supabase sync.
"""

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.config import settings


engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    future=True,
    connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {},
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""
    pass


async def get_db() -> AsyncSession:
    """FastAPI dependency: yield an async DB session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Create all tables on startup (local SQLite)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
        # Migration: add active_mode_timeout if it doesn't exist
        try:
            from sqlalchemy import text
            await conn.execute(text("ALTER TABLE settings ADD COLUMN active_mode_timeout INTEGER DEFAULT 120"))
        except Exception:
            pass  # Column likely already exists
            
        # Migration: add require_wake_word_always if it doesn't exist
        try:
            await conn.execute(text("ALTER TABLE settings ADD COLUMN require_wake_word_always BOOLEAN DEFAULT 1"))
        except Exception:
            pass

        # Migration: add shortcuts
        try:
            await conn.execute(text("ALTER TABLE settings ADD COLUMN overlay_shortcut VARCHAR(50) DEFAULT 'Alt+A'"))
        except Exception:
            pass

        try:
            await conn.execute(text("ALTER TABLE settings ADD COLUMN listen_shortcut VARCHAR(50) DEFAULT 'Alt+S'"))
        except Exception:
            pass
