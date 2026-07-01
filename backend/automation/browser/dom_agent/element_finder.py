import re
from loguru import logger
from playwright.async_api import Page, ElementHandle
from app.services.llm.llm_service import llm_service
from app.config import settings
from app.services.page_context_service import PageElement

class ElementFinderMixin:
    async def get_element_handle(self, element: PageElement) -> ElementHandle | None:
        """
        Locates the Playwright ElementHandle for a PageElement by executing
        a query in the page context.
        """
        page = self.page
        
        # 1. Try by ID first, as it's the most specific and fastest
        if element.el_id:
            # Clean up selector ID in case of invalid characters
            if re.match(r'^[a-zA-Z_][a-zA-Z0-9_\-]*$', element.el_id):
                loc = page.locator(f"#{element.el_id}").first
                if await loc.count() > 0:
                    return await loc.element_handle()

        # 2. Try using the exact placeholder
        if element.placeholder:
            loc = page.get_by_placeholder(element.placeholder, exact=True).first
            if await loc.count() > 0:
                return await loc.element_handle()

        # 3. Try using the name attribute or aria-label
        if element.name:
            # Match elements with name attribute or aria-label
            locators = [
                page.locator(f"[name='{element.name}']").first,
                page.locator(f"[aria-label='{element.name}']").first,
                page.get_by_label(element.name, exact=True).first
            ]
            for loc in locators:
                if await loc.count() > 0:
                    return await loc.element_handle()
            
            # 3b. Fuzzy label match: covers label-derived names like "Deduction Start Month"
            # that don't match any HTML `name` or `aria-label` attribute exactly.
            try:
                loc = page.get_by_label(element.name, exact=False).first
                if await loc.count() > 0:
                    return await loc.element_handle()
            except Exception:
                pass

        # 4. JS-based visual element matcher
        # Evaluates in the browser context to find the best match based on properties
        js_finder = """
        (info) => {
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
            
            // Phase 1: Try exact text and context match
            for (const el of elements) {
                const style = window.getComputedStyle(el);
                if (style.display === 'none' || style.visibility === 'hidden' || el.offsetWidth === 0) continue;
                
                if (info.el_id && el.id !== info.el_id) continue;
                if (info.placeholder && el.placeholder !== info.placeholder) continue;

                
                if (info.name) {
                    const nameAttr = el.getAttribute('name') || '';
                    const ariaLabel = el.getAttribute('aria-label') || '';
                    if (nameAttr !== info.name && ariaLabel !== info.name && getLabelText(el) !== info.name) continue;
                }
                
                let context = '';
                const row = el.closest('tr');
                if (row) {
                    context = (row.innerText || '').replace(/\\s+/g, ' ').trim().slice(0, 150);
                } else {
                    const li = el.closest('li');
                    if (li) {
                        context = (li.innerText || '').replace(/\\s+/g, ' ').trim().slice(0, 150);
                    }
                }
                if (info.context && context.toLowerCase() !== info.context.toLowerCase()) continue;
                
                if (info.text) {
                    const text = (el.innerText || el.textContent || '').trim().toLowerCase();
                    if (text !== info.text.toLowerCase()) continue;
                }
                
                return el;
            }
            
            // Phase 2: Fall back to partial text match and context match
            for (const el of elements) {
                const style = window.getComputedStyle(el);
                if (style.display === 'none' || style.visibility === 'hidden' || el.offsetWidth === 0) continue;
                
                if (info.el_id && el.id !== info.el_id) continue;
                if (info.placeholder && el.placeholder !== info.placeholder) continue;
                
                if (info.name) {
                    const nameAttr = el.getAttribute('name') || '';
                    const ariaLabel = el.getAttribute('aria-label') || '';
                    if (nameAttr !== info.name && ariaLabel !== info.name && getLabelText(el) !== info.name) continue;
                }
                
                let context = '';
                const row = el.closest('tr');
                if (row) {
                    context = (row.innerText || '').replace(/\\s+/g, ' ').trim().slice(0, 150);
                } else {
                    const li = el.closest('li');
                    if (li) {
                        context = (li.innerText || '').replace(/\\s+/g, ' ').trim().slice(0, 150);
                    }
                }
                if (info.context && context.toLowerCase() !== info.context.toLowerCase()) continue;
                
                if (info.text) {
                    const text = (el.innerText || el.textContent || '').trim().toLowerCase();
                    if (!text.includes(info.text.toLowerCase())) continue;
                }
                
                return el;
            }
            
            // Phase 3: Fall back to partial text match without context match
            for (const el of elements) {
                const style = window.getComputedStyle(el);
                if (style.display === 'none' || style.visibility === 'hidden' || el.offsetWidth === 0) continue;
                
                if (info.el_id && el.id !== info.el_id) continue;
                if (info.placeholder && el.placeholder !== info.placeholder) continue;
                
                if (info.name) {
                    const nameAttr = el.getAttribute('name') || '';
                    const ariaLabel = el.getAttribute('aria-label') || '';
                    if (nameAttr !== info.name && ariaLabel !== info.name && getLabelText(el) !== info.name) continue;
                }
                
                if (info.text) {
                    const text = (el.innerText || el.textContent || '').trim().toLowerCase();
                    if (!text.includes(info.text.toLowerCase())) continue;
                }
                
                return el;
            }
            
            return null;
        }

        """
        info_dict = {
            "tag": element.tag,
            "el_id": element.el_id,
            "placeholder": element.placeholder,
            "name": element.name,
            "text": element.text,
            "context": getattr(element, "context", "")
        }
        
        try:
            handle = await page.evaluate_handle(js_finder, info_dict)
            if handle:
                el = handle.as_element()
                if el:
                    return el
        except Exception as e:
            logger.debug(f"JS element handle finder failed: {e}")

        # 5. Last resort: standard Playwright locators by role and text
        try:
            if element.text:
                if element.role in ("button", "link", "tab", "menuitem"):
                    loc = page.get_by_role(element.role, name=element.text, exact=True).first
                    if await loc.count() > 0:
                        return await loc.element_handle()
                loc = page.get_by_text(element.text, exact=True).first
                if await loc.count() > 0:
                    return await loc.element_handle()
        except Exception:
            pass

        return None
