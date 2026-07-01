import asyncio
import sys
import os

# Ensure root is in sys.path
from pathlib import Path
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.append(str(_ROOT))

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# Disable restriction for testing
from app.config import settings
settings.restrict_browser_automation = False

from app.services.command_service import command_service
from app.services.intent_registry import register_all_intents

async def main():
    try:
        register_all_intents()
        # Run command_service.parse_and_execute
        print("Parsing and executing 'deduction start month june'...")
        res = await command_service.parse_and_execute("deduction start month june")
        print("Result:")
        print(res)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
