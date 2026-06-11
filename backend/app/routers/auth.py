"""
ACE Voice Controller — API Routers
auth.py — Registration, login, token management via Supabase Auth.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from loguru import logger

from app.database import get_db
from app.models import User, UserSettings
from app.schemas import RegisterRequest, LoginRequest, TokenResponse
from app.core.security import hash_password, verify_password, create_access_token
from app.core.supabase_client import supabase
from pydantic import BaseModel
from app.config import settings

router = APIRouter()


async def _get_or_create_settings(db: AsyncSession, user_id: str) -> None:
    result = await db.execute(select(UserSettings).where(UserSettings.user_id == user_id))
    if not result.scalar_one_or_none():
        db.add(UserSettings(user_id=user_id))
        await db.flush()

class SyncRequest(BaseModel):
    access_token: str


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")

    user = User(
        email=body.email,
        hashed_password=hash_password(body.password),
        display_name=body.display_name or body.email.split("@")[0],
    )
    db.add(user)
    await db.flush()
    await _get_or_create_settings(db, user.id)

    token = create_access_token({"sub": user.id, "email": user.email})
    logger.info(f"New user registered: {user.email}")
    return TokenResponse(access_token=token, user_id=user.id, email=user.email)


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled")

    token = create_access_token({"sub": user.id, "email": user.email})
    logger.info(f"User logged in: {user.email}")
    return TokenResponse(access_token=token, user_id=user.id, email=user.email)


@router.get("/me")
async def get_me(db: AsyncSession = Depends(get_db)):
    # Simplified — in production, decode JWT from Authorization header
    return {"message": "Attach JWT middleware for /me endpoint"}

@router.post("/sync", response_model=TokenResponse)
async def sync_supabase_user(body: SyncRequest, db: AsyncSession = Depends(get_db)):
    """Validates a Supabase JWT and ensures the user exists in the local database."""
    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase client not configured")

    try:
        response = supabase.auth.get_user(body.access_token)
        sb_user = response.user
        if not sb_user:
            raise ValueError("Invalid session")
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid Supabase token: {e}")

    # Check if user already exists
    result = await db.execute(select(User).where(User.supabase_uid == sb_user.id))
    user = result.scalar_one_or_none()

    if not user:
        # Fallback to email check in case they were registered locally first
        result = await db.execute(select(User).where(User.email == sb_user.email))
        user = result.scalar_one_or_none()
        
        if user:
            # Link local user to Supabase
            user.supabase_uid = sb_user.id
            await db.flush()
        else:
            # Create new user
            display_name = sb_user.user_metadata.get("display_name") or sb_user.email.split("@")[0]
            user = User(
                email=sb_user.email,
                hashed_password="", # Managed by Supabase
                display_name=display_name,
                supabase_uid=sb_user.id
            )
            db.add(user)
            await db.flush()
            
    await _get_or_create_settings(db, user.id)
    await db.commit()

    # Issue a local JWT token for subsequent API calls
    token = create_access_token({"sub": user.id, "email": user.email})
    return TokenResponse(access_token=token, user_id=user.id, email=user.email)
