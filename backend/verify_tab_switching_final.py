import asyncio
import sys
import logging
from automation.browser.browser_engine import BrowserEngine
from automation.browser.tab_registry import tab_registry

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("FinalVerifier")

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

    # Let's get their target IDs via direct CDP target query
    cdp = await engine._browser.new_browser_cdp_session()
    res = await cdp.send("Target.getTargets")
    target_infos = res.get("targetInfos", [])
    
    chatgpt_tid = None
    youtube_tid = None
    for t in target_infos:
        if "chatgpt.com" in t.get("url", ""):
            chatgpt_tid = t.get("targetId")
        elif "youtube.com" in t.get("url", ""):
            youtube_tid = t.get("targetId")

    logger.info(f"ChatGPT target ID: {chatgpt_tid}")
    logger.info(f"YouTube target ID: {youtube_tid}")

    # Wait for things to stabilize
    logger.info("Waiting 3 seconds for active tab detection to initialize...")
    await asyncio.sleep(3.0)

    # Test 1: Switch to YouTube
    logger.info("\n--- TEST 1: Activating YouTube target via CDP ---")
    await cdp.send("Target.activateTarget", {"targetId": youtube_tid})
    
    logger.info("Executing real-time get_active_page()...")
    active_page = await engine.get_active_page()
    logger.info(f"get_active_page() returned URL: {active_page.url}")
    
    if active_page == youtube_page:
        logger.info("✅ TEST 1 PASSED: Target successfully resolved to YouTube!")
    else:
        logger.error(f"❌ TEST 1 FAILED: Target resolved to {active_page.url}")

    # Test 2: Switch to ChatGPT
    logger.info("\n--- TEST 2: Activating ChatGPT target via CDP ---")
    await cdp.send("Target.activateTarget", {"targetId": chatgpt_tid})
    
    logger.info("Executing real-time get_active_page()...")
    active_page = await engine.get_active_page()
    logger.info(f"get_active_page() returned URL: {active_page.url}")
    
    if active_page == chatgpt_page:
        logger.info("✅ TEST 2 PASSED: Target successfully resolved to ChatGPT!")
    else:
        logger.error(f"❌ TEST 2 FAILED: Target resolved to {active_page.url}")

    # Test 3: Verify background sync loop
    logger.info("\n--- TEST 3: Verifying 1.5s background sync loop ---")
    logger.info("Switching to YouTube target again...")
    await cdp.send("Target.activateTarget", {"targetId": youtube_tid})
    
    logger.info("Waiting 2.5 seconds for background sync loop to run...")
    await asyncio.sleep(2.5)
    
    reg_active = tab_registry.get_active()
    reg_active_url = reg_active.url if reg_active else "None"
    logger.info(f"TabRegistry active page after background sync: {reg_active_url}")
    if reg_active == youtube_page:
        logger.info("✅ TEST 3 PASSED: Background sync loop successfully updated TabRegistry to YouTube!")
    else:
        logger.error(f"❌ TEST 3 FAILED: TabRegistry has active page {reg_active_url}")

    logger.info("\nDetaching CDP session and closing browser engine...")
    await cdp.detach()
    await engine.close_browser()
    logger.info("All tests completed.")

if __name__ == "__main__":
    asyncio.run(main())
