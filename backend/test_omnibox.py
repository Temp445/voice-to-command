import asyncio
import os
import sys
from playwright.async_api import async_playwright

async def main():
    p = await async_playwright().start()
    
    profile_path = os.path.abspath("./tmp-profile-omnibox")
    os.makedirs(profile_path, exist_ok=True)
    
    ctx = await p.chromium.launch_persistent_context(
        user_data_dir=profile_path,
        channel="chrome",
        headless=False,
        no_viewport=True,
        ignore_default_args=["--enable-automation"]
    )
    
    page = ctx.pages[0] if ctx.pages else await ctx.new_page()
    await page.goto("https://www.google.com/search?q=payroll")
    
    print("Waiting 2 seconds...")
    await asyncio.sleep(2)
    
    print("Pressing Control+L...")
    await page.keyboard.press("Control+l")
    
    print("Wait 5 seconds to observe...")
    await asyncio.sleep(5)
    
    await ctx.close()
    await p.stop()

if __name__ == '__main__':
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(main())
