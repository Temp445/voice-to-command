import asyncio
import os
import sys
from playwright.async_api import async_playwright

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

async def main():
    p = await async_playwright().start()
    print('started')
    ctx = await p.chromium.launch_persistent_context(
        './tmp-profile-pos', 
        headless=False, 
        channel="chrome",
        args=['--window-position=-32000,-32000', '--disable-blink-features=AutomationControlled']
    )
    print('launched context')
    await asyncio.sleep(2)
    print('opening page')
    page = ctx.pages[0] if ctx.pages else await ctx.new_page()
    await page.goto("https://example.com")
    print('navigated')
    await asyncio.sleep(1)
    
    # Try maximizing
    try:
        import pygetwindow as gw
        wins = gw.getWindowsWithTitle("Chrome") or gw.getWindowsWithTitle("Google Chrome")
        if wins:
            print(f'found window: {wins[0].title}')
            wins[0].maximize()
            print('maximized')
        else:
            print('no window found')
    except Exception as e:
        print(f'gw err: {e}')
        
    await asyncio.sleep(2)
    await ctx.close()
    await p.stop()

if __name__ == '__main__':
    asyncio.run(main())
