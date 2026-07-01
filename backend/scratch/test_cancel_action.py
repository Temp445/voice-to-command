import asyncio
import sys
import os
from loguru import logger

# Add backend to sys.path so we can import app modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.intent_registry import handle_cancel
from automation.browser.browser_engine import BrowserEngine

async def main():
    engine = BrowserEngine()
    # Connect to the running Chrome instance
    page = await engine.ensure_browser()
    if not page:
        print("No active page found.")
        return
        
    print(f"Active page URL: {page.url}")
    print("Calling handle_cancel()...")
    
    result = await handle_cancel()
    print(f"Result of handle_cancel(): {result}")

if __name__ == "__main__":
    asyncio.run(main())
