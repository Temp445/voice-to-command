"""Automation router — Logs and direct action triggers."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.database import get_db
from app.models import AutomationLog
from app.schemas import AutomationLogResponse

router = APIRouter()


@router.get("/logs", response_model=list[AutomationLogResponse])
async def get_logs(limit: int = 100, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(AutomationLog).order_by(desc(AutomationLog.created_at)).limit(limit)
    )
    return result.scalars().all()
