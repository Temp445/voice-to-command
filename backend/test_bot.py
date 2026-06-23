import asyncio
import os
import sys
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

async def main():
    p = await async_playwright().start()
    
    profile_path = os.path.abspath("./tmp-profile-bot")
    os.makedirs(profile_path, exist_ok=True)
    
    args_list = [
        "--disable-blink-features=AutomationControlled",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-features=PasswordManager",
        "--disable-session-crashed-bubble",
        "--start-maximized"
    ]
    
    ctx = await p.chromium.launch_persistent_context(
        user_data_dir=profile_path,
        channel="chrome",
        headless=False,
        no_viewport=True,
        args=args_list,
        ignore_default_args=["--enable-automation"]
    )
    
    await Stealth().apply_stealth_async(ctx)
    
    page = ctx.pages[0] if ctx.pages else await ctx.new_page()
    await page.goto("https://bot.sannysoft.com/")
    await asyncio.sleep(5)
    await page.screenshot(path="bot_test.png", full_page=True)
    
    await ctx.close()
    await p.stop()

if __name__ == '__main__':
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(main())
