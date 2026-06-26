import asyncio
import sys
from loguru import logger

# Add app to path
sys.path.insert(0, ".")

from app.services.command_service import CommandService
from automation.browser.browser_engine import BrowserEngine

async def run():
    # Configure logger to print to stdout
    logger.remove()
    logger.add(sys.stdout, level="DEBUG")
    
    # Initialize BrowserEngine and connect to remote debugging port
    engine = BrowserEngine()
    
    print("Initializing browser engine and connecting...")
    # Trigger get_active_page to establish connection
    page = await engine.get_active_page()
    if not page:
        print("Could not get active page! Is Chrome running on 9222?")
        return
        
    print(f"Active page: {page.url}")
    
    service = CommandService()
    print("Executing voice command...")
    res = await service.parse_and_execute("email nivin3456@gmail.com password reSet@123")
    print(f"Result dictionary:\n{res}")

if __name__ == "__main__":
    asyncio.run(run())
