import asyncio
import json
from automation.browser.browser_engine import ACEBrowserEngine

async def main():
    e = ACEBrowserEngine()
    elements = await e.get_interactive_elements()
    with open('elements.json', 'w', encoding='utf-8') as f:
        json.dump(elements, f, indent=2)

if __name__ == '__main__':
    asyncio.run(main())
