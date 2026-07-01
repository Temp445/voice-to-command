import asyncio
import sys
import os

# Ensure root is in sys.path
from pathlib import Path
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.append(str(_ROOT))

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from app.config import settings
settings.restrict_browser_automation = False

from app.services.page_context_service import page_context_service

async def main():
    from automation.browser.browser_engine import BrowserEngine
    from automation.browser.dom_agent import DOMAgent
    try:
        engine = BrowserEngine()
        page = await engine.get_active_page()
        if not page:
            print("Failed to get active page.", flush=True)
            return
        print(f"Connected to page: {page.url}", flush=True)
        
        print("Getting snapshot...", flush=True)
        page_context_service.invalidate()
        snapshot = await page_context_service.get_snapshot()
        print("Snapshot retrieved.", flush=True)
        
        # Find element Deduction Start Month
        el = None
        for item in snapshot.elements:
            if "deduction" in item.name.lower():
                el = item
                break
                
        if not el:
            print("Element not found in snapshot.", flush=True)
            return
            
        print(f"Found element: {el.tag}, name={el.name}", flush=True)
        
        print("Locating element handle...", flush=True)
        agent = DOMAgent(page)
        handle = await agent.get_element_handle(el)
        print(f"Handle result: {handle}", flush=True)
        
    except Exception as e:
        print(f"Error: {e}", flush=True)

if __name__ == "__main__":
    asyncio.run(main())
