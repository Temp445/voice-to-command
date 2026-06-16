import asyncio
import sys
import os

sys.path.append(os.path.abspath("backend"))

from backend.automation.browser.browser_engine import BrowserEngine
from backend.automation.browser.dom_agent import DOMAgent

async def main():
    try:
        be = BrowserEngine()
        page = await be.ensure_browser()
        print(f"Browser Page: {page.url}")
        
        agent = DOMAgent(page)
        print("Getting elements...")
        els = await agent.get_interactive_elements()
        print(f"Elements: {len(els)}")
    except Exception as e:
        print(f"Error: {e}")

asyncio.run(main())
