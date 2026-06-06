import asyncio
import os
import sys

# Add backend dir to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from playwright.async_api import async_playwright
from automation.browser.dom_agent import DOMAgent
import automation.browser.dom_agent as da

# Create a mock LLM service
class MockLLM:
    async def chat(self, prompt):
        print("\n[FAILED] Fast path failed. Falling back to LLM.")
        return "element_123"

# Mock the module before initializing
da.llm_service = MockLLM()

async def test_dom_agent():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        mock_path = os.path.abspath('mock_crm.html')
        await page.goto(f"file:///{mock_path.replace(os.sep, '/')}")
        
        agent = DOMAgent(page)
        
        print("\n--- Test 1: 'expand lead management' ---")
        result = await agent.find_element_for_intent("expand lead management")
        print(f"Result Element ID: {result[0] if result and result[0] else None}")
        
        print("\n--- Test 2: 'click lead management' ---")
        result2 = await agent.find_element_for_intent("click lead management")
        print(f"Result Element ID: {result2[0] if result2 and result2[0] else None}")
        
        # Verify the actual elements in the DOM
        elements = await agent.get_interactive_elements()
        print("\n--- Extracted Elements ---")
        for el in elements:
            print(f"ID: {el['id']}, Text: {el.get('text', '')}, Tag: {el.get('tag', '')}, Aria: {el.get('aria', '')}")
            
        await browser.close()

if __name__ == '__main__':
    asyncio.run(test_dom_agent())
