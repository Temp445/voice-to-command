import asyncio
import sys
from loguru import logger
from app.services.command_service import command_service
from app.services.intent_registry import register_all_intents
import json

# Setup
register_all_intents()

commands_to_test = [
    "switch to last tab",
    "close all tabs",
    "hover over the menu",
    "copy selected text",
    "select all",
    "scroll down a little",
    "fill the form with my details",
    "check the checkbox",
    "summarize this page",
    "take a full page screenshot",
    "restart browser",
    "clear highlights",
    "open google and search for python",
    # New Commands Added Below:
    "click the first result",
    "double click the image",
    "right click here",
    "press escape",
    "press tab",
    "maximize window",
    "minimize window",
    "restore window",
    "wait for login button",
    "wait for search results",
    "download this file",
    "upload a file"
]

async def main():
    results = {}
    for cmd in commands_to_test:
        logger.info(f"Testing command: '{cmd}'")
        res = await command_service.parse_and_execute(cmd)
        results[cmd] = {
            "intent": res.get("intent"),
            "status": res.get("status")
        }
    
    with open("test_results_nlp.json", "w") as f:
        json.dump(results, f, indent=2)
        
    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    # Ensure Windows asyncio loop policy
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(main())
