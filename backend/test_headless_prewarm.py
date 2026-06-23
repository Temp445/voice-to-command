import asyncio
import time
from playwright.async_api import async_playwright

async def main():
    try:
        p = await async_playwright().start()
        
        print("--- FIRST LAUNCH (HEADLESS PREWARM) ---")
        t0 = time.time()
        ctx1 = await p.chromium.launch_persistent_context('./tmp-profile-hw', headless=True)
        t1 = time.time()
        print(f"Prewarm took: {t1-t0:.2f}s")
        
        await ctx1.close()
        
        print("--- SECOND LAUNCH (VISIBLE) ---")
        t2 = time.time()
        ctx2 = await p.chromium.launch_persistent_context('./tmp-profile-hw', headless=False)
        t3 = time.time()
        print(f"Visible launch took: {t3-t2:.2f}s")
        
        await ctx2.close()
        await p.stop()
        print("SUCCESS")
    except Exception as e:
        print("ERROR:", e)

if __name__ == '__main__':
    import sys
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(main())
