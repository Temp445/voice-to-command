import re
import asyncio
from loguru import logger
from playwright.async_api import Page
from app.services.llm.llm_service import llm_service
from app.config import settings
from app.services.page_context_service import page_context_service, find_best_element, PageElement

class ActionExecutorMixin:
    async def execute_intent(self, intent_text: str) -> str:
        """
        Main entry point for executing an intent on the DOM.
        """
        logger.info(f"DOMAgent executing intent: '{intent_text}'")
        
        # 1. Fetch current snapshot
        page_context_service.invalidate()
        snapshot = await page_context_service.get_snapshot()
        if not snapshot or not snapshot.elements:
            return "Failed to get interactive elements from page."

        # 2. Try LLM-based execution if enabled and ready
        if llm_service.is_ready:
            res = await self.execute_intent_with_llm(intent_text, snapshot.elements)
            if res:
                return res

        # 3. Fallback to deterministic local execution
        return await self.execute_intent_deterministically(intent_text, snapshot)

    async def execute_intent_with_llm(self, command: str, elements: list[PageElement]) -> str | None:
        try:
            # Build interactive elements list
            elements_desc = []
            for i, el in enumerate(elements):
                desc = f"[{i}] tag={el.tag}, role={el.role}"
                if el.text: desc += f", text='{el.text}'"
                if el.name: desc += f", name='{el.name}'"
                if el.placeholder: desc += f", placeholder='{el.placeholder}'"
                if el.el_id: desc += f", id='{el.el_id}'"
                elements_desc.append(desc)
                
            elements_str = "\n".join(elements_desc)
            
            system_prompt = (
                "You are an AI assistant controlling a web browser. Your job is to select the correct elements to interact with based on the user's command.\n"
                "Available elements on the page:\n"
                f"{elements_str}\n\n"
                "Generate the actions to perform to fulfill the command. Respond with ONLY a JSON object of this structure:\n"
                "{\n"
                "  \"actions\": [\n"
                "    { \"action\": \"click\", \"index\": 5 },\n"
                "    { \"action\": \"fill\", \"index\": 10, \"value\": \"some text\" },\n"
                "    { \"action\": \"select\", \"index\": 12, \"value\": \"option_value\" },\n"
                "    { \"action\": \"wait\", \"timeout_ms\": 500 }\n"
                "  ]\n"
                "}\n"
                "Respond with valid JSON only. Do not include markdown code block syntax or any other preamble/explanation."
            )
            
            msgs = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"User command: '{command}'"}
            ]
            
            raw = await asyncio.wait_for(
                llm_service._provider.chat(msgs, temperature=0.0),
                timeout=5.0
            )
            
            # Clean response
            raw = raw.strip()
            if raw.startswith("```json"):
                raw = raw[7:]
            if raw.endswith("```"):
                raw = raw[:-3]
            raw = raw.strip()
            
            import json
            data = json.loads(raw)
            actions = data.get("actions", [])
            if not actions:
                return None
                
            results = []
            for act in actions:
                action_type = act.get("action")
                if action_type == "wait":
                    ms = act.get("timeout_ms", 100)
                    await asyncio.sleep(ms / 1000.0)
                    continue
                    
                idx = act.get("index")
                if idx is None or idx < 0 or idx >= len(elements):
                    continue
                    
                el = elements[idx]
                handle = await self.get_element_handle(el)
                if not handle:
                    continue
                    
                if action_type == "click":
                    await handle.click()
                    results.append(f"Clicked element {idx}")
                elif action_type == "fill":
                    val = act.get("value", "")
                    await handle.click()
                    await handle.fill(val)
                    results.append(f"Filled element {idx} with '{val}'")
                elif action_type == "select":
                    await handle.click()
                    await asyncio.sleep(0.5)
                    val = act.get("value", "")
                    loc = self.page.get_by_role("option", name=re.compile(val, re.IGNORECASE)).first
                    if await loc.count() > 0:
                        await loc.click()
                        results.append(f"Selected option '{val}'")
                    else:
                        await self.page.keyboard.type(val)
                        await self.page.keyboard.press("Enter")
                        results.append(f"Typed option '{val}'")
                        
            return " & ".join(results) if results else "No actions performed."
        except Exception as e:
            logger.warning(f"DOMAgent LLM action execution failed, falling back: {e}")
            return None

    async def execute_intent_deterministically(self, intent_text: str, snapshot) -> str:
        cmd = intent_text.lower().strip()
        
        dropdown = None
        option = None
        value = None
        target = None
        
        # 1. Check Change / Select option pattern (e.g. "change the view mode chart", "report type is lead tracking")
        m = re.search(r'^(?:change|set|switch|toggle|select)\s+(?:the\s+)?(.+?)\s+(?:to\s+)?(chart|list|kanban|grid|table|board|view|mode|\w+)$', cmd)
        if m:
            dropdown = m.group(1).strip()
            option = m.group(2).strip()
        else:
            m = re.search(r'^select\s+(.+?)\s+(?:from|in)\s+(?:the\s+)?(.+)$', cmd)
            if m:
                dropdown = m.group(2).strip()
                option = m.group(1).strip()
            else:
                m = re.search(r'^(.+?)\s+(?:is|to|set\s+to)\s+(.+)$', cmd)
                if m:
                    dropdown = m.group(1).strip()
                    option = m.group(2).strip()

        if dropdown and option:
            # Find select/combobox/button/input element
            candidates = [el for el in snapshot.elements if el.role in ("button", "select", "combobox", "input") or el.tag in ("select", "button", "input")]
            dropdown_el = find_best_element(candidates, dropdown, min_score=40, roles=None)
            
            if dropdown_el:
                handle = await self.get_element_handle(dropdown_el)
                if handle:
                    await handle.click()
                    await asyncio.sleep(0.5)
                    
                    # Invalidate context and fetch fresh snapshot
                    page_context_service.invalidate()
                    fresh_snapshot = await page_context_service.get_snapshot()
                    if fresh_snapshot:
                        option_candidates = [el for el in fresh_snapshot.elements if el.role in ("option", "button", "link", "listitem") or el.tag in ("option", "li")]
                        option_el = find_best_element(option_candidates, option, min_score=40, roles=None)
                        if option_el:
                            opt_handle = await self.get_element_handle(option_el)
                            if opt_handle:
                                await opt_handle.click()
                                return f"Selected option '{option}' from '{dropdown}'."
                    
                    # Direct click fallback
                    try:
                        loc = self.page.get_by_role("option", name=re.compile(option, re.IGNORECASE)).first
                        if await loc.count() > 0:
                            await loc.click()
                            return f"Selected option '{option}' from '{dropdown}'."
                        loc = self.page.locator(f"li:has-text('{option}')").first
                        if await loc.count() > 0:
                            await loc.click()
                            return f"Selected option '{option}' from '{dropdown}'."
                    except Exception:
                        pass
            
            # Direct clickable option fallback (segmented control / tabs / tab buttons)
            clickable_candidates = snapshot.clickable()
            direct_el = find_best_element(clickable_candidates, option, min_score=50)
            if direct_el:
                direct_handle = await self.get_element_handle(direct_el)
                if direct_handle:
                    await direct_handle.click()
                    return f"Clicked '{option}' directly."

        # 2. Check type/fill/write target pattern (e.g. "type text into field")
        m = re.match(r'^(?:type|write|enter|fill)\s+(.+?)\s+(?:into|in|to)\s+(?:the\s+)?(.+)$', cmd)
        if m:
            value = m.group(1).strip()
            target = m.group(2).strip()
            el = find_best_element(snapshot.inputs(), target, min_score=40, roles=None)
            if el:
                handle = await self.get_element_handle(el)
                if handle:
                    await handle.click()
                    await handle.fill(value)
                    return f"Typed '{value}' into '{target}'."

        # 3. Check click target pattern (e.g. "click submit")
        m = re.match(r'^(?:click|tap|press|hit)\s+(?:on\s+)?(?:the\s+)?(.+)$', cmd)
        if m:
            target = m.group(1).strip()
            el = find_best_element(snapshot.clickable(), target, min_score=40)
            if el:
                handle = await self.get_element_handle(el)
                if handle:
                    await handle.click()
                    return f"Clicked '{target}'."

        # 4. Check bare type pattern (e.g. "type hello")
        m = re.match(r'^(?:type|write|enter)\s+(.+)$', cmd)
        if m:
            value = m.group(1).strip()
            await self.page.keyboard.type(value)
            return f"Typed '{value}' into focused element."

        return f"Could not determine DOM action to execute for command: '{intent_text}'."
