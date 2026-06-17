import asyncio
import sys
from playwright.async_api import async_playwright
from automation.desktop.window_manager import WindowManager

async def main():
    print("Launching Playwright browser with Chrome channel...")
    async with async_playwright() as p:
        # Launch using Google Chrome channel (same as the main application)
        browser = await p.chromium.launch(channel="chrome", headless=False)
        context = await browser.new_context(no_viewport=True)
        page = await context.new_page()
        await page.goto("https://crm.acesoftcloud.in/dashboard")
        
        # Get actual page title
        title = await page.title()
        print(f"Page launched. Title: '{title}'")
        
        # Minimize the window using WindowManager
        wm = WindowManager()
        win = wm._find_window_by_title(title)
        if win:
            print("Found window. Minimizing it...")
            win.minimize()
        else:
            print("Could not find window by title initially!")
            
        print("Waiting 3 seconds in minimized state...")
        await asyncio.sleep(3)
        
        print("Attempting to restore, maximize, and focus...")
        wm.force_focus_by_title(title)
        
        print("Waiting 5 seconds to inspect result...")
        await asyncio.sleep(5)
        
        await browser.close()
        print("Done.")

if __name__ == "__main__":
    asyncio.run(main())
