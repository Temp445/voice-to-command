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

async def main():
    from automation.browser.browser_engine import BrowserEngine
    try:
        engine = BrowserEngine()
        page = await engine.get_active_page()
        if not page:
            print("Failed to get active page.", flush=True)
            return
        print(f"Connected to page: {page.url}", flush=True)
        
        print("Evaluating a basic query...", flush=True)
        handle = await page.evaluate_handle("() => document.querySelector('input')")
        print(f"Basic query handle result: {handle}", flush=True)
        
    except Exception as e:
        print(f"Error: {e}", flush=True)

if __name__ == "__main__":
    asyncio.run(main())
