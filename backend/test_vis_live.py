import asyncio
import sys
import logging
from playwright.async_api import async_playwright

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("VisLive")

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

    ctx = browser.contexts[0]
    pages = ctx.pages
    logger.info(f"Open pages: {len(pages)}")

    for idx, page in enumerate(pages):
        url = page.url
        logger.info(f"Page {idx} URL: {url}")
        
        # Expose callback
        func_name = f"report_vis_{idx}"
        
        async def make_cb(i=idx, p_obj=page):
            async def _cb():
                logger.info(f"🟢 CALLBACK TRIGGERED for Page {i} (URL: {p_obj.url})")
            return _cb
            
        await page.expose_function(func_name, await make_cb())
        
        script = f"""
        (() => {{
            const handler = () => {{
                if (document.visibilityState === 'visible') {{
                    window.{func_name}().catch(() => {{}});
                }}
            }};
            document.addEventListener('visibilitychange', handler);
            window.addEventListener('focus', handler);
            window.addEventListener('pageshow', handler);
            handler();
        }})();
        """
        await page.add_init_script(script)
        try:
            await page.evaluate(script)
            logger.info(f"Injected listener to Page {idx}")
        except Exception as e:
            logger.warning(f"Failed to evaluate on Page {idx}: {e}")

    logger.info("Listening for 20 seconds. Please switch tabs between ChatGPT and YouTube manually now...")
    await asyncio.sleep(20.0)
    
    logger.info("Test finished.")
    await p.stop()

if __name__ == "__main__":
    asyncio.run(main())
