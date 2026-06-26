import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto("http://crm.acesoftcloud.in/", wait_until="domcontentloaded")
        
        print("--- LINKS ---")
        links = await page.locator("a").all()
        for idx, link in enumerate(links):
            text = await link.inner_text()
            href = await link.get_attribute("href")
            visible = await link.is_visible()
            print(f"Link {idx}: text={text.strip()!r}, href={href!r}, visible={visible}")
            
        print("--- BUTTONS ---")
        buttons = await page.locator("button").all()
        for idx, btn in enumerate(buttons):
            text = await btn.inner_text()
            visible = await btn.is_visible()
            print(f"Button {idx}: text={text.strip()!r}, visible={visible}")
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
