import asyncio
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp("http://localhost:9222")
        context = browser.contexts[0]
        page = context.pages[0]
        
        # Get all elements with "Sheet1" text
        locators = await page.get_by_text("Sheet1").all()
        for i, loc in enumerate(locators):
            html = await loc.evaluate("el => el.outerHTML")
            role = await loc.evaluate("el => el.getAttribute('role')")
            tag = await loc.evaluate("el => el.tagName")
            print(f"Match {i}: Tag={tag}, Role={role}, HTML={html[:200]}")
            
asyncio.run(run())
