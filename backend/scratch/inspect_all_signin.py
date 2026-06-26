import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        try:
            browser = await p.chromium.connect_over_cdp("http://localhost:9222")
            page = browser.contexts[0].pages[0]
            await page.goto("https://crm.acesoftcloud.in/", wait_until="domcontentloaded")
            
            elements = await page.locator("a, button").all()
            for idx, el in enumerate(elements):
                text = await el.inner_text()
                if "sign in" in text.lower():
                    html = await el.evaluate("el => el.outerHTML")
                    visible = await el.is_visible()
                    print(f"El {idx}: visible={visible}, html={html}")
                    
            await browser.close()
        except Exception as e:
            print("Failed:", e)

if __name__ == "__main__":
    asyncio.run(main())
