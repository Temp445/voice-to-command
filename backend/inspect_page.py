import asyncio
from playwright.async_api import async_playwright

async def main():
    p = await async_playwright().start()
    browser = await p.chromium.launch(headless=True)
    context = await browser.new_context()
    page = await context.new_page()
    
    cdp = await context.new_cdp_session(page)
    try:
        # Try without arguments
        info = await cdp.send("Target.getTargetInfo")
        print("Target.getTargetInfo without args:")
        print(info)
    except Exception as e:
        print("Target.getTargetInfo without args failed:", e)
        
    await browser.close()
    await p.stop()

if __name__ == "__main__":
    asyncio.run(main())
