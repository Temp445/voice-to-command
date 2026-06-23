import asyncio
import subprocess
import time
import os
import sys

async def main():
    try:
        profile_path = os.path.abspath("./tmp-profile-bg4")
        os.makedirs(profile_path, exist_ok=True)
        
        chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        if not os.path.exists(chrome_path):
            chrome_path = r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
            
        cmd = [
            chrome_path,
            f"--user-data-dir={profile_path}",
            "--remote-debugging-port=9222",
            "--no-startup-window",
            "--disable-blink-features=AutomationControlled",
            "--no-first-run",
            "--no-default-browser-check"
        ]
        
        print("Launching chrome in background...")
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        p = subprocess.Popen(cmd, creationflags=flags)
        
        # wait for cdp port to open
        for _ in range(20):
            try:
                import urllib.request
                urllib.request.urlopen("http://localhost:9222/json/version", timeout=1)
                print("CDP port is up!")
                break
            except:
                time.sleep(0.5)
                
        from playwright.async_api import async_playwright
        pwt = await async_playwright().start()
        
        print("Connecting via CDP...")
        browser = await pwt.chromium.connect_over_cdp("http://localhost:9222")
        ctx = browser.contexts[0] if browser.contexts else await browser.new_context()
        
        print(f"Context pages: {len(ctx.pages)}")
        
        print("Waiting 2s...")
        await asyncio.sleep(2)
        
        print("Creating new page...")
        page = await ctx.new_page()
        await page.goto("https://example.com")
        print("Navigation done. Window should be visible!")
        
        await asyncio.sleep(3)
        await browser.close()
        await pwt.stop()
        p.kill()
        print("SUCCESS")
    except Exception as e:
        print("ERROR:", e)

if __name__ == '__main__':
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(main())
