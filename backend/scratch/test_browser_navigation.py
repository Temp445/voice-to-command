import asyncio
import sys
import os
from loguru import logger

# Add root backend to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from automation.browser.browser_engine import BrowserEngine
from automation.desktop.window_manager import WindowManager

async def test():
    engine = BrowserEngine()
    wm = WindowManager()
    
    print("Step 1: Navigating to Google (this will launch the browser if not running)...")
    res1 = await engine.navigate("https://www.google.com")
    print(f"Navigation result: {res1}")
    
    # Wait for the browser window to settle
    await asyncio.sleep(3)
    
    # Let's find the browser window and minimize it
    print("Step 2: Locating the browser window to minimize it...")
    # Using our new PID-first matching or title
    win = wm._find_window_by_title("google")
    if win:
        print(f"Found browser window: '{win.window_text()}'. Minimizing it...")
        win.minimize()
    else:
        print("Could not find browser window!")
        
    print("Waiting 3 seconds in minimized state...")
    await asyncio.sleep(3)
    
    print("Step 3: Navigating to Wikipedia (should restore, maximize, and foreground the browser)...")
    res2 = await engine.navigate("https://www.wikipedia.org")
    print(f"Navigation result: {res2}")
    
    print("Waiting 5 seconds to inspect the screen state...")
    await asyncio.sleep(5)
    
    # Clean up
    print("Closing browser...")
    await engine.close_browser()
    print("Test complete.")

if __name__ == "__main__":
    asyncio.run(test())
