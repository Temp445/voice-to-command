import asyncio
import time
from playwright.async_api import async_playwright

async def main():
    p = await async_playwright().start()
    
    print("--- FIRST LAUNCH (HEADLESS PREWARM) ---")
    t0 = time.time()
    ctx1 = await p.chromium.launch_persistent_context('./tmp-profile-warm', headless=True)
    t1 = time.time()
    print(f"Prewarm took: {t1-t0:.2f}s")
    
    await ctx1.close()
    
    print("--- SECOND LAUNCH (VISIBLE) ---")
    t2 = time.time()
    ctx2 = await p.chromium.launch_persistent_context('./tmp-profile-warm', headless=False)
    t3 = time.time()
    print(f"Visible launch took: {t3-t2:.2f}s")
    
    await ctx2.close()
    await p.stop()

if __name__ == '__main__':
    asyncio.run(main())
