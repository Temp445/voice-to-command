import asyncio
import sys
import logging
from playwright.async_api import async_playwright

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("CDPLogger")

sys.stdout.reconfigure(encoding='utf-8')

async def main():
    p = await async_playwright().start()
    try:
        browser = await p.chromium.connect_over_cdp("http://localhost:9222")
        logger.info("Connected to Chrome successfully!")
    except Exception as e:
        logger.error(f"Failed to connect: {e}")
        await p.stop()
        return

    # Create browser-level CDP session
    cdp = await browser.new_browser_cdp_session()
    
    # Enable all Target domain events
    await cdp.send("Target.setDiscoverTargets", {"discover": True})
    
    # Let's listen to all events on this session
    def on_cdp_event(event_data):
        method = event_data.get("method")
        params = event_data.get("params")
        logger.info(f"[CDP Event Received] Method: {method} | Params: {params}")

    # Listen to raw protocol events in Playwright
    # CDPSession inherits from EventEmitter. The event is 'event' in python playwright.
    cdp.on("event", on_cdp_event)
    
    logger.info("="*80)
    logger.info("LOGGING ALL BROWSER-LEVEL CDP EVENTS")
    logger.info("Please switch tabs manually in Chrome now...")
    logger.info("="*80)
    
    # Run for 20 seconds to capture events
    await asyncio.sleep(20.0)
    
    logger.info("Completed event logging.")
    await browser.close()
    await p.stop()

if __name__ == "__main__":
    asyncio.run(main())
