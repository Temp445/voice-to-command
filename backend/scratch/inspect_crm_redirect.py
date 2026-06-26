import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        try:
            browser = await p.chromium.connect_over_cdp("http://localhost:9222")
            page = browser.contexts[0].pages[0]
            
            # Go to HTTPS homepage
            print("Navigating to https://crm.acesoftcloud.in/ ...")
            await page.goto("https://crm.acesoftcloud.in/", wait_until="networkidle")
            print("Current URL:", page.url)
            
            # Get Sign In element
            signin_loc = page.locator("a:has-text('Sign In'), button:has-text('Sign In')").first
            href = await signin_loc.get_attribute("href")
            print("Sign In href:", href)
            
            # Click it
            print("Clicking Sign In...")
            await signin_loc.click()
            await asyncio.sleep(3)
            print("URL after click:", page.url)
            
            await browser.close()
        except Exception as e:
            print("Failed:", e)

if __name__ == "__main__":
    asyncio.run(main())
