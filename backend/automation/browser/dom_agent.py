"""
Dynamic DOM Agent
Extracts actionable elements from a Playwright page and queries an LLM
to find the correct element for a user's intent.
"""

from loguru import logger
from playwright.async_api import Page
from app.services.llm.llm_service import llm_service

class DOMAgent:
    def __init__(self, page: Page):
        self.page = page

    async def get_interactive_elements(self):
        """Extracts all clickable and typable elements with bounding boxes."""
        script = """
        () => {
            const elements = [];
            const tags = ['a', 'button', 'input', 'textarea', 'select'];
            const allElements = document.querySelectorAll(tags.join(', ') + ', [role="button"], [role="combobox"], [onclick]');
            
            allElements.forEach((el, index) => {
                const rect = el.getBoundingClientRect();
                // Filter out hidden elements AND elements outside the active viewport
                const inViewport = rect.top >= 0 && rect.bottom <= (window.innerHeight || document.documentElement.clientHeight);
                if (rect.width > 0 && rect.height > 0 && inViewport) {
                    let text = el.innerText ? el.innerText.trim() : (el.value || el.placeholder || el.name || '');
                    if (el.tagName.toLowerCase() === 'select') {
                        const opts = Array.from(el.options).map(o => o.text).join(', ');
                        text = `Options: [${opts}]`;
                    }
                    
                    // Get text of parent for better context (helps distinguish form labels from table rows)
                    let parentText = '';
                    if (el.parentElement && el.parentElement.innerText) {
                        parentText = el.parentElement.innerText.replace(/\\n/g, ' ').substring(0, 60).trim();
                    }

                    elements.push({
                        id: index,
                        tag: el.tagName.toLowerCase(),
                        text: text,
                        type: el.type || '',
                        aria: el.getAttribute('aria-label') || '',
                        y: Math.round(rect.y),
                        context: parentText
                    });
                    // Tag the element in the DOM so we can click it later
                    el.setAttribute('data-ace-id', index);
                }
            });
            return elements;
        }
        """
        return await self.page.evaluate(script)

    async def find_element_for_intent(self, intent: str, action_type: str = "click"):
        """
        Asks the LLM to identify which element ID corresponds to the user's intent.
        action_type can be 'click' or 'type'.
        """
        logger.info(f"Extracting DOM elements to evaluate intent: '{intent}'")
        elements = await self.get_interactive_elements()
        
        if not elements:
            return None

        # Prepare a condensed list for the LLM
        element_lines = []
        for el in elements:
            if not el['text'] and not el['aria'] and not el['context']:
                continue
            
            # Format: [ID] tag 'text' (type) [context] - minimal format to save tokens
            desc = f"[{el['id']}] {el['tag']}"
            if el['text']: desc += f" '{el['text'][:40]}'"
            elif el['aria']: desc += f" aria:'{el['aria'][:40]}'"
            
            if el['context'] and el['context'] != el['text']:
                desc += f" ctx:'{el['context'][:40]}'"
            
            if el['type'] and el['type'] not in ['text', 'submit', 'button']:
                desc += f" type:{el['type']}"
                
            element_lines.append(desc)
            
        if len(element_lines) > 50:
            logger.warning(f"DOM has {len(element_lines)} interactive elements. Truncating to 50 to prevent TPM errors.")
            element_lines = element_lines[:50]
            
        element_text = "\n".join(element_lines)
        
        prompt = f"""
You are a browser automation agent. The user wants to perform an action: "{intent}"
The action type is: {action_type}

Note: The user may be interacting with the Acesoftcloud CRM. Keep CRM terminology (Leads, Opportunities, Tickets, Invoices, Follow-ups) in mind when selecting elements.
IMPORTANT: The user might refer to elements that do not have explicit text labels (e.g., "start date" or "end date" might just be calendar icons with type="date" next to each other). Use the 'type' attribute and the element's position (smaller Y coordinate = higher up, adjacent elements = date ranges) to infer their purpose.

Here are the interactive elements on the current webpage:
{element_text}

Analyze the user's intent and select the single most appropriate Element ID to interact with. 
ONLY return multiple IDs if the user's intent explicitly requires interacting with multiple elements simultaneously (like filling a date range that has two inputs). Otherwise, return exactly ONE Element ID.
Reply ONLY with a comma-separated list of integer IDs (e.g., '45' or '26, 27'). If no element matches, reply with 'NONE'.
"""
        tokens = len(prompt) // 4
        logger.info(f"DOM Agent queried LLM for element ID. Approx Payload: {tokens} tokens ({len(prompt)} chars)")
        try:
            response = await llm_service.chat(prompt)
            response = response.strip()
            if response == "NONE" or not response:
                return []
            
            import re
            ids = [int(x) for x in re.findall(r'\d+', response)]
            return ids
        except Exception as e:
            logger.error(f"DOM Agent LLM Error: {e}")
            return None

    async def execute_intent(self, intent: str) -> str:
        """Determines action type, finds the element, and executes it."""
        intent_lower = intent.lower()
        if "highlight" in intent_lower and "all" not in intent_lower:
            return await self.highlight_specific_element(intent)
            
        import re
        # Default: click
        action_type = "click"
        
        # Explicit type keywords
        if re.search(r'\b(type|fill|enter|write|put|set|input)\b', intent_lower):
            action_type = "type"
        elif re.search(r'\b(select|choose|pick)\b', intent_lower):
            action_type = "select"
        elif re.search(r'\b(check|uncheck|tick)\b', intent_lower):
            action_type = "check"
        else:
            # Smart detection: "field_name value" pattern (e.g. "company name demo45")
            # If command has NO action verb but looks like "<label> <value>", treat as type
            # Heuristic: if the last "word" looks like a value (alphanumeric, a date, a number)
            # and does not match any known button label, infer it's a fill action
            words = intent_lower.split()
            if len(words) >= 2:
                last_word = words[-1]
                # If last word looks like a value (contains digit, or is a short code), treat as type
                if re.search(r'\d', last_word) or re.match(r'^[a-z]{2,10}\d+$', last_word):
                    action_type = "type"

        element_ids = await self.find_element_for_intent(intent, action_type)
        
        if not element_ids:
            return f"I couldn't find the correct element for: {intent}"
            
        results = []
        for i, element_id in enumerate(element_ids):
            try:
                selector = f"[data-ace-id='{element_id}']"
                
                if action_type == "click":
                    await self.page.click(selector, timeout=3000)
                    results.append("Clicked the requested element.")
                elif action_type == "check":
                    if "uncheck" in intent_lower:
                        await self.page.uncheck(selector, timeout=3000)
                        results.append("Unchecked the requested element.")
                    else:
                        await self.page.check(selector, timeout=3000)
                        results.append("Checked the requested element.")
                elif action_type == "select":
                    extract_prompt = f"Extract exactly the option text or value the user wants to select from this intent: '{intent}'. Reply ONLY with the text."
                    option_to_select = await llm_service.chat(extract_prompt)
                    await self.page.select_option(selector, label=option_to_select.strip())
                    results.append(f"Selected '{option_to_select}'.")
                else:
                    # Check if it's a date input to enforce YYYY-MM-DD format
                    is_date = False
                    is_fillable = True
                    try:
                        el_info = await self.page.evaluate(f"""
                            (() => {{
                                const el = document.querySelector('[data-ace-id="{element_id}"]');
                                return {{
                                    type: el.type,
                                    tag: el.tagName.toLowerCase(),
                                    isContentEditable: el.isContentEditable
                                }};
                            }})()
                        """)
                        is_date = (el_info['type'] == "date")
                        if el_info['tag'] in ["button", "a"] and not el_info['isContentEditable']:
                            is_fillable = False
                    except Exception:
                        pass
                        
                    if not is_fillable:
                        logger.info(f"Element {element_id} is a button/link but action was 'type'. Converting to 'click'.")
                        await self.page.click(selector, timeout=3000)
                        results.append(f"Clicked element {element_id} instead of typing.")
                        continue

                    if is_date:
                        date_target = "first (start) date" if i == 0 else "second (end) date" if i == 1 else "date"
                        extract_prompt = f"Extract exactly the {date_target} the user wants to type into the field from this intent: '{intent}'. Format it strictly as YYYY-MM-DD (e.g., 2026-04-10). Reply ONLY with the formatted date."
                    else:
                        extract_prompt = f"Extract exactly the text the user wants to type from this intent: '{intent}'. If the intent contains multiple values for multiple fields, extract the {'first' if i == 0 else 'second' if i == 1 else 'appropriate'} value. Reply ONLY with the text."
                    
                    tokens = len(extract_prompt) // 4
                    logger.info(f"DOM Agent queried LLM for text extraction. Approx Payload: {tokens} tokens")
                    text_to_type = await llm_service.chat(extract_prompt)
                    text_to_type = text_to_type.strip()
                    try:
                        await self.page.fill(selector, text_to_type, timeout=3000)
                    except Exception as e:
                        logger.warning(f"Native fill failed, falling back to click & type: {e}")
                        await self.page.click(selector, timeout=2000)
                        await self.page.keyboard.insert_text(text_to_type)
                    results.append(f"Typed '{text_to_type}' into the element.")
                    
            except Exception as e:
                logger.error(f"Failed to execute {action_type} on element {element_id}: {e}")
                results.append(f"Action failed for element {element_id}: {e}")
                
        return " and ".join(results)

    async def highlight_specific_element(self, intent: str) -> str:
        element_ids = await self.find_element_for_intent(intent, "highlight")
        if not element_ids:
            return "Could not find element to highlight."
        
        element_id = element_ids[0]
        script = f"""
        () => {{
            const el = document.querySelector("[data-ace-id='{element_id}']");
            if(el) {{
                el.style.border = '3px solid red';
                el.style.boxShadow = '0 0 10px red';
            }}
        }}
        """
        await self.page.evaluate(script)
        return f"Highlighted element {element_id}."

    async def fill_form(self, context: str) -> str:
        elements = await self.get_interactive_elements()
        inputs = [el for el in elements if el['tag'] in ['input', 'textarea', 'select']]
        if not inputs:
            return "No form fields found."
            
        if len(inputs) > 100:
            logger.warning(f"Truncating {len(inputs)} form fields to 100 to prevent TPM errors.")
            inputs = inputs[:100]
            
        desc = "\n".join([f"[{el['id']}] {el['tag']} '{el['text']}'" for el in inputs])
        prompt = f"""
You are a form filling agent. The user provided this context: "{context}"

Note: The user may be interacting with the Acesoftcloud CRM. Map values logically for CRM fields (e.g. Lead details, Opportunity stages, etc).

Here are the available form fields on the page:
{desc}
Based on the context, map the form fields to the appropriate values.
Reply strictly in JSON format where keys are the integer IDs and values are the text to type or select. Example: {{"1": "John", "3": "USA"}}
"""
        import json
        tokens = len(prompt) // 4
        logger.info(f"DOM Agent queried LLM for form fill mapping. Approx Payload: {tokens} tokens ({len(prompt)} chars)")
        try:
            response = await llm_service.chat(prompt)
            # Find the JSON block
            import re
            json_str = re.search(r'\{.*\}', response, re.DOTALL)
            if json_str:
                mapping = json.loads(json_str.group())
                for eid_str, value in mapping.items():
                    try:
                        selector = f"[data-ace-id='{eid_str}']"
                        el_type = next((el['tag'] for el in inputs if str(el['id']) == eid_str), 'input')
                        if el_type == 'select':
                            await self.page.select_option(selector, label=str(value))
                        else:
                            await self.page.fill(selector, str(value))
                    except Exception as e:
                        logger.warning(f"Failed to fill field {eid_str}: {e}")
                return "Filled the form."
            return "Failed to generate form mapping."
        except Exception as e:
            logger.error(f"Form fill error: {e}")
            return "Form fill failed."

    async def extract_headings(self) -> str:
        script = "() => Array.from(document.querySelectorAll('h1, h2, h3')).map(h => h.tagName + ': ' + h.innerText.trim()).filter(t => t.length > 4).join('\\n')"
        res = await self.page.evaluate(script)
        return res if res else "No headings found."

    async def extract_first_paragraph(self) -> str:
        script = "() => { const p = document.querySelector('p'); return p ? p.innerText.trim() : ''; }"
        res = await self.page.evaluate(script)
        return res if res else "No paragraphs found."
