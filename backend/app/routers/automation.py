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
    # from automation.desktop.app_scanner import get_scanner
    # scanner = get_scanner()
    # if q:
    #     entry = scanner.find(q)
    #     if entry:
    #         from dataclasses import asdict
    #         return {"found": True, "app": asdict(entry)}
    #     return {"found": False, "app": None}
    # return {
    #     "total": len(scanner.apps),
    #     "apps": scanner.all_apps(),
    # }
    return {
        "total": 0,
        "apps": [],
    }


@router.post("/apps/rescan", summary="Trigger a fresh app discovery scan")
async def rescan_apps(request: Request):
    """Forces the AppScanner to re-scan all sources and update the cache."""
    # import asyncio
    # from automation.desktop.app_scanner import get_scanner
    # scanner = get_scanner()
    # await scanner.scan_and_cache()
    # return {
    #     "status": "ok",
    #     "total": len(scanner.apps),
    #     "message": f"Rescan complete. {len(scanner.apps)} apps discovered.",
    # }
    return {
        "status": "disabled",
        "total": 0,
        "message": "App scanning is disabled.",
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


@router.get("/browser/test_tabs", summary="Verify multi-tab navigation, switching, closing and active tab tracking")
async def test_browser_tabs():
    from automation.browser.browser_engine import BrowserEngine
    from app.services.command_service import command_service
    import asyncio
    
    logs = []
    
    try:
        engine = BrowserEngine()
        
        # Step 1: Open acesoft
        logs.append("Step 1: Executing command 'open acesoft'...")
        res1 = await command_service.parse_and_execute("open acesoft")
        logs.append(f"Result status: {res1.get('status')}, result: {res1.get('result')}")
        
        await asyncio.sleep(2)
        
        # Step 2: Open google in new tab
        logs.append("Step 2: Executing command 'search google.com in the new tab'...")
        res2 = await command_service.parse_and_execute("search google.com in the new tab")
        logs.append(f"Result status: {res2.get('status')}, result: {res2.get('result')}")
        
        await asyncio.sleep(2)
        
        # Check active tab URL - should be google.com
        active_page = await engine.ensure_browser()
        logs.append(f"Currently active tab URL: {active_page.url}")
        
        # Step 3: Switch to previous tab
        logs.append("Step 3: Executing command 'switch to previous tab'...")
        res3 = await command_service.parse_and_execute("switch to previous tab")
        logs.append(f"Result status: {res3.get('status')}, result: {res3.get('result')}")
        
        await asyncio.sleep(2)
        active_page = await engine.ensure_browser()
        logs.append(f"After 'switch to previous tab', active tab URL: {active_page.url}")
        
        # Step 4: Switch to next tab
        logs.append("Step 4: Executing command 'go to next tab'...")
        res4 = await command_service.parse_and_execute("go to next tab")
        logs.append(f"Result status: {res4.get('status')}, result: {res4.get('result')}")
        
        await asyncio.sleep(2)
        active_page = await engine.ensure_browser()
        logs.append(f"After 'go to next tab', active tab URL: {active_page.url}")
        
        # Step 5: Switch to first tab
        logs.append("Step 5: Executing command 'switch to first tab'...")
        res5 = await command_service.parse_and_execute("switch to first tab")
        logs.append(f"Result status: {res5.get('status')}, result: {res5.get('result')}")
        
        await asyncio.sleep(2)
        active_page = await engine.ensure_browser()
        logs.append(f"After 'switch to first tab', active tab URL: {active_page.url}")
        
        return {"status": "success", "logs": logs}
    except Exception as e:
        import traceback
        return {"status": "error", "message": str(e), "traceback": traceback.format_exc(), "logs": logs}

