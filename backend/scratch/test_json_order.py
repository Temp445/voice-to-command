import asyncio
import urllib.request
import json
from playwright.async_api import async_playwright

async def test():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp("http://localhost:9222")
        context = browser.contexts[0]
        pages = context.pages
        print("Pages in context:", [p.url for p in pages])
        
        def get_json_targets():
            with urllib.request.urlopen("http://127.0.0.1:9222/json") as r:
                return json.loads(r.read().decode())
                
        pages_to_test = [p for p in pages if not p.url.startswith("chrome-extension://") and p.url != "about:blank"]
        
        print("\nActivating CRM page...")
        crm_page = [p for p in pages_to_test if "crm" in p.url][0]
        await crm_page.bring_to_front()
        await asyncio.sleep(2)
        targets = get_json_targets()
        print("--- After activating CRM ---")
        for i, t in enumerate(targets):
            if t.get("type") == "page":
                print(f"Index {i}: id={t.get('id')}, url={t.get('url')}")
                
        print("\nActivating Payroll page...")
        payroll_page = [p for p in pages_to_test if "payroll" in p.url][0]
        await payroll_page.bring_to_front()
        await asyncio.sleep(2)
        targets = get_json_targets()
        print("--- After activating Payroll ---")
        for i, t in enumerate(targets):
            if t.get("type") == "page":
                print(f"Index {i}: id={t.get('id')}, url={t.get('url')}")

asyncio.run(test())
