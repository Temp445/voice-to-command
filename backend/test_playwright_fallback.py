import asyncio
import sys
import logging
from loguru import logger
from automation.browser.browser_controller import BrowserController

# Set up simple logging
logger.add(sys.stdout, level="INFO")

async def test_browser():
    print("Initializing BrowserController...")
    controller = BrowserController()
    
    print("\n1. Searching YouTube for 'lofi girl'...")
    res1 = await controller.search_youtube("lofi girl")
    print(f"Result: {res1}")
    
    # Wait for page to load
    await asyncio.sleep(4)
    
    print("\n2. Getting page title...")
    title = await controller.get_page_title()
    print(f"Title: {title}")
    
    print("\n3. Clicking first result...")
    res2 = await controller.click_first_result()
    print(f"Result: {res2}")
    
    print("\n4. Getting new page title...")
    await asyncio.sleep(4)
    title2 = await controller.get_page_title()
    print(f"New Title: {title2}")
    
    print("\nDone. Browser will remain open for 5 seconds to verify.")
    await asyncio.sleep(5)
    await controller.close()

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(test_browser())
