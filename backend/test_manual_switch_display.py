import asyncio
import sys
import logging
from automation.browser.browser_engine import BrowserEngine
from automation.browser.tab_registry import tab_registry

# Configure standard logging to console
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("ManualSwitchTester")

sys.stdout.reconfigure(encoding='utf-8')

async def main():
    logger.info("Initializing BrowserEngine...")
    engine = BrowserEngine()
    
    logger.info("Connecting to Chrome on port 9222...")
    await engine.ensure_browser()
    
    ctx = engine._context
    
    # We want three tabs open with the specified URLs
    target_urls = [
        "https://crm.acesoftcloud.in/",
        "https://payroll-acesoftcloud.netlify.app/",
        "https://acesoft.in/"
    ]
    
    # Check existing pages
    pages = [p for p in ctx.pages if not p.is_closed()]
    logger.info(f"Currently open pages in Chrome: {len(pages)}")
    
    # Align existing pages or open new ones to match the target URLs (non-blocking)
    active_pages = []
    for i, url in enumerate(target_urls):
        if i < len(pages):
            pg = pages[i]
            logger.info(f"Reusing existing page {i} for {url} (non-blocking)...")
            # We run the navigation asynchronously so we don't block the monitoring startup
            asyncio.create_task(pg.goto(url, timeout=10000, wait_until="commit"))
        else:
            logger.info(f"Opening new page for {url} (non-blocking)...")
            pg = await ctx.new_page()
            asyncio.create_task(pg.goto(url, timeout=10000, wait_until="commit"))
        active_pages.append(pg)

    # Let the CDP handlers and seeding catch up
    await asyncio.sleep(2.0)
    
    logger.info("\n" + "="*80)
    logger.info("STARTING MANUAL SWITCH MONITORING")
    logger.info("Please manually switch tabs in the Chrome browser window.")
    logger.info("We will log the active tab in the TabRegistry every 1 second.")
    logger.info("="*80 + "\n")
    
    last_active_url = None
    for sec in range(120): # increased to 120 seconds to give plenty of time to test
        active_page = tab_registry.get_active()
        active_url = active_page.url if active_page else "None"
        focused_tid = tab_registry._focused_target_id
        
        # Format focused target details
        focused_info = "None"
        if focused_tid:
            focused_info = f"{focused_tid[:8]}…"
            # See if we have a tab_id for it
            tab_id = tab_registry._target_to_tab.get(focused_tid)
            if tab_id:
                focused_info += f" (tab_id: {tab_id[:8]}…)"
        
        if active_url != last_active_url:
            logger.info(f"[{sec:02d}s] 🔵 ACTIVE TAB CHANGED! URL: {active_url} | Focused Target: {focused_info}")
            last_active_url = active_url
        else:
            logger.info(f"[{sec:02d}s] Current active URL: {active_url} | Focused Target: {focused_info}")
            
        await asyncio.sleep(1.0)
        
    logger.info("\nMonitoring completed. Closing connection...")
    await engine.close_browser()
    logger.info("Done.")

if __name__ == "__main__":
    asyncio.run(main())
