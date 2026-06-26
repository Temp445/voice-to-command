import asyncio
import urllib.request
import json
from playwright.async_api import async_playwright
from automation.browser.tab_registry import tab_registry

async def test():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp("http://localhost:9222")
        context = browser.contexts[0]
        pages = [pg for pg in context.pages if not pg.is_closed()]
        print("Pages open in Chrome:", [pg.url for pg in pages])
        
        # Register them in tab_registry
        for pg in pages:
            if not pg.url.startswith("chrome-extension://") and pg.url != "about:blank":
                tab_registry.register(pg)
                
        # Wait for target ID seeding
        print("Waiting 2s for target ID seeding...")
        await asyncio.sleep(2)
        
        print("\n--- Current mapped target IDs ---")
        with tab_registry._mu:
            print("tab_ids:", list(tab_registry._pages.keys()))
            print("target_ids mapping:", tab_registry._target_ids)
            print("target_to_tab mapping:", tab_registry._target_to_tab)
            print("active_tab_id:", tab_registry._active_tab_id)
            active_pg = tab_registry.get_active()
            print("active page url:", active_pg.url if active_pg else None)
            
        # Enable CDP event wiring
        print("\nWiring CDP session...")
        await tab_registry.wire_cdp_session(context)
        
        # Get CRM and Payroll pages
        crm_pg = [pg for pg in pages if "crm" in pg.url][0]
        payroll_pg = [pg for pg in pages if "payroll" in pg.url][0]
        
        # Test 1: Switch to CRM
        print("\n--- Test 1: Switch to CRM page ---")
        print("Bringing CRM page to front...")
        await crm_pg.bring_to_front()
        print("Waiting 3s for sync / events...")
        await asyncio.sleep(3)
        active_pg = tab_registry.get_active()
        print("Active page in tab_registry:", active_pg.url if active_pg else "None")
        if active_pg == crm_pg:
            print("✅ TEST 1 PASSED: TabRegistry detected switch to CRM")
        else:
            print("❌ TEST 1 FAILED")
            
        # Test 2: Switch to Payroll
        print("\n--- Test 2: Switch to Payroll page ---")
        print("Bringing Payroll page to front...")
        await payroll_pg.bring_to_front()
        print("Waiting 3s for sync / events...")
        await asyncio.sleep(3)
        active_pg = tab_registry.get_active()
        print("Active page in tab_registry:", active_pg.url if active_pg else "None")
        if active_pg == payroll_pg:
            print("✅ TEST 2 PASSED: TabRegistry detected switch to Payroll")
        else:
            print("❌ TEST 2 FAILED")

asyncio.run(test())
