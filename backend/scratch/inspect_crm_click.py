import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto("http://crm.acesoftcloud.in/", wait_until="domcontentloaded")
        
        print("Page URL before click:", page.url)
        
        # Click the Sign In link or button
        try:
            # Let's locate the Sign In link or button and click it
            signin = page.locator("a:has-text('Sign In'), button:has-text('Sign In')").first
            await signin.click()
            await page.wait_for_load_state("networkidle", timeout=5000)
        except Exception as e:
            print("Click failed or timed out:", e)
            
        print("Page URL after click:", page.url)
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
