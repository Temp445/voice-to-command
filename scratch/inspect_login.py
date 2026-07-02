import asyncio
from playwright.async_api import async_playwright

async def inspect():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp("http://127.0.0.1:9222")
        context = browser.contexts[0]
        pages = context.pages
        print(f"Number of open pages: {len(pages)}")
        for idx, page in enumerate(pages):
            print(f"Page {idx}: title='{await page.title()}', url='{page.url}'")
            inputs = await page.query_selector_all("input")
            print(f"  Inputs count: {len(inputs)}")
            for inp in inputs:
                t = await inp.get_attribute("type")
                name = await inp.get_attribute("name")
                ph = await inp.get_attribute("placeholder")
                val = await inp.evaluate("el => el.value")
                print(f"    - type={t}, name={name}, placeholder={ph}, value={val}")

asyncio.run(inspect())
