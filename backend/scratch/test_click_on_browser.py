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
    try:
        engine = BrowserEngine()
        page = await engine.get_active_page()
        if not page:
            print("Failed to get active page.")
            return
        print(f"Connected to page: {page.url}")
        
        artifact_dir = "C:/Users/Nivin/.gemini/antigravity/brain/a5d38af5-67b6-4c53-9ca0-1a394ef563a2"
        
        # Take a screenshot before click
        before_path = os.path.join(artifact_dir, "before_click.png")
        await page.screenshot(path=before_path)
        print(f"Before click screenshot saved to: {before_path}")
        
        snapshot = await page_context_service.get_snapshot()
        if not snapshot or not snapshot.elements:
            print("No elements extracted by scanner.")
            return
            
        # Find element 17 (View button of the first row)
        view_el = None
        for el in snapshot.elements:
            if el.text == "View" and "6 months" in getattr(el, 'context', ''):
                view_el = el
                break
                
        if not view_el:
            print("Could not find 'View' button with '6 months' context.")
            # fallback: find first element with text "View" and tag "button"
            for el in snapshot.elements:
                if el.text == "View" and el.tag == "button":
                    view_el = el
                    break
                    
        if not view_el:
            print("Could not find any View button.")
            return
            
        print(f"Clicking element: role={view_el.role}, text='{view_el.text}', context='{getattr(view_el, 'context', '')}'")
        
        # Get handle
        from automation.browser.dom_agent.action_executor import ActionExecutorMixin
        class Executor(ActionExecutorMixin):
            def __init__(self, page):
                self.page = page
        
        executor = Executor(page)
        handle = await executor.get_element_handle(view_el)
        if not handle:
            print("Failed to get element handle.")
            return
            
        # Click
        await executor._click_element(handle)
        print("Clicked element.")
        
        await asyncio.sleep(2.0)
        
        # Take a screenshot after click
        after_path = os.path.join(artifact_dir, "after_click.png")
        await page.screenshot(path=after_path)
        print(f"After click screenshot saved to: {after_path}")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
