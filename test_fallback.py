import asyncio
import sys
import os
import traceback
from rapidfuzz import fuzz

sys.path.append(os.path.abspath("backend"))

from backend.automation.browser.browser_controller import BrowserController
from backend.automation.browser.dom_agent import DOMAgent

async def main():
    try:
        print("Testing DOMAgent match for 'start free trail'...")
        bc = BrowserController()
        page = await bc.engine.ensure_browser()
        print(f"Connected to page: {page.url}")
        
        agent = DOMAgent(page)
        elements = await agent.get_interactive_elements()
        print(f"Found {len(elements)} interactive elements.")
        
        intent = "click start free trail"
        clean_intent = "start free trail"
        
        print("\n--- Substring & Fuzzy Match Debug ---")
        for el in elements:
            text_val = el.get('text', '').lower().strip()
            aria_val = el.get('aria', '').lower().strip()
            
            if 'free' in text_val or 'trial' in text_val or 'trail' in text_val:
                print(f"Element ID: {el.get('id')} | Tag: {el.get('tag')} | Text: '{text_val}' | Aria: '{aria_val}'")
                w_score = fuzz.WRatio(clean_intent, text_val)
                p_score = fuzz.partial_ratio(clean_intent, text_val)
                print(f"  -> WRatio: {w_score:.2f} | partial_ratio: {p_score:.2f}")
                
        print("\nRunning execute_intent...")
        res = await agent.execute_intent(intent)
        print(f"Result: {res}")
        
    except Exception as e:
        traceback.print_exc()

asyncio.run(main())
