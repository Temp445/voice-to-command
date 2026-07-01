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

# Force stdout to use utf-8
sys.stdout.reconfigure(encoding='utf-8')

# Disable restriction for this diagnostic dump script
from app.config import settings
settings.restrict_browser_automation = False

from app.services.page_context_service import page_context_service

async def main():
    from automation.browser.browser_engine import BrowserEngine
    try:
        engine = BrowserEngine()
        page = await engine.get_active_page()
        if not page:
            print("Failed to get active page.")
            return
        print(f"Connected to page: {page.url}")
        
        snapshot = await page_context_service.get_snapshot()
        if not snapshot or not snapshot.elements:
            print("No elements extracted by scanner.")
            return
            
        print(f"Total interactive elements: {len(snapshot.elements)}")
        for i, el in enumerate(snapshot.elements):
            text = el.text.replace("\n", " ")
            context = getattr(el, 'context', '').replace("\n", " ")
            print(f"[{i}] tag={el.tag}, role={el.role}, text='{text}', name='{el.name}', id='{el.el_id}', context='{context}'")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
