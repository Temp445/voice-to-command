import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        try:
            browser = await p.chromium.connect_over_cdp("http://localhost:9222")
            page = browser.contexts[0].pages[0]
            print("Navigating directly to crm.acesoftcloud.in/login ...")
            await page.goto("https://crm.acesoftcloud.in/login", wait_until="commit")
            await asyncio.sleep(4)
            print("Final URL:", page.url)
            await browser.close()
        except Exception as e:
            print("Failed:", e)

if __name__ == "__main__":
    asyncio.run(main())
