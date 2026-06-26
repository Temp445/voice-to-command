import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        try:
            browser = await p.chromium.connect_over_cdp("http://localhost:9222")
            contexts = browser.contexts
            page = None
            for ctx in contexts:
                for pg in ctx.pages:
                    if "crm.acesoftcloud.in" in pg.url:
                        page = pg
                        break
                if page:
                    break
            
            if not page:
                print("No page with crm.acesoftcloud.in open! Opening one...")
                page = await contexts[0].new_page()
                await page.goto("http://crm.acesoftcloud.in/")
            
            # Go to home page if not already there
            if "/login" in page.url or "/dashboard" in page.url:
                print("Navigating page to homepage...")
                await page.goto("http://crm.acesoftcloud.in/")
                
            print("URL before clicking:", page.url)
            
            # Click the Sign In link/button
            signin = page.locator("a:has-text('Sign In'), button:has-text('Sign In')").first
            print("Clicking element...")
            await signin.click()
            
            # Wait a few seconds to see if it redirects
            await asyncio.sleep(3)
            print("URL after clicking:", page.url)
            
            await browser.close()
        except Exception as e:
            print("Failed:", e)

if __name__ == "__main__":
    asyncio.run(main())
