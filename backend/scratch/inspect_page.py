import asyncio
from playwright.async_api import async_playwright

async def inspect():
    async with async_playwright() as p:
        try:
            browser = await p.chromium.connect_over_cdp("http://127.0.0.1:9222")
            contexts = browser.contexts
            if not contexts:
                print("No contexts found!")
                return
            context = contexts[0]
            pages = context.pages
            if not pages:
                print("No pages found!")
                return
            
            # Find active/visible page or the first page
            page = pages[0]
            print(f"Connected to page: {page.url}")
            print(f"Title: {await page.title()}")
            
            inputs = await page.locator("input").all()
            print(f"Found {len(inputs)} input elements:")
            for idx, inp in enumerate(inputs):
                html = await inp.evaluate("el => el.outerHTML")
                visible = await inp.is_visible()
                print(f"Input {idx}: visible={visible}, html={html}")
        except Exception as e:
            print(f"Error inspecting: {e}")

if __name__ == "__main__":
    asyncio.run(inspect())
