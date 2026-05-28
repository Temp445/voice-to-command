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
from app.config import settings

router = APIRouter()


async def _get_or_create_settings(db: AsyncSession, user_id: str) -> None:
    result = await db.execute(select(UserSettings).where(UserSettings.user_id == user_id))
    if not result.scalar_one_or_none():
        db.add(UserSettings(user_id=user_id))
        await db.flush()


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
