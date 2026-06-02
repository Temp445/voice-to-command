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
                    elements.push({
                        id: index,
                        tag: el.tagName.toLowerCase(),
                        text: el.innerText ? el.innerText.trim() : (el.value || el.placeholder || el.name || ''),
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
        action_type = "type" if "type" in intent_lower or "fill" in intent_lower or "enter" in intent_lower else "click"
        
        element_id = await self.find_element_for_intent(intent, action_type)
        
        if element_id is None:
            return f"I couldn't find the correct element for: {intent}"
            
        try:
            selector = f"[data-ace-id='{element_id}']"
            
            if action_type == "click":
                await self.page.click(selector, timeout=3000)
                return f"Clicked the requested element."
            else:
                # For typing, we need to extract the text to type from the intent
                # This requires another quick LLM call or regex, but for simplicity we ask LLM
                extract_prompt = f"Extract exactly the text the user wants to type from this intent: '{intent}'. Reply ONLY with the text."
                text_to_type = await llm_service.generate_response(extract_prompt)
                await self.page.fill(selector, text_to_type.strip())
                return f"Typed '{text_to_type}' into the element."
                
        except Exception as e:
            logger.error(f"Failed to execute DOM interaction: {e}")
            return f"Failed to interact with the element."
