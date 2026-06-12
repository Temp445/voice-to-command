"""Automation router — Logs and direct action triggers."""

from datetime import datetime, timezone
from fastapi import APIRouter, Request
from fastapi.responses import FileResponse

from app.schemas import AutomationLogResponse
from app.core.supabase_client import supabase_admin, sb_run

router = APIRouter()


@router.get("/logs", response_model=list[AutomationLogResponse])
async def get_logs(limit: int = 100):
    res = await sb_run(
        lambda: supabase_admin
        .table("automation_logs")
        .select("*")
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    rows = res.data or []
    return [
        AutomationLogResponse(
            id=r["id"],
            action=r["action"],
            target=r.get("target"),
            status=r.get("status", "success"),
            details=r.get("details"),
            level=r.get("level", "info"),
            created_at=datetime.fromisoformat(r["created_at"]) if isinstance(r["created_at"], str) else r["created_at"],
        )
        for r in rows
    ]


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


@router.post("/browser/screenshot", summary="Take a screenshot of the Browser")
async def take_browser_screenshot():
    """Takes a screenshot of the active browser page and returns the image."""
    from automation.browser.browser_engine import BrowserEngine
    import os
    engine = BrowserEngine()
    try:
        path = await engine.screenshot("latest.png")
        if os.path.exists(path):
            return FileResponse(path, media_type="image/png")
        return {"status": "error", "message": "Screenshot failed"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.post("/browser/test", summary="Run a browser test suite")
async def run_browser_tests():
    """Runs the built-in browser test suite."""
    from automation.browser.browser_testing import BrowserTestRunner
    runner = BrowserTestRunner()
    
    # Example test suite
    test = {
        "name": "Google Search Test",
        "steps": [
            {"action": "search_google", "params": {"query": "playwright automation"}},
            {"action": "wait_for_selector", "params": {"selector": "textarea[name='q'], input[name='q']"}},
            {"action": "assert_text_exists", "params": {"text": "playwright"}}
        ]
    }
    
    result = await runner.run_test(test)
    return result
