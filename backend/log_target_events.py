import asyncio
import sys
import logging
from playwright.async_api import async_playwright

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("CDPTargetLogger")

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
    
    # Enable target discovery so activatedTarget events flow
    await cdp.send("Target.setDiscoverTargets", {"discover": True})
    
    # Register specific listeners
    def make_listener(event_name):
        def listener(params):
            logger.info(f"🟢 [CDP EVENT] {event_name} -> {params}")
        return listener

    events = [
        "Target.targetActivated",
        "Target.targetCreated",
        "Target.targetDestroyed",
        "Target.targetInfoChanged"
    ]
    
    for ev in events:
        cdp.on(ev, make_listener(ev))
        logger.info(f"Subscribed to {ev}")
        
    logger.info("="*80)
    logger.info("LOGGING TARGET CDP EVENTS")
    logger.info("Please switch tabs manually in Chrome now...")
    logger.info("="*80)
    
    # Run for 20 seconds to capture events
    await asyncio.sleep(20.0)
    
    logger.info("Completed target event logging.")
    await p.stop()

if __name__ == "__main__":
    asyncio.run(main())
