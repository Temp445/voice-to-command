import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        # Set up a mock HTML page replicating the settings screen
        html_content = """
        <html>
        <body>
            <div id="settings-group">
                <h3>Default Reminder Preferences</h3>
                
                <div>
                    <span>Notification Methods</span>
                    <label><input type="checkbox" id="push" /> Push Notifications</label>
                    <label><input type="checkbox" id="email" /> Email Notifications</label>
                    <label><input type="checkbox" id="sms" /> SMS Notifications</label>
                </div>

                <div>
                    <span>Sound Alerts</span>
                    <label><input type="checkbox" id="sound" /> Enable sound alerts for notifications</label>
                </div>

                <div>
                    <span>Priority Level</span>
                    <label><input type="radio" name="priority" id="urgent" /> Urgent</label>
                    <label><input type="radio" name="priority" id="normal" checked /> Normal</label>
                    <label><input type="radio" name="priority" id="low" /> Low</label>
                </div>
            </div>
        </body>
        </html>
        """
        await page.set_content(html_content)

        # The JS logic from handle_toggle_element
        js_code = """
            (target) => {
                const toggleSels = [
                    'input[type="checkbox"]',
                    'input[type="radio"]',
                    '[role="checkbox"]',
                    '[role="radio"]',
                    '[role="switch"]',
                    'button[class*="toggle" i]',
                    'button[class*="switch" i]',
                    'label[class*="toggle" i]',
                    'div[class*="toggle" i]',
                    'span[class*="toggle" i]',
                ];
                const allToggles = Array.from(document.querySelectorAll(toggleSels.join(',')));

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

                const targetClean = target.toLowerCase().replace(/\\s+/g, ' ').trim();
                const targetWords = targetClean.split(/\\s+/).filter(Boolean);

                let bestToggle = null;
                let bestScore = -1;

                for (const t of allToggles) {
                    const label = getLabelText(t).toLowerCase().replace(/\\s+/g, ' ').trim();
                    if (!label && t.tagName !== 'INPUT') continue;

                    const labelWords = label.split(/\\s+/).filter(Boolean);

                    // 1. Calculate label match score
                    let labelScore = 0;
                    if (label) {
                        for (const w of labelWords) {
                            if (targetWords.includes(w)) {
                                labelScore += 10;
                            }
                        }
                        if (targetClean.includes(label) || label.includes(targetClean)) {
                            labelScore += 20;
                        }
                    }

                    // 2. Calculate container/context match score
                    let containerText = '';
                    let parent = t.parentElement;
                    for (let depth = 0; depth < 8; depth++) {
                        if (!parent) break;
                        containerText += ' ' + (parent.innerText || '');
                        parent = parent.parentElement;
                    }
                    containerText = containerText.toLowerCase().replace(/\\s+/g, ' ');

                    let containerScore = 0;
                    for (const w of targetWords) {
                        if (containerText.includes(w)) {
                            containerScore += 2;
                        }
                    }

                    const totalScore = labelScore + containerScore;
                    if (totalScore > bestScore) {
                        bestScore = totalScore;
                        bestToggle = t;
                    }
                }

                if (bestToggle && bestScore >= 5) {
                    bestToggle.click();
                    return { id: bestToggle.id, score: bestScore };
                }
                return { id: null, score: bestScore };
            }
        """

        # Test case 1: "Priority Level urgent"
        res1 = await page.evaluate(js_code, "Priority Level urgent")
        is_urgent_checked = await page.locator("#urgent").is_checked()
        print(f"Test 'Priority Level urgent': Result={res1}, UrgentChecked={is_urgent_checked}")

        # Test case 2: "email notifications"
        res2 = await page.evaluate(js_code, "email notifications")
        is_email_checked = await page.locator("#email").is_checked()
        print(f"Test 'email notifications': Result={res2}, EmailChecked={is_email_checked}")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
