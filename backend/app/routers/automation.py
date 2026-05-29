"""Automation router — Logs and direct action triggers."""

from fastapi import APIRouter, Depends, Request
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


@router.get("/apps", summary="List all dynamically discovered apps")
async def list_apps(request: Request, q: str = ""):
    """
    Returns all applications discovered by the AppScanner.
    Pass ?q=<query> to fuzzy-search the list.
    """
    from automation.desktop.app_scanner import get_scanner
    scanner = get_scanner()
    if q:
        entry = scanner.find(q)
        if entry:
            from dataclasses import asdict
            return {"found": True, "app": asdict(entry)}
        return {"found": False, "app": None}
    return {
        "total": len(scanner.apps),
        "apps": scanner.all_apps(),
    }


@router.post("/apps/rescan", summary="Trigger a fresh app discovery scan")
async def rescan_apps(request: Request):
    """Forces the AppScanner to re-scan all sources and update the cache."""
    import asyncio
    from automation.desktop.app_scanner import get_scanner
    scanner = get_scanner()
    await scanner.scan_and_cache()
    return {
        "status": "ok",
        "total": len(scanner.apps),
        "message": f"Rescan complete. {len(scanner.apps)} apps discovered.",
    }

