import asyncio
from playwright.async_api import async_playwright

async def main():
    p = await async_playwright().start()
    ctx = await p.chromium.launch_persistent_context('./tmp-profile-cdp', headless=False)
    page = ctx.pages[0] if ctx.pages else await ctx.new_page()
    await page.goto("https://example.com")
    
    # Wait to see normal size
    await asyncio.sleep(2)
    
    # Maximize via CDP
    print("Maximizing via CDP...")
    cdp = await ctx.new_cdp_session(page)
    res = await cdp.send("Browser.getWindowForTarget")
    window_id = res["windowId"]
    await cdp.send("Browser.setWindowBounds", {"windowId": window_id, "bounds": {"windowState": "maximized"}})
    
    await asyncio.sleep(3)
    await ctx.close()
    await p.stop()

if __name__ == '__main__':
    asyncio.run(main())
