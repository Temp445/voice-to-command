import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        try:
            browser = await p.chromium.connect_over_cdp("http://localhost:9222")
            page = browser.contexts[0].pages[0]
            await page.goto("https://crm.acesoftcloud.in/login", wait_until="networkidle")
            print("URL:", page.url)
            print("Title:", await page.title())
            body_text = await page.locator("body").inner_text()
            print("Body Text Preview:", body_text[:500])
            await browser.close()
        except Exception as e:
            print("Failed:", e)

if __name__ == "__main__":
    asyncio.run(main())
