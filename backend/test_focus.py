import asyncio
import time
import uuid
import sys

from playwright.async_api import async_playwright

async def main():
    p = await async_playwright().start()
    ctx = await p.chromium.launch_persistent_context('./tmp-profile-focus', headless=False)
    page = ctx.pages[0] if ctx.pages else await ctx.new_page()
    await page.goto("https://example.com")
    
    unique_title = str(uuid.uuid4())
    print("Setting unique title:", unique_title)
    
    # Store original and set unique
    await page.evaluate(f"window.__origTitle = document.title; document.title = '{unique_title}';")
    
    await asyncio.sleep(1) # wait for OS to register title change
    
    import pygetwindow as gw
    import ctypes
    
    wins = gw.getWindowsWithTitle(unique_title)
    if wins:
        win = wins[0]
        print("Found window!", win.title)
        
        # Windows focus stealing bypass
        # Press ALT key
        ctypes.windll.user32.keybd_event(0x12, 0, 0, 0) # ALT down
        ctypes.windll.user32.keybd_event(0x12, 0, 2, 0) # ALT up
        
        # Restore and set foreground
        win.restore()
        user32 = ctypes.windll.user32
        user32.SetForegroundWindow(win._hWnd)
        win.maximize()
        print("Forced to front and maximized.")
    else:
        print("Window not found!")
        
    # Restore title
    await page.evaluate("document.title = window.__origTitle;")
    
    await asyncio.sleep(5)
    await ctx.close()
    await p.stop()

if __name__ == '__main__':
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(main())
