import asyncio
from playwright.async_api import async_playwright

async def run_test():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp("http://127.0.0.1:9222")
        context = browser.contexts[0]
        pages = context.pages
        page = [pg for pg in pages if "login" in pg.url][0]
        print(f"Target page url: {page.url}")
        
        # Test locator count
        _loc = page.locator("input[type='password'], input[name*='pass' i], input[placeholder*='pass' i]").first
        count = await _loc.count()
        print(f"Locator count: {count}")
        if count > 0:
            try:
                print("Attempting to fill password field...")
                await _loc.fill("racer@123")
                print("Fill succeeded!")
            except Exception as e:
                print(f"Fill failed with exception: {type(e).__name__}: {e}")
        else:
            print("Password input locator count is 0!")

asyncio.run(run_test())
