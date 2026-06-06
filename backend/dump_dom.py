import asyncio
import json
import os
import sys

# Add backend dir to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from automation.browser.dom_agent import DOMAgent

async def main():
    agent = DOMAgent()
    await agent.initialize()
    elements = await agent.get_interactive_elements()
    
    with open('elements_dump.json', 'w', encoding='utf-8') as f:
        json.dump(elements, f, indent=2)
        
    print(f"Dumped {len(elements)} elements")

if __name__ == '__main__':
    asyncio.run(main())
