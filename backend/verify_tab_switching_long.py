import asyncio
import sys
import logging
from automation.browser.browser_engine import BrowserEngine
from automation.browser.tab_registry import tab_registry

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("TabSwitchVerifier")

sys.stdout.reconfigure(encoding='utf-8')

async def main():
    logger.info("Initializing BrowserEngine...")
    engine = BrowserEngine()
    
    logger.info("Connecting to Chrome on port 9222...")
    await engine.ensure_browser()
    
    ctx = engine._context
    pages = [p for p in ctx.pages if not p.is_closed()]
    logger.info(f"Open pages: {len(pages)}")
    
    # Find ChatGPT and YouTube pages
    chatgpt_page = None
    youtube_page = None
    for p in pages:
        if "chatgpt.com" in p.url:
            chatgpt_page = p
        elif "youtube.com" in p.url:
            youtube_page = p

    if not chatgpt_page or not youtube_page:
        logger.error("Could not find both ChatGPT and YouTube pages open! Please ensure they are open.")
        await engine.close_browser()
        return

    logger.info(f"Found ChatGPT page: {chatgpt_page.url}")
    logger.info(f"Found YouTube page: {youtube_page.url}")

    # Wait 10 seconds for all background target seeding and visibility listeners to finish injecting
    logger.info("Waiting 10 seconds for setup/injection to stabilize...")
    await asyncio.sleep(10.0)

    # Step 1: Switch to YouTube programmatically
    logger.info("\n--- STEP 1: Switching to YouTube programmatically ---")
    await youtube_page.bring_to_front()
    
    # Wait for visibility listener/CDP updates
    await asyncio.sleep(3.0)
    
    active_now = tab_registry.get_active()
    active_url = active_now.url if active_now else "None"
    logger.info(f"Active tab URL in TabRegistry: {active_url}")
    if active_now == youtube_page:
        logger.info("✅ SUCCESS: Target correctly updated to YouTube!")
    else:
        logger.error(f"❌ FAILURE: Target is {active_url}, expected YouTube")

    # Step 2: Switch to ChatGPT programmatically
    logger.info("\n--- STEP 2: Switching to ChatGPT programmatically ---")
    await chatgpt_page.bring_to_front()
    
    # Wait for visibility listener/CDP updates
    await asyncio.sleep(3.0)
    
    active_now = tab_registry.get_active()
    active_url = active_now.url if active_now else "None"
    logger.info(f"Active tab URL in TabRegistry: {active_url}")
    if active_now == chatgpt_page:
        logger.info("✅ SUCCESS: Target correctly updated to ChatGPT!")
    else:
        logger.error(f"❌ FAILURE: Target is {active_url}, expected ChatGPT")

    logger.info("\nClosing connection...")
    await engine.close_browser()
    logger.info("Test run finished.")

if __name__ == "__main__":
    asyncio.run(main())
