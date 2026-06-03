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
            const allElements = document.querySelectorAll(tags.join(', ') + ', [role="button"], [onclick]');
            
            allElements.forEach((el, index) => {
                const rect = el.getBoundingClientRect();
                // Filter out hidden elements
                if (rect.width > 0 && rect.height > 0) {
                    let text = el.innerText ? el.innerText.trim() : (el.value || el.placeholder || el.name || '');
                    if (el.tagName.toLowerCase() === 'select') {
                        const opts = Array.from(el.options).map(o => o.text).join(', ');
                        text = `Options: [${opts}]`;
                    }
                    elements.push({
                        id: index,
                        tag: el.tagName.toLowerCase(),
                        text: text,
                        type: el.type || '',
                        aria: el.getAttribute('aria-label') || ''
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
            desc = f"ID: {el['id']} | Tag: {el['tag']}"
            if el['text']: desc += f" | Text: {el['text']}"
            if el['type']: desc += f" | Type: {el['type']}"
            if el['aria']: desc += f" | Aria: {el['aria']}"
            element_lines.append(desc)
            
        element_text = "\n".join(element_lines)
        
        prompt = f"""
You are a browser automation agent. The user wants to perform an action: "{intent}"
The action type is: {action_type}

Here are the interactive elements on the current webpage:
{element_text}

Analyze the user's intent and select the single most appropriate Element ID to interact with.
Reply ONLY with the integer ID. If no element matches, reply with 'NONE'.
"""
        logger.info("Querying LLM for correct element ID...")
        try:
            response = await llm_service.generate_response(prompt)
            response = response.strip()
            if response == "NONE":
                return None
            return int(response)
        except Exception as e:
            logger.error(f"DOM Agent LLM Error: {e}")
            return None

    async def execute_intent(self, intent: str) -> str:
        """Determines action type, finds the element, and executes it."""
        intent_lower = intent.lower()
        if "highlight" in intent_lower and "all" not in intent_lower:
            return await self.highlight_specific_element(intent)
            
        action_type = "type" if "type" in intent_lower or "fill" in intent_lower or "enter" in intent_lower else "click"
        if "select" in intent_lower: action_type = "select"
        if "check" in intent_lower: action_type = "check"
        
        element_id = await self.find_element_for_intent(intent, action_type)
        
        if element_id is None:
            return f"I couldn't find the correct element for: {intent}"
            
        try:
            selector = f"[data-ace-id='{element_id}']"
            
            if action_type == "click":
                await self.page.click(selector, timeout=3000)
                return f"Clicked the requested element."
            elif action_type == "check":
                if "uncheck" in intent_lower:
                    await self.page.uncheck(selector, timeout=3000)
                    return "Unchecked the requested element."
                else:
                    await self.page.check(selector, timeout=3000)
                    return "Checked the requested element."
            elif action_type == "select":
                extract_prompt = f"Extract exactly the option text or value the user wants to select from this intent: '{intent}'. Reply ONLY with the text."
                option_to_select = await llm_service.generate_response(extract_prompt)
                await self.page.select_option(selector, label=option_to_select.strip())
                return f"Selected '{option_to_select}'."
            else:
                extract_prompt = f"Extract exactly the text the user wants to type from this intent: '{intent}'. Reply ONLY with the text."
                text_to_type = await llm_service.generate_response(extract_prompt)
                await self.page.fill(selector, text_to_type.strip())
                return f"Typed '{text_to_type}' into the element."
                
        except Exception as e:
            logger.error(f"Failed to execute DOM interaction: {e}")
            return f"Failed to interact with the element."

    async def highlight_specific_element(self, intent: str) -> str:
        element_id = await self.find_element_for_intent(intent, "highlight")
        if element_id is None:
            return "Could not find element to highlight."
        
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
            
        desc = "\n".join([f"ID: {el['id']} | Type: {el['type']} | Label: {el['text']} | Aria: {el['aria']}" for el in inputs])
        prompt = f"""
You are a form filling agent. The user provided this context: "{context}"
Here are the available form fields on the page:
{desc}
Based on the context, map the form fields to the appropriate values.
Reply strictly in JSON format where keys are the integer IDs and values are the text to type or select. Example: {{"1": "John", "3": "USA"}}
"""
        import json
        try:
            response = await llm_service.generate_response(prompt)
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
