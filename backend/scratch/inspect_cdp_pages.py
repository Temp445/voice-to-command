import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        try:
            browser = await p.chromium.connect_over_cdp("http://localhost:9222")
            contexts = browser.contexts
            print(f"Connected. Number of contexts: {len(contexts)}")
            for idx, ctx in enumerate(contexts):
                pages = ctx.pages
                print(f"Context {idx}: {len(pages)} pages")
                for p_idx, page in enumerate(pages):
                    print(f"  Page {p_idx}: url={page.url}, title={await page.title()}")
            await browser.close()
        except Exception as e:
            print("Failed to connect or query CDP:", e)

if __name__ == "__main__":
    asyncio.run(main())
