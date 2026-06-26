import asyncio
import sys
import logging
from automation.browser.browser_engine import BrowserEngine
from automation.browser.tab_registry import tab_registry

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("CDPSwitchVerifier")

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

    # Let's get their target IDs
    chatgpt_tid = tab_registry._target_ids.get(tab_registry.get_tab_id(chatgpt_page))
    youtube_tid = tab_registry._target_ids.get(tab_registry.get_tab_id(youtube_page))

    logger.info(f"Found ChatGPT target ID: {chatgpt_tid} for {chatgpt_page.url}")
    logger.info(f"Found YouTube target ID: {youtube_tid} for {youtube_page.url}")

    # Wait 10 seconds for setup/injection to stabilize
    logger.info("Waiting 10 seconds for visibility listener setup to stabilize...")
    await asyncio.sleep(10.0)

    # Establish a browser CDP session to send Target commands
    cdp = await engine._browser.new_browser_cdp_session()

    # Step 1: Switch to YouTube
    logger.info("\n--- STEP 1: Activating YouTube target via CDP ---")
    await cdp.send("Target.activateTarget", {"targetId": youtube_tid})
    
    # Wait for visibility listener callback to fire
    await asyncio.sleep(4.0)
    
    active_now = tab_registry.get_active()
    active_url = active_now.url if active_now else "None"
    logger.info(f"Active tab URL in TabRegistry: {active_url}")
    if active_now == youtube_page:
        logger.info("✅ SUCCESS: Target correctly updated to YouTube!")
    else:
        logger.error(f"❌ FAILURE: Target is {active_url}, expected YouTube")

    # Step 2: Switch to ChatGPT
    logger.info("\n--- STEP 2: Activating ChatGPT target via CDP ---")
    await cdp.send("Target.activateTarget", {"targetId": chatgpt_tid})
    
    # Wait for visibility listener callback to fire
    await asyncio.sleep(4.0)
    
    active_now = tab_registry.get_active()
    active_url = active_now.url if active_now else "None"
    logger.info(f"Active tab URL in TabRegistry: {active_url}")
    if active_now == chatgpt_page:
        logger.info("✅ SUCCESS: Target correctly updated to ChatGPT!")
    else:
        logger.error(f"❌ FAILURE: Target is {active_url}, expected ChatGPT")

    logger.info("\nDetaching CDP session and closing browser engine...")
    await cdp.detach()
    await engine.close_browser()
    logger.info("Test run finished.")

if __name__ == "__main__":
    asyncio.run(main())
