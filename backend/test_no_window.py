import asyncio
from playwright.async_api import async_playwright

async def main():
    p = await async_playwright().start()
    print('started')
    ctx = await p.chromium.launch_persistent_context(
        './tmp-profile', 
        headless=False, 
        args=['--no-startup-window']
    )
    print('launched context')
    await asyncio.sleep(2)
    print('opening page')
    page = await ctx.new_page()
    await asyncio.sleep(2)
    await ctx.close()
    await p.stop()

if __name__ == '__main__':
    asyncio.run(main())
