import asyncio
import os
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # Set simple HTML content with some height and a button in the middle
        html_content = """
        <html>
            <body style="background: #fafafa; margin: 0; padding: 100px;">
                <button id="btn" style="padding: 20px; font-size: 20px;">Click Me</button>
            </body>
        </html>
        """
        await page.set_content(html_content)
        
        # Injected JS style and DOM insertion code
        js_script = """
        async (args) => {
            const { x, y, actionType } = args;
            if (!document.body) return;
            
            let style = document.getElementById('ace-animations-style');
            if (!style) {
                style = document.createElement('style');
                style.id = 'ace-animations-style';
                style.innerHTML = `
                    .ace-virtual-cursor {
                        position: fixed;
                        width: 20px;
                        height: 20px;
                        background: rgba(255, 100, 0, 0.8) !important;
                        border: 2px solid #fff !important;
                        border-radius: 50% !important;
                        pointer-events: none !important;
                        z-index: 10000000 !important;
                        transition: all 0.5s cubic-bezier(0.25, 1, 0.5, 1) !important;
                        box-shadow: 0 0 10px rgba(0,0,0,0.5) !important;
                        transform: translate(-50%, -50%) !important;
                    }
                    .ace-click-ripple {
                        position: fixed;
                        border: 4px solid rgba(255, 100, 0, 0.8) !important;
                        border-radius: 50% !important;
                        pointer-events: none !important;
                        z-index: 10000000 !important;
                        transform: translate(-50%, -50%) !important;
                        animation: ace-ripple-ani 0.4s ease-out forwards !important;
                    }
                    .ace-element-highlight {
                        outline: 3px solid rgba(255, 100, 0, 0.8) !important;
                        outline-offset: 2px !important;
                        transition: outline 0.2s ease !important;
                    }
                    @keyframes ace-ripple-ani {
                        0% { width: 0px; height: 0px; opacity: 1; }
                        100% { width: 50px; height: 50px; opacity: 0; }
                    }
                `;
                document.head.appendChild(style);
            }
            let cursor = document.querySelector('.ace-virtual-cursor');
            if (!cursor) {
                cursor = document.createElement('div');
                cursor.className = 'ace-virtual-cursor';
                cursor.style.left = '0px';
                cursor.style.top = '0px';
                document.body.appendChild(cursor);
                await new Promise(r => setTimeout(r, 50));
            }
            const el = document.elementFromPoint(x, y);
            if (el) {
                el.classList.add('ace-element-highlight');
                setTimeout(() => el.classList.remove('ace-element-highlight'), 1000);
            }
            cursor.style.left = x + 'px';
            cursor.style.top = y + 'px';
            await new Promise(r => setTimeout(r, 500));
            
            if (actionType === 'click' || actionType === 'dblclick') {
                const ripple = document.createElement('div');
                ripple.className = 'ace-click-ripple';
                ripple.style.left = x + 'px';
                ripple.style.top = y + 'px';
                document.body.appendChild(ripple);
                setTimeout(() => ripple.remove(), 400);
            }
        }
        """
        
        btn = page.locator("#btn")
        box = await btn.bounding_box()
        if box:
            x = box["x"] + box["width"] / 2
            y = box["y"] + box["height"] / 2
            print(f"Target coordinates: x={x}, y={y}")
            
            # Start animation evaluate task
            anim_task = asyncio.create_task(page.evaluate(js_script, {"x": x, "y": y, "actionType": "click"}))
            
            # Wait 300ms (middle of cursor moving animation) and take screenshot
            await asyncio.sleep(0.3)
            os.makedirs("scratch", exist_ok=True)
            await page.screenshot(path="scratch/screenshot_mid.png")
            print("Captured scratch/screenshot_mid.png")
            
            # Wait for animation to finish
            await anim_task
            
            # Take screenshot after click ripple starts
            await page.screenshot(path="scratch/screenshot_end.png")
            print("Captured scratch/screenshot_end.png")
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
