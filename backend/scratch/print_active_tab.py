import asyncio
import sys
sys.path.append('.')
from automation.browser.tab_registry import tab_registry
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp("http://localhost:9222")
        context = browser.contexts[0]
        
        # Let's populate the registry with the active pages first, since this script runs in a different process,
        # but wait - does get_active look at the memory space of the running FastAPI server?
        # No, because this is a separate process! The singleton tab_registry is process-local!
        # But we can read .ace_tab_registry.json to see what was persisted by the FastAPI server!
        import json
        import os
        state_file = "automation/browser/.ace_tab_registry.json"
        if os.path.exists(state_file):
            with open(state_file, "r") as f:
                print("Persisted state:", f.read())
        else:
            print("No persisted state found")
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
