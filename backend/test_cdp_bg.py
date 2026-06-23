import asyncio
import subprocess
import time
import os
import sys

async def main():
    profile_path = os.path.abspath("./tmp-profile-bg2")
    os.makedirs(profile_path, exist_ok=True)
    
    chrome_path = r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
    
    cmd = [
        chrome_path,
        f"--user-data-dir={profile_path}",
        "--remote-debugging-port=9222",
        "--no-startup-window",
        "--disable-blink-features=AutomationControlled",
        "--no-first-run"
    ]
    
    print("Launching chrome in background...")
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    p = subprocess.Popen(cmd, creationflags=flags)
    time.sleep(3)
    
    from playwright.async_api import async_playwright
    pwt = await async_playwright().start()
    
    print("Connecting via CDP...")
    browser = await pwt.chromium.connect_over_cdp("http://localhost:9222")
    ctx = browser.contexts[0] if browser.contexts else browser
    
    print("Creating new page...")
    page = await ctx.new_page()
    await page.goto("https://example.com")
    
    await asyncio.sleep(2)
    
    # Can we maximize it?
    import pygetwindow as gw
    wins = gw.getWindowsWithTitle("Chrome") or gw.getWindowsWithTitle("Google Chrome")
    if wins:
        print(f"Maximizing {wins[0].title}")
        wins[0].maximize()
    else:
        print("No window found!")
        
    await asyncio.sleep(2)
    p.terminate()

if __name__ == '__main__':
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(main())
