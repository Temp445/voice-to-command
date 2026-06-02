import asyncio
import tempfile
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        temp_dir = tempfile.mkdtemp()
        ctx = await p.chromium.launch_persistent_context(
            user_data_dir=temp_dir,
            channel="chrome",
            headless=False,
            args=[
                "--start-maximized",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-sync",
                "--disable-infobars",
                "--disable-features=OptimizationHints,MediaRouter,DialMediaRouteProvider,CalculateNativeWinOcclusion,ProfilePicker"
            ]
        )
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()
        await page.goto("https://google.com")
        await asyncio.sleep(2)
        await ctx.close()

asyncio.run(main())
