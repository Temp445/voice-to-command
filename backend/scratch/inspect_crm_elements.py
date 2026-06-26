import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        try:
            browser = await p.chromium.connect_over_cdp("http://localhost:9222")
            page = browser.contexts[0].pages[0]
            await page.goto("https://crm.acesoftcloud.in/", wait_until="domcontentloaded")
            
            print("--- HTML OF LINK ---")
            link = page.locator("a:has-text('Sign In')").first
            if await link.count() > 0:
                print(await link.evaluate("el => el.outerHTML"))
            else:
                print("No link found")
                
            print("--- HTML OF BUTTON ---")
            btn = page.locator("button:has-text('Sign In')").first
            if await btn.count() > 0:
                print(await btn.evaluate("el => el.outerHTML"))
            else:
                print("No button found")
                
            await browser.close()
        except Exception as e:
            print("Failed:", e)

if __name__ == "__main__":
    asyncio.run(main())
