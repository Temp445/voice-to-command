import asyncio
import sys
import os

# Ensure root is in sys.path
from pathlib import Path
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.append(str(_ROOT))

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

async def main():
    from automation.browser.browser_engine import BrowserEngine
    try:
        engine = BrowserEngine()
        page = await engine.get_active_page()
        if not page:
            print("Failed to get active page.", flush=True)
            return
        print(f"Connected to page: {page.url}", flush=True)
        
        js_finder = """
        (info) => {
            try {
                const labelsMap = {};
                const labels = document.querySelectorAll('label[for]');
                for (const label of labels) {
                    const htmlFor = label.getAttribute('for');
                    if (htmlFor) {
                        labelsMap[htmlFor] = label.innerText || label.textContent || '';
                    }
                }

                const getLabelText = (el) => {
                    const tag = el.tagName.toUpperCase();
                    if (tag !== 'INPUT' && tag !== 'SELECT' && tag !== 'TEXTAREA' && el.getAttribute('role') !== 'combobox') {
                        return '';
                    }
                    let labelText = '';
                    if (el.labels && el.labels.length > 0) {
                        labelText = Array.from(el.labels).map(l => l.innerText || l.textContent || '').join(' ');
                    } else if (el.id && labelsMap[el.id]) {
                        labelText = labelsMap[el.id];
                    }
                    if (!labelText.trim()) {
                        const parentLabel = el.closest('label');
                        if (parentLabel) {
                            labelText = parentLabel.innerText || parentLabel.textContent || '';
                        }
                    }
                    if (!labelText.trim()) {
                        let prev = el.previousElementSibling;
                        while (prev) {
                            const prevText = (prev.innerText || prev.textContent || '').trim();
                            if (prevText && prevText.length < 100) {
                                labelText = prevText;
                                break;
                            }
                            prev = prev.previousElementSibling;
                        }
                    }
                    if (!labelText.trim()) {
                        const parent = el.parentElement;
                        if (parent) {
                            const parentText = (parent.innerText || parent.textContent || '').trim();
                            if (parentText && parentText.length < 100) {
                                labelText = parentText;
                            }
                        }
                    }
                    return labelText.replace(/\\s+/g, ' ').trim();
                };

                const selector = info.tag || '*';
                const elements = Array.from(document.querySelectorAll(selector));
                console.log("Elements count: " + elements.length);
                return elements.length;
            } catch (e) {
                return "ERROR: " + e.message + "\\n" + e.stack;
            }
        }
        """
        
        print("Evaluating js_finder...", flush=True)
        res = await page.evaluate(js_finder, {"tag": "input"})
        print(f"Result: {res}", flush=True)
        
    except Exception as e:
        print(f"Exception: {e}", flush=True)

if __name__ == "__main__":
    asyncio.run(main())
