import asyncio
import re
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        try:
            print("Connecting to Chrome on port 9222...")
            browser = await p.chromium.connect_over_cdp("http://localhost:9222")
            context = browser.contexts[0]
            pages = context.pages
            print(f"Total open pages: {len(pages)}")
            for idx, page in enumerate(pages):
                print(f"Page {idx}: {page.url} - {await page.title()}")
                
            # Filter pages to find the payroll app
            target_page = None
            for page in pages:
                if "payroll" in page.url:
                    target_page = page
                    break
            
            if not target_page:
                print("Payroll page not found among open tabs.")
                return
            
            print(f"Target page found: {target_page.url}")
            
            # 1. Try pressing Escape first
            print("Pressing Escape...")
            await target_page.keyboard.press("Escape")
            await asyncio.sleep(1.0)
            
            # 2. Try close button selectors
            CLOSE_SELECTORS = [
                "[aria-label*='close' i]",
                "[aria-label*='dismiss' i]",
                "[aria-label*='cancel' i]",
                "button.close",
                ".close",
                ".btn-close",
                ".modal-close",
                ".popup-close",
                ".dialog-close",
                "[class*='close-btn' i]",
                "[class*='closeBtn' i]",
                "[class*='close-button' i]",
                "[class*='lucide-x' i]",
                "svg[class*='x' i]",
                "button:has-text('×')",
                "button:has-text('✕')",
                "span:has-text('×')",
                "i:has-text('×')",
                "button:has-text('X')",
                "[role='button'][aria-label*='close' i]",
            ]
            
            for sel in CLOSE_SELECTORS:
                loc = target_page.locator(sel)
                count = await loc.count()
                for i in range(count):
                    el = loc.nth(i)
                    if await el.is_visible():
                        print(f"Found visible element with selector: {sel}")
                        await el.click()
                        print("Clicked!")
                        await asyncio.sleep(1.0)
                        
            # 3. Try text-based close
            print("Trying text-based close...")
            for label in ["cancel", "close", "dismiss"]:
                cancel_button = target_page.locator(
                    "button, a, input[type='button'], [role='button']"
                ).filter(has_text=re.compile(rf"^\s*{re.escape(label)}\s*$", re.IGNORECASE))
                
                if await cancel_button.count() == 0:
                    cancel_button = target_page.locator(
                        "button, a, input[type='button'], [role='button']"
                    ).filter(has_text=re.compile(re.escape(label), re.IGNORECASE))
                    
                if await cancel_button.count() == 0:
                    cancel_button = target_page.locator(
                        "div, span"
                    ).filter(has_text=re.compile(rf"^\s*{re.escape(label)}\s*$", re.IGNORECASE))
                    
                count = await cancel_button.count()
                for i in range(count):
                    btn = cancel_button.nth(i)
                    if await btn.is_visible():
                        print(f"Found visible '{label}' button: text={await btn.inner_text()}")
                        await btn.click()
                        print("Clicked!")
                        await asyncio.sleep(1.0)
            
            print("Done testing.")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
