import asyncio
import sys
import os

# Add parent directory to sys.path so we can import from app and automation
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from automation.browser.browser_engine import BrowserEngine

async def main():
    be = BrowserEngine()
    print("Prewarming profile (launching Chrome)...")
    await be.prewarm_profile()
    print("Ensuring browser is connected...")
    page = await be.ensure_browser()
    print(f"Browser connected! Active page URL: {page.url}")
    
    context = be._context
    print(f"Number of pages in context: {len(context.pages)}")
    
    # Listen to Target events
    cdp = await context.new_cdp_session(context.pages[0])
    await cdp.send("Target.setDiscoverTargets", {"discover": True})
    
    def on_event(event_name):
        return lambda params: print(f"\nCDP Event [{event_name}]: {params}")
        
    cdp.on("Target.targetActivated", on_event("Target.targetActivated"))
    cdp.on("Target.targetCreated", on_event("Target.targetCreated"))
    cdp.on("Target.targetInfoChanged", on_event("Target.targetInfoChanged"))
    cdp.on("Target.targetDestroyed", on_event("Target.targetDestroyed"))
    
    # Open another page to test
    print("\nOpening new tab...")
    await be.new_tab("https://example.com")
    
    print("\nWaiting 10 seconds. Try to switch tabs if possible (though we are headless/automated)...")
    await asyncio.sleep(10)
    
    await be.close_browser()
    await be.kill_browser()

if __name__ == "__main__":
    asyncio.run(main())
