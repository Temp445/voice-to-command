import asyncio
import sys
from loguru import logger

# Add backend folder to sys.path
sys.path.append(r"e:\Nivin_Sync\ACE\Voice\voice-to-command\backend")

from app.core.logging import setup_logging
from automation.browser.browser_controller import BrowserController

async def main():
    setup_logging()
    bc = BrowserController()
    
    # Ensure page is loaded/connected
    page = await bc._ensure_page()
    if not page:
        print("No active page found!")
        return

    print("Active page URL:", page.url)
    print("Page Title:", await page.title())

    # Get all buttons, links, spans, svgs, etc.
    elements = await page.evaluate("""() => {
        const results = [];
        document.querySelectorAll('button, a, input[type="button"], [role="button"], span, i, svg').forEach(el => {
            const rect = el.getBoundingClientRect();
            if (rect.width > 0 && rect.height > 0) {
                results.push({
                    tag: el.tagName,
                    text: el.innerText || el.textContent || "",
                    id: el.id,
                    className: el.className,
                    role: el.getAttribute('role'),
                    ariaLabel: el.getAttribute('aria-label'),
                    rect: { x: rect.x, y: rect.y, width: rect.width, height: rect.height }
                });
            }
        });
        return results;
    }""")

    print(f"\nFound {len(elements)} visible elements:")
    for i, el in enumerate(elements):
        text = el['text'].replace('\n', ' ').strip()
        desc = f"Tag: {el['tag']}, Text: '{text}', ID: '{el['id']}', Class: '{el['className']}', Role: '{el['role']}', AriaLabel: '{el['ariaLabel']}'"
        print(f"[{i}] {desc}")

if __name__ == "__main__":
    asyncio.run(main())
