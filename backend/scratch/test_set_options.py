import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        # Set up mock HTML settings page
        html_content = """
        <html>
        <body>
            <div>
                <h3>Notification Methods</h3>
                <label><input type="checkbox" id="push" checked /> Push Notifications</label>
                <label><input type="checkbox" id="email" /> Email Notifications</label>
                <label><input type="checkbox" id="sms" /> SMS Notifications</label>
            </div>
        </body>
        </html>
        """
        await page.set_content(html_content)

        # JS code from handle_set_options
        js_code = """
            (payload) => {
                const groupText = payload.group;
                const parts = payload.parts;
                const rawValues = payload.rawValues;

                const headerSels = ['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'span', 'div', 'label', 'strong', 'b'];
                const headers = Array.from(document.querySelectorAll(headerSels.join(',')));
                
                let bestGroupEl = null;
                let bestGroupScore = 0;
                
                for (const h of headers) {
                    const txt = (h.innerText || h.textContent || '').toLowerCase().replace(/\\s+/g, ' ').trim();
                    if (!txt) continue;
                    
                    if (txt.includes(groupText)) {
                        let score = 10;
                        if (txt === groupText) score += 20;
                        if (h.tagName.startsWith('H')) score += 5;
                        
                        if (score > bestGroupScore) {
                            bestGroupScore = score;
                            bestGroupEl = h;
                        }
                    }
                }

                let container = document.body;
                if (bestGroupEl && bestGroupScore >= 10) {
                    let parent = bestGroupEl.parentElement;
                    for (let depth = 0; depth < 5; depth++) {
                        if (!parent) break;
                        const inputs = parent.querySelectorAll('input[type="checkbox"], input[type="radio"], [role="checkbox"], [role="radio"]');
                        if (inputs.length >= 1) {
                            container = parent;
                            break;
                        }
                        parent = parent.parentElement;
                    }
                }

                const optionSels = [
                    'input[type="checkbox"]',
                    'input[type="radio"]',
                    '[role="checkbox"]',
                    '[role="radio"]',
                    '[role="switch"]'
                ];
                const toggles = Array.from(container.querySelectorAll(optionSels.join(',')));
                if (toggles.length === 0 && container !== document.body) {
                    toggles.push(...Array.from(document.body.querySelectorAll(optionSels.join(','))));
                }

                function getLabelText(t) {
                    if (t.tagName === 'INPUT') {
                        if (t.id) {
                            const lbl = document.querySelector(`label[for="${t.id}"]`);
                            if (lbl && lbl.innerText) return lbl.innerText;
                        }
                        let parent = t.parentElement;
                        while (parent) {
                            if (parent.tagName === 'LABEL') {
                                return parent.innerText;
                            }
                            parent = parent.parentElement;
                        }
                    }
                    return t.innerText || t.getAttribute('aria-label') || t.placeholder || '';
                }

                let clickedCount = 0;
                const clickedLabels = [];

                for (const t of toggles) {
                    const label = getLabelText(t).toLowerCase().replace(/\\s+/g, ' ').trim();
                    if (!label) continue;

                    let matches = false;
                    for (const p of parts) {
                        if (label.includes(p) || p.includes(label)) {
                            matches = true;
                            break;
                        }
                    }
                    if (!matches && rawValues.includes(label)) {
                        matches = true;
                    }

                    if (matches) {
                        const isChecked = t.checked || t.getAttribute('aria-checked') === 'true' || t.classList.contains('checked');
                        if (!isChecked) {
                            t.click();
                            clickedCount++;
                            clickedLabels.push(label);
                        } else {
                            clickedCount++;
                            clickedLabels.push(label);
                        }
                    }
                }

                if (clickedCount > 0) {
                    return { status: 'success', labels: clickedLabels };
                }
                return { status: 'not_found' };
            }
        """

        # Run evaluation simulating "Notification Methods are Email Notifications SMS Notifications"
        payload = {
            "group": "notification methods",
            "parts": ["email notifications", "sms notifications"],
            "rawValues": "email notifications sms notifications"
        }
        res = await page.evaluate(js_code, payload)
        print("Mock execution result:", res)
        print("Push checked:", await page.locator("#push").is_checked())
        print("Email checked:", await page.locator("#email").is_checked())
        print("SMS checked:", await page.locator("#sms").is_checked())

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
