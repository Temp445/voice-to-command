import asyncio
from playwright.async_api import async_playwright

async def main():
    p = await async_playwright().start()
    try:
        browser = await p.chromium.connect_over_cdp("http://localhost:9222")
        context = browser.contexts[0]
        print("Connected to Chrome via CDP!")
    except Exception as e:
        print("Failed to connect to Chrome on port 9222:", e)
        await p.stop()
        return

    pages = context.pages
    print(f"Number of pages: {len(pages)}")
    for i, page in enumerate(pages):
        print(f"Page {i}: {page.url}")
        
    if pages:
        cdp = await context.new_cdp_session(pages[0])
        await cdp.send("Target.setDiscoverTargets", {"discover": True})
        
        def on_event(event_name):
            return lambda params: print(f"CDP Event [{event_name}]:", params)
            
        cdp.on("Target.targetActivated", on_event("Target.targetActivated"))
        cdp.on("Target.targetCreated", on_event("Target.targetCreated"))
        cdp.on("Target.targetInfoChanged", on_event("Target.targetInfoChanged"))
        cdp.on("Target.targetDestroyed", on_event("Target.targetDestroyed"))
        
        print("Listening for 15 seconds. Switch tabs in Chrome now...")
        await asyncio.sleep(15)
            
    await browser.close()
    await p.stop()

if __name__ == "__main__":
    asyncio.run(main())
