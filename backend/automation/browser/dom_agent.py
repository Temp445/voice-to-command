"""
Dynamic DOM Agent
Extracts actionable elements from a Playwright page and queries an LLM
to find the correct element for a user's intent.
"""

from loguru import logger
from playwright.async_api import Page
from app.services.llm.llm_service import llm_service
from app.config import settings

class DOMAgent:
    def __init__(self, page: Page):
        self.page = page

    async def get_interactive_elements(self):
        """Extracts all clickable and typable elements with bounding boxes."""
        script = """
        () => {
            const elements = [];
            const interactiveSelectors = [
                'a', 'button', 'input', 'textarea', 'select', 'summary', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'label', 'li', 'tr', 'td',
                'svg', 'img', '[role="button"]', '[role="combobox"]', '[role="menuitem"]', '[role="tab"]', '[onclick]', '[aria-expanded]', '[data-toggle]',
                '[class*="btn"]', '[class*="button"]', '[class*="accordion"]', '[class*="header"]', '[class*="title"]', '[class*="menu"]', 
                '[class*="item"]', '[class*="link"]', '[class*="dropdown"]', '[class*="cursor-pointer"]', '[class*="tab"]',
                '[class*="avatar"]', '[class*="profile"]', '[class*="user"]'
            ].join(', ');
            
            const allNodes = Array.from(document.querySelectorAll('*'));
            const allElements = allNodes.filter(el => {
                if (el.matches(interactiveSelectors)) return true;
                // Capture leaf nodes with text (e.g., poorly structured divs/spans)
                if (el.innerText && el.innerText.trim().length > 0 && Array.from(el.children).every(c => c.tagName.toLowerCase() === 'br' || c.tagName.toLowerCase() === 'span')) {
                    return true;
                }
                return false;
            });
            
            allElements.forEach((el, index) => {
                const rect = el.getBoundingClientRect();
                // Filter out hidden elements AND elements outside the active viewport (allowing partially visible elements)
                const inViewport = rect.bottom >= 0 && rect.top <= (window.innerHeight || document.documentElement.clientHeight);
                const isFileInput = el.tagName.toLowerCase() === 'input' && el.type === 'file';
                if ((rect.width > 0 && rect.height > 0 && inViewport) || isFileInput) {
                    let text = el.innerText ? el.innerText.trim() : (el.value || el.placeholder || el.name || '');
                    if (el.tagName.toLowerCase() === 'select') {
                        const opts = Array.from(el.options).map(o => o.text).join(', ');
                        text = `Options: [${opts}]`;
                    }
                    
                    // Get text of parent for better context (helps distinguish form labels from table rows)
                    let parentText = '';
                    let parent = el.parentElement;
                    let levels = 0;
                    while (parent && levels < 3) {
                        const tag = parent.tagName.toLowerCase();
                        if (['tr', 'fieldset', 'li'].includes(tag) || (tag === 'div' && parent.innerText.length > 20)) {
                            if (parent.innerText) {
                                parentText = parent.innerText.replace(/\\n/g, ' ').substring(0, 120).trim();
                                break;
                            }
                        }
                        parent = parent.parentElement;
                        levels++;
                    }
                    if (!parentText && el.parentElement && el.parentElement.innerText) {
                        parentText = el.parentElement.innerText.replace(/\\n/g, ' ').substring(0, 60).trim();
                    }

                    // Try to get aria-label, title, or testid
                    let aria = el.getAttribute('aria-label') || el.getAttribute('title') || el.getAttribute('data-testid') || el.getAttribute('alt') || '';
                    
                    // If no text and no aria, check inside for SVG hints or use own class
                    if (!text && !aria) {
                        const svg = el.tagName.toLowerCase() === 'svg' ? el : el.querySelector('svg');
                        if (svg) {
                            let svgClass = svg.getAttribute('class') || '';
                            if (typeof svgClass === 'object' && svgClass.baseVal) svgClass = svgClass.baseVal;
                            aria = svg.getAttribute('aria-label') || svg.getAttribute('title') || svg.getAttribute('data-testid') || svgClass || '';
                        }
                        if (!aria && el.tagName.toLowerCase() === 'img') {
                            aria = el.getAttribute('src') || '';
                        }
                        if (!aria) {
                            aria = el.className || '';
                            if (typeof aria === 'object' && aria.baseVal) aria = aria.baseVal;
                        }
                    }

                    // Determine approximate location on screen
                    const cx = rect.x + (rect.width / 2);
                    const cy = rect.y + (rect.height / 2);
                    const ww = window.innerWidth || document.documentElement.clientWidth;
                    const wh = window.innerHeight || document.documentElement.clientHeight;
                    
                    let locX = "center";
                    if (cx < ww * 0.33) locX = "left";
                    else if (cx > ww * 0.66) locX = "right";
                    
                    let locY = "center";
                    if (cy < wh * 0.33) locY = "top";
                    else if (cy > wh * 0.66) locY = "bottom";
                    
                    let location = `${locY}-${locX}`;
                    if (location === "center-center") location = "center";
                    
                    elements.push({
                        id: index,
                        tag: el.tagName.toLowerCase(),
                        text: text,
                        type: el.type || '',
                        aria: aria,
                        y: Math.round(rect.y),
                        loc: location,
                        context: parentText
                    });
                    // Tag the element in the DOM so we can click it later
                    el.setAttribute('data-ace-id', index);
                }
            });
            return elements;
        }
        """
        raw_elements = await self.page.evaluate(script)
        if not raw_elements:
            return []
            
        cleaned_elements = []
        for el in raw_elements:
            if not isinstance(el, dict):
                continue
            for field in ['text', 'type', 'aria', 'context', 'tag', 'loc']:
                val = el.get(field)
                if val is None:
                    el[field] = ''
                elif isinstance(val, dict):
                    el[field] = str(val.get('baseVal', val.get('animVal', str(val))))
                elif not isinstance(val, str):
                    el[field] = str(val)
            cleaned_elements.append(el)
            
        return cleaned_elements

    async def fast_path_resolve(self, intent_lower: str, action_type: str) -> tuple[list[int], str, str]:
        """
        Attempts to deterministically resolve the target element ID without an LLM.
        Returns a tuple: (element_ids, text_to_type, resolved_action_type). 
        If it fails, returns (None, None, action_type).
        """
        elements = await self.get_interactive_elements()
        if not elements:
            return None, None, action_type
            
        import re
        
        # Strip action verbs for matching
        clean_intent = re.sub(r'\b(click|press|hit|open|close|minimize|maximize|expand|collapse|toggle|type|fill|enter|write|put|set|input|select|choose|pick|check|uncheck|tick|upload|attach)\b', '', intent_lower).strip()
        
        if not clean_intent:
            return None, None, action_type

        def _norm(s: str) -> str:
            s = s.lower().strip()
            s = re.sub(r'[*:\-\s\(\)]+', ' ', s)
            return " ".join(s.split())

        # Heuristic 1: "field_name value" type heuristic.
        # Run it early if the user did NOT specify an explicit click/select verb (e.g. "product name temp")
        has_explicit_click = bool(re.search(r'\b(click|press|hit|open|select|choose|pick|check|uncheck|tick)\b', intent_lower))
        if not has_explicit_click:
            words = clean_intent.split()
            if len(words) >= 2:
                for split_idx in range(len(words)-1, 0, -1):
                    label_candidate = " ".join(words[:split_idx]).strip()
                    value_candidate = " ".join(words[split_idx:]).strip()
                    norm_cand = _norm(label_candidate)
                    
                    matches = [
                        el for el in elements 
                        if (el.get('tag') in ['input', 'textarea'] or el.get('type') in ['text', 'number', 'email', 'tel'])
                        and el.get('type') not in ['radio', 'checkbox', 'submit', 'button', 'file', 'image', 'hidden']
                        and (norm_cand == _norm(el.get('context', '')) or norm_cand == _norm(el.get('aria', '')) or norm_cand == _norm(el.get('text', '')))
                    ]
                    
                    if len(matches) == 1:
                        logger.info(f"Fast path early type match: label '{label_candidate}' (normalized: '{norm_cand}'), value '{value_candidate}'")
                        number_words = {'zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten', 'hundred', 'thousand','lakh', 'crore', 'million', 'billion'}
                        has_spelled_number = any(w in number_words for w in value_candidate.split())
                        
                        if has_spelled_number and matches[0].get('type') == 'number':
                            return [matches[0]['id']], None, "type"
                        return [matches[0]['id']], value_candidate, "type"

        # Proceed to click/check logic
        if action_type == "click" or action_type == "check":
            # Exact match on text or aria (strip punctuation like > or -)
            import re
            exact_matches = []
            for el in elements:
                t_val = re.sub(r'^[^a-zA-Z0-9]+|[^a-zA-Z0-9]+$', '', el.get('text', '')).lower().strip()
                a_val = re.sub(r'^[^a-zA-Z0-9]+|[^a-zA-Z0-9]+$', '', el.get('aria', '')).lower().strip()
                if clean_intent == t_val or clean_intent == a_val:
                    exact_matches.append(el)
                    
            if len(exact_matches) == 1:
                logger.info(f"Fast path match: exact text/aria match for '{clean_intent}'")
                return [exact_matches[0]['id']], None, action_type
                
            if len(exact_matches) > 1:
                logger.info(f"Fast path match: {len(exact_matches)} exact matches found for '{clean_intent}'")
                # Prioritize interactive tags
                priority_matches = [m for m in exact_matches if m['tag'] in ['button', 'a', 'input', 'select']]
                if priority_matches:
                    return [priority_matches[0]['id']], None, action_type
                return [exact_matches[0]['id']], None, action_type
                
            if not exact_matches:
                # Heuristic 1: If intent starts with a window control verb, see if exactly one button matches the verb
                first_word = intent_lower.split()[0] if intent_lower else ""
                if first_word in ["close", "minimize", "maximize", "open", "toggle", "expand", "collapse"]:
                    is_generic_target = not clean_intent or clean_intent in ["it", "that", "this", "the window", "window", "tab", "the tab"]
                    if is_generic_target:
                        verb_matches = [el for el in elements if el.get('text', '').lower().strip() == first_word or el.get('aria', '').lower().strip() == first_word or first_word in el.get('context', '').lower().split()]
                        # Filter to only buttons/links for this verb heuristic
                        verb_matches = [el for el in verb_matches if el.get('tag') in ['button', 'a', 'svg'] or el.get('role') == 'button']
                        if len(verb_matches) == 1:
                            logger.info(f"Fast path match: mapped verb '{first_word}' to single element")
                            return [verb_matches[0]['id']], None, action_type
                        
                # Heuristic 2: Substring inclusion & Fuzzy Matching
                # Rank matches by how closely they match the intent
                import rapidfuzz
                from rapidfuzz import process, fuzz
                
                substr_matches = []
                for el in elements:
                    text_val = el.get('text', '').lower().strip()
                    aria_val = el.get('aria', '').lower().strip()
                    
                    # 1. Exact substring check (very fast)
                    if (len(text_val) >= 4 and (text_val in intent_lower or clean_intent in text_val)) or \
                       (len(aria_val) >= 4 and (aria_val in intent_lower or clean_intent in aria_val)):
                        len_diff = min(
                            abs(len(text_val) - len(clean_intent)) if text_val else 999,
                            abs(len(aria_val) - len(clean_intent)) if aria_val else 999
                        )
                        substr_matches.append((len_diff, el))
                        continue
                        
                    # 2. Fuzzy match against the clean intent
                    # Handle typos like "free trail" vs "Start Free Trial"
                    if len(clean_intent) > 3:
                        for val in [text_val, aria_val]:
                            if val and len(val) > 3:
                                # We use both WRatio and partial_ratio to handle partial matches and typos
                                w_score = fuzz.WRatio(clean_intent, val)
                                p_score = fuzz.partial_ratio(clean_intent, val)
                                score = max(w_score, p_score)
                                
                                if score > 70:  # Lowered to 70 to catch "trail" vs "trial" (73.68 score) without LLM fallback
                                    # We use 100 - score as the "difference" so it sorts correctly alongside len_diff
                                    substr_matches.append(((100 - score) + 5, el))
                                    break
                        
                if substr_matches:
                    # Sort by difference (closest match first)
                    substr_matches.sort(key=lambda x: x[0])
                    best_diff, best_el = substr_matches[0]
                    
                    # If the best match is reasonably close, trust it (diff <= 35 corresponds to score >= 70)
                    if best_diff <= 35 or len(substr_matches) == 1:
                        logger.info(f"Fast path match: ranked match for '{best_el.get('text') or best_el.get('aria')}' (score diff: {best_diff})")
                        return [best_el['id']], None, action_type

        # Fallback Type Heuristic: If it wasn't matched above, or if action_type was already "type", let's try the "type" heuristic.
        # This handles STT typos like "price twenty two thround" or direct type actions.
        words = clean_intent.split()
        if len(words) >= 2:
            for split_idx in range(len(words)-1, 0, -1):
                label_candidate = " ".join(words[:split_idx]).strip()
                value_candidate = " ".join(words[split_idx:]).strip()
                norm_cand = _norm(label_candidate)
                
                # Check if label_candidate matches any input field's context, aria, or placeholder
                matches = [
                    el for el in elements 
                    if (el.get('tag') in ['input', 'textarea'] or el.get('type') in ['text', 'number', 'email', 'tel'])
                    and el.get('type') not in ['radio', 'checkbox', 'submit', 'button', 'file', 'image', 'hidden']
                    and (norm_cand == _norm(el.get('context', '')) or norm_cand == _norm(el.get('aria', '')) or norm_cand == _norm(el.get('text', '')))
                ]
                
                if len(matches) == 1:
                    logger.info(f"Fast path fallback type match: label '{label_candidate}' (normalized: '{norm_cand}'), value '{value_candidate}'")
                    number_words = {'zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten', 'hundred', 'thousand','lakh', 'crore', 'million', 'billion'}
                    has_spelled_number = any(w in number_words for w in value_candidate.split())
                    
                    if has_spelled_number and matches[0].get('type') == 'number':
                        return [matches[0]['id']], None, "type" # Let LLM extract the text
                    return [matches[0]['id']], value_candidate, "type"

        return None, None, action_type

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
                
            if 'loc' in el and el['loc']:
                desc += f" pos:[{el['loc']}]"
                
            element_lines.append(desc)
            
        if len(element_lines) > 150:
            logger.warning(f"DOM has {len(element_lines)} interactive elements. Truncating to 150 to prevent TPM errors.")
            element_lines = element_lines[:150]
            
        element_text = "\n".join(element_lines)
        
        headings = await self.page.evaluate("() => Array.from(document.querySelectorAll('h1, h2, h3')).map(h => h.innerText).join(' | ')")
        
        prompt = f"""
You are a browser automation agent. The user wants to perform an action: "{intent}"
The action type is: {action_type}

Page Context (Headings):
{headings}

Note: The user may be interacting with the Acesoftcloud CRM. Keep CRM terminology (Leads, Opportunities, Tickets, Invoices, Follow-ups) in mind when selecting elements.
IMPORTANT: If the user intends to interact with a form field (like "select product", "enter name"), strongly prioritize elements whose context indicates they are inside a form or creation panel (e.g., context containing 'Create', 'New', 'Add') over elements located in data tables or lists.
The user might refer to elements that do not have explicit text labels (e.g., "start date" or "end date" might just be calendar icons with type="date" next to each other). Use the 'type' attribute and the element's position (smaller Y coordinate = higher up, adjacent elements = date ranges) to infer their purpose.

CRITICAL POSITIONING: Elements include a 'pos' indicator (e.g. pos:[center], pos:[bottom-right]). Use this to distinguish visually identical buttons! If the user says "close the popup card" or "close modal", choose the button in the 'center', 'top-center', 'top-right', or 'center-right'. If they say "close the floating button" or "chat", choose the button in the 'bottom-right' or 'bottom-left'.
CRITICAL: Do NOT guess or make loose matches if the context contradicts the user's intent. For example, if the user asks for a specific date like "May 20", but the Page Context indicates the current month is "June", do NOT select the "20" button. 
If the user specifies a serial number (e.g., "S.No 2", "row 2"), you MUST match the exact number at the beginning of the row's context, and do NOT confuse it with an Order ID or Document Number that happens to contain that digit (like "ORD-0002").
If you cannot be absolutely sure the element matches the user's intent, reply with 'NONE'.

Here are the interactive elements on the current webpage:
{element_text}

Analyze the user's intent and select the single most appropriate Element ID to interact with. 
ONLY return multiple IDs if the user's intent explicitly requires interacting with multiple elements simultaneously (like filling a date range that has two inputs). Otherwise, return exactly ONE Element ID.
Reply ONLY with a comma-separated list of integer IDs (e.g., '45' or '26, 27'). If no element matches, reply with 'NONE'.
"""
        tokens = len(prompt) // 4
        logger.info(f"DOM Agent queried LLM for element ID. Approx Payload: {tokens} tokens ({len(prompt)} chars)")
        try:
            import asyncio
            response = await asyncio.wait_for(llm_service.chat(prompt), timeout=10.0)
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
        if re.search(r'\b(type|fill|enter|write|put|set|input|search|change|update|edit|modify|revise|correct|alter|fix|replace)\b', intent_lower) and not re.search(r'\b(status|dropdown|option)\b', intent_lower):
            action_type = "type"
        elif re.search(r'\b(select|choose|pick|grab)\b', intent_lower) or (re.search(r'\b(change|update|edit|modify)\b', intent_lower) and re.search(r'\b(status|dropdown|option)\b', intent_lower)):
            action_type = "select"
        elif re.search(r'\b(check|uncheck|tick|untick|mark|unmark|deselect|clear)\b', intent_lower):
            action_type = "check"
        elif re.search(r'\b(upload|attach|insert|provide)\b', intent_lower):
            action_type = "upload"
        else:
            # Smart detection: "field_name value" pattern (e.g. "company name demo45")
            # If command has NO action verb but looks like "<label> <value>", treat as type
            # Heuristic: if the last "word" looks like a value (alphanumeric, a date, a number)
            # and does not match any known button label, infer it's a fill action
            words = intent_lower.split()
            if len(words) >= 2:
                last_word = words[-1]
                number_words = {
                    'zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten',
                    'eleven', 'twelve', 'thirteen', 'fourteen', 'fifteen', 'sixteen', 'seventeen', 'eighteen', 'nineteen',
                    'twenty', 'thirty', 'forty', 'fifty', 'sixty', 'seventy', 'eighty', 'ninety',
                    'hundred', 'thousand', 'lakh', 'crore', 'million', 'billion', 'trillion'
                }
                # If last word looks like a value (contains digit, or is a short code, or is a spelled-out number), treat as type
                if re.search(r'\d', last_word) or re.match(r'^[a-z]{2,10}\d+$', last_word) or last_word in number_words:
                    action_type = "type"

        field_keywords = ['email', 'password', 'username', 'name', 'phone', 'address', 'city', 'zip', 'code', 'date', 'description', 'price', 'sku', 'cost', 'subject', 'comment', 'note', 'details', 'title', 'company', 'first', 'last']
        num_keywords = sum(1 for k in field_keywords if re.search(r'\b' + k + r'\b', intent_lower))

        # Detect bare credential pairs: e.g. "user@site.com reSet@123" or "user@site.com , pass123"
        # If the intent has an email-like token AND another non-trivial token, treat as multi-field.
        intent_tokens = intent.split()
        email_tokens = [t for t in intent_tokens if '@' in t and '.' in t]
        non_email_tokens = [t for t in intent_tokens if t not in email_tokens and len(t) > 2]
        has_email_pair = len(email_tokens) >= 1 and len(non_email_tokens) >= 1

        is_multi_field = (
            re.search(r'\b(and|with)\b', intent_lower)
            or ',' in intent
            or num_keywords >= 2
            or has_email_pair
        )
        if action_type == "type" and is_multi_field:
            logger.info("Intent looks like a multi-field fill (detected separators, multiple keywords, or email+credential pair), delegating to fill_form.")
            fill_result = await self.fill_form(intent)
            # Route through the friendly rewriter so the user gets a natural spoken confirmation
            try:
                import asyncio
                rewrite_prompt = f"User command: '{intent}'. System result: '{fill_result}'. Rewrite this into a very short, conversational confirmation as a helpful voice assistant (e.g. 'Filled in your email and password', 'Entered your details'). Do NOT reveal any credential values. Do NOT use the phrase 'for you'. Keep it under 1 short sentence."
                friendly = await asyncio.wait_for(llm_service.chat(rewrite_prompt), timeout=5.0)
                return friendly.strip()
            except Exception as e:
                logger.error(f"Error: {e}")
                return fill_result

        fast_element_ids, fast_text, resolved_action_type = await self.fast_path_resolve(intent_lower, action_type)
        fast_path_used = False
        
        if fast_element_ids:
            element_ids = fast_element_ids
            action_type = resolved_action_type
            fast_path_used = True
            logger.info(f"Bypassed LLM for element ID. Using fast path: {element_ids} (action: {action_type})")
        else:
            element_ids = await self.find_element_for_intent(intent, action_type)
        
        # Prevent runaway multi-element execution hallucinated by the LLM
        if element_ids and not re.search(r'\b(all|both|range|multiple|every)\b', intent_lower):
            if len(element_ids) > 1:
                logger.warning(f"LLM returned {len(element_ids)} IDs but intent does not imply multiple elements. Truncating to 1.")
                element_ids = element_ids[:1]
                
        if not element_ids:
            return f"I couldn't find '{intent}'."
            
        results = []
        for i, element_id in enumerate(element_ids):
            current_action = action_type
            try:
                selector = f"[data-ace-id='{element_id}']"
                
                # Dynamically correct action_type based on actual element tag
                try:
                    el_info = await self.page.evaluate(f"""
                        (() => {{
                            const el = document.querySelector("{selector}");
                            if (!el) return {{}};
                            return {{
                                tag: el.tagName.toLowerCase(),
                                type: el.type || '',
                                isContentEditable: el.isContentEditable
                            }};
                        }})()
                    """)
                    tag = el_info.get('tag', '')
                    el_type = el_info.get('type', '')
                    
                    if current_action == "click":
                        is_input = (tag in ['input', 'textarea'] and el_type not in ['submit', 'button', 'checkbox', 'radio', 'file', 'image']) or el_info.get('isContentEditable')
                        if is_input and len(intent_lower.split()) >= 2 and not re.search(r'\b(click|press|hit|focus|select)\b', intent_lower):
                            logger.info(f"Element {element_id} is an input and intent has {len(intent_lower.split())} words. Converting 'click' to 'type'.")
                            current_action = "type"
                            
                    elif current_action == "type":
                        if tag == "select":
                            logger.info(f"Element {element_id} is a <select> but action was 'type'. Converting 'type' to 'select'.")
                            current_action = "select"
                        elif tag == "input" and el_type in ["radio", "checkbox"]:
                            logger.info(f"Element {element_id} is a {el_type} but action was 'type'. Converting 'type' to 'click'.")
                            current_action = "click"
                except Exception as e:
                    logger.error(f"Error: {e}")
                    pass
                
                # Show visual feedback
                await self.animate_action(selector, current_action)
                
                if current_action == "click":
                    try:
                        # Find if there is a more appropriate parent button/link/combobox/dropdown trigger to click.
                        # This ensures the click event targets the container holding the event listener, preventing 
                        # inner spans/divs/icons from swallowing the click or failing custom React reference checks.
                        resolved_selector = await self.page.evaluate(f"""
                            (() => {{
                                const el = document.querySelector("{selector}");
                                if (!el) return "{selector}";
                                const parent = el.closest('button, a, [role="button"], [role="combobox"], [role="select"], [aria-haspopup="true"], [class*="select-trigger"], [class*="dropdown-trigger"], .dropdown-toggle');
                                if (parent && parent !== el) {{
                                    if (!parent.hasAttribute('data-ace-id')) {{
                                        parent.setAttribute('data-ace-id', 'parent-' + Date.now());
                                    }}
                                    return '[data-ace-id="' + parent.getAttribute('data-ace-id') + '"]';
                                }}
                                return "{selector}";
                            }})()
                        """)
                        await self.page.click(resolved_selector, timeout=3000)
                    except Exception as native_err:
                        logger.warning(f"Native click failed ({native_err}), falling back to robust JS pointer events.")
                        # Fallback to native DOM click if Playwright click fails
                        clicked = await self.page.evaluate(f"""
                            (() => {{
                                let el = document.querySelector("{selector}");
                                if (el) {{
                                    const parentBtn = el.closest('button, a, [role="button"], [role="combobox"], [role="select"], [aria-haspopup="true"], [class*="select-trigger"], [class*="dropdown-trigger"], .dropdown-toggle');
                                    if (parentBtn) el = parentBtn;
                                    
                                    // Many modern UI libraries (HeadlessUI, Radix, MUI) listen for pointerdown/mousedown 
                                    // instead of click to open dropdown menus faster.
                                    el.dispatchEvent(new PointerEvent('pointerdown', {{ bubbles: true, cancelable: true, view: window }}));
                                    el.dispatchEvent(new MouseEvent('mousedown', {{ bubbles: true, cancelable: true, view: window }}));
                                    el.dispatchEvent(new PointerEvent('pointerup', {{ bubbles: true, cancelable: true, view: window }}));
                                    el.dispatchEvent(new MouseEvent('mouseup', {{ bubbles: true, cancelable: true, view: window }}));
                                    el.click();
                                    return true;
                                }}
                                return false;
                            }})()
                        """)
                        if not clicked:
                            raise Exception(f"Element {selector} disappeared from the page before clicking.")
                    results.append("Clicked the requested element.")
                elif current_action == "check":
                    if "uncheck" in intent_lower:
                        await self.page.uncheck(selector, timeout=3000)
                        results.append("Unchecked the requested element.")
                    else:
                        await self.page.check(selector, timeout=3000)
                        results.append("Checked the requested element.")
                elif current_action == "select":
                    extract_prompt = f"Extract exactly the option text or value the user wants to select from this intent: '{intent}'. Reply ONLY with the text."
                    import asyncio
                    option_to_select = await asyncio.wait_for(llm_service.chat(extract_prompt), timeout=6.0)
                    option_to_select = option_to_select.strip()
                    
                    match_script = f"""
                        (() => {{
                            const select = document.querySelector("{selector}");
                            if (!select || select.tagName.toLowerCase() !== 'select') return null;
                            const search = `{option_to_select}`.toLowerCase();
                            for (let opt of select.options) {{
                                if (opt.text.toLowerCase().includes(search) || opt.value.toLowerCase().includes(search) || search.includes(opt.text.toLowerCase())) {{
                                    return opt.value;
                                }}
                            }}
                            return null;
                        }})()
                    """
                    best_val = await self.page.evaluate(match_script)
                    if best_val:
                        await self.page.select_option(selector, value=best_val, timeout=3000)
                        results.append(f"Selected '{option_to_select}'.")
                    else:
                        try:
                            await self.page.select_option(selector, label=option_to_select, timeout=3000)
                            results.append(f"Selected '{option_to_select}'.")
                        except Exception as e:
                            logger.error(f"Error: {e}")
                            raise Exception(f"Could not find an option matching '{option_to_select}' in the dropdown.")
                elif current_action == "upload":
                    extract_prompt = f"Extract exactly the filename (with extension if provided) the user wants to upload from this intent: '{intent}'. Reply ONLY with the filename."
                    import asyncio
                    filename = await asyncio.wait_for(llm_service.chat(extract_prompt), timeout=6.0)
                    filename = filename.strip()
                    
                    from automation.desktop.file_indexer import get_indexer
                    indexer = get_indexer()
                    results_list = indexer.search(query=filename, is_folder=False, limit=1)
                    if not results_list:
                        results.append(f"Could not find local file matching '{filename}'.")
                        continue
                        
                    file_path = results_list[0]['path']
                    logger.info(f"Uploading file resolved to: {file_path}")
                    
                    file_input_selector = await self.page.evaluate(f"""
                        (() => {{
                            const el = document.querySelector("{selector}");
                            if (!el) return null;
                            if (el.tagName.toLowerCase() === 'input' && el.type === 'file') return "{selector}";
                            const inner = el.querySelector('input[type="file"]');
                            if (inner) {{
                                if (!inner.hasAttribute('data-ace-id')) inner.setAttribute('data-ace-id', 'temp-' + Date.now());
                                return '[data-ace-id="' + inner.getAttribute('data-ace-id') + '"]';
                            }}
                            const anyFile = document.querySelector('input[type="file"]');
                            if (anyFile) {{
                                if (!anyFile.hasAttribute('data-ace-id')) anyFile.setAttribute('data-ace-id', 'temp-' + Date.now());
                                return '[data-ace-id="' + anyFile.getAttribute('data-ace-id') + '"]';
                            }}
                            return null;
                        }})()
                    """)
                    if not file_input_selector:
                        results.append("Could not find a file input element on the page.")
                        continue
                        
                    await self.page.set_input_files(file_input_selector, file_path)
                    results.append(f"Uploaded file '{filename}'.")
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
                    except Exception as e:
                        logger.error(f"Error: {e}")
                        pass
                        
                    if not is_fillable:
                        logger.info(f"Element {element_id} is a button/link but action was 'type'. Converting to 'click'.")
                        await self.page.click(selector, timeout=3000)
                        results.append(f"Clicked element {element_id} instead of typing.")
                        continue

                    if is_date:
                        date_target = "first (start) date" if i == 0 else "second (end) date" if i == 1 else "date"
                        extract_prompt = f"Extract exactly the {date_target} the user wants to type into the field from this intent: '{intent}'. Format it strictly as YYYY-MM-DD (e.g., 2026-04-10). Reply ONLY with the formatted date."
                    elif el_info.get('type') == 'number':
                        extract_prompt = f"Extract exactly the numeric value the user wants to type into the field from this intent: '{intent}'. Convert any spelled-out numbers into digits (e.g., 'eight thousand' -> '8000'). Reply ONLY with the numeric digits."
                    else:
                        extract_prompt = f"Extract exactly the text the user wants to type from this intent: '{intent}'. Omit any action verbs like 'type', 'search', 'enter', or 'write'. If the text contains spelled-out numbers meant for a numeric field, convert them to digits. Reply ONLY with the text."
                    
                    if fast_path_used and fast_text is not None and not is_date:
                        text_to_type = fast_text
                        logger.info(f"Bypassed LLM for text extraction. Using fast path value: '{text_to_type}'")
                    else:
                        tokens = len(extract_prompt) // 4
                        logger.info(f"DOM Agent queried LLM for text extraction. Approx Payload: {tokens} tokens")
                        import asyncio
                        text_to_type = await asyncio.wait_for(llm_service.chat(extract_prompt), timeout=6.0)
                        text_to_type = text_to_type.strip()
                    
                    if el_info.get('type') == 'number':
                        import re
                        text_to_type = re.sub(r'[^\d.]', '', text_to_type)
                        
                    try:
                        await self.page.fill(selector, text_to_type, timeout=3000)
                    except Exception as e:
                        logger.warning(f"Native fill failed, falling back to JS injection: {e}")
                        await self.page.evaluate(f"""
                            (() => {{
                                        let targetEl = document.querySelector("{selector}");
                                        if (targetEl) {{
                                            if (targetEl.tagName.toLowerCase() !== 'input' && targetEl.tagName.toLowerCase() !== 'textarea') {{
                                                const childInput = targetEl.querySelector('input, textarea');
                                                if (childInput) targetEl = childInput;
                                            }}
                                            
                                            const nativeSetter = Object.getOwnPropertyDescriptor(
                                                window.HTMLInputElement.prototype, 'value'
                                            )?.set || Object.getOwnPropertyDescriptor(
                                                window.HTMLTextAreaElement.prototype, 'value'
                                            )?.set;
                                            
                                            if (nativeSetter) {{
                                                nativeSetter.call(targetEl, `{text_to_type}`);
                                            }} else {{
                                                targetEl.value = `{text_to_type}`;
                                            }}
                                            
                                            targetEl.dispatchEvent(new Event('input', {{ bubbles: true }}));
                                            targetEl.dispatchEvent(new Event('change', {{ bubbles: true }}));
                                        }} else {{
                                            throw new Error("Element " + "{selector}" + " no longer exists in DOM.");
                                        }}
                            }})()
                        """)
                    results.append(f"Typed '{text_to_type}' into the element.")
                    
            except Exception as e:
                err_msg = str(e)
                if "disappeared from the page" in err_msg or "Execution context was destroyed" in err_msg or "Target page, context or browser has been closed" in err_msg or "Target closed" in err_msg:
                    logger.info(f"Element {element_id} disappeared or context destroyed (likely due to successful navigation). Stopping loop.")
                    break
                logger.error(f"Failed to execute {current_action} on element {element_id}: {e}")
                results.append(f"Action failed for element {element_id}: {e}")
                
        raw_result = " and ".join(results)
        if not raw_result:
            return "Action completed."
            
        if "Action failed" in raw_result:
            return raw_result
            
        try:
            import asyncio
            prompt = f"User command: '{intent}'. System result: '{raw_result}'. Rewrite this into a very short, conversational confirmation as a helpful voice assistant (e.g. 'Signed you in', 'Opened the dropdown', 'Typed John into the name field'). Do NOT use the phrase 'for you' or sound overly eager. Keep it under 1 short sentence."
            friendly_result = await asyncio.wait_for(llm_service.chat(prompt), timeout=5.0)
            return friendly_result.strip()
        except Exception as e:
            logger.error(f"Failed to generate friendly response: {e}")
            return raw_result

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

        # ── Deterministic Credential Pre-fill ────────────────────────────────
        # Detect a bare "email + password" pair in the context (e.g. "user@site.com , Pass@123")
        # Fill directly using the HTML type attribute — zero LLM tokens, zero mis-mapping.
        import re as _re
        context_tokens = context.split()
        # A real email must have @ AND a dot after the @ (e.g. user@gmail.com)
        email_cands = [t.strip(',.') for t in context_tokens if '@' in t and '.' in t.split('@')[-1]]
        stop_words = {'type', 'enter', 'write', 'fill', 'and', 'with', 'the', 'into', 'in', 'to'}
        pass_cands = [
            t.strip(',.')
            for t in context_tokens
            if t.strip(',.') not in email_cands
            and t.strip(',.').lower() not in stop_words
            and len(t.strip(',.')) > 3
        ]

        if email_cands and pass_cands:
            email_val = email_cands[0]
            pass_val  = pass_cands[-1]   # last non-email token is the password

            # Find email field: prefer type=email, fall back to text field labelled email/username
            email_field = next(
                (el for el in inputs if el.get('type') == 'email'),
                None
            ) or next(
                (el for el in inputs
                 if el.get('type') in ('text', '')
                 and any(k in (el.get('text','') + el.get('aria','') + el.get('context','')).lower()
                         for k in ('email', 'username', 'user name', 'mail', 'login'))),
                None
            )
            # Find password field: type=password is definitive
            pass_field = next(
                (el for el in inputs if el.get('type') == 'password'),
                None
            )

            if email_field and pass_field:
                logger.info(
                    f"Deterministic credential fill: email→field {email_field['id']} "
                    f"('{email_val}'), password→field {pass_field['id']}"
                )
                filled = []
                for field_el, value in ((email_field, email_val), (pass_field, pass_val)):
                    selector = f"[data-ace-id='{field_el['id']}']"
                    await self.animate_action(selector, "type")
                    try:
                        await self.page.fill(selector, value, timeout=3000)
                    except Exception as e:
                        logger.error(f"Error: {e}")
                        # JS fallback for React-controlled inputs
                        safe_val = value.replace('`', r'\`').replace('\\', '\\\\')
                        await self.page.evaluate(f"""
                            (() => {{
                                const el = document.querySelector("{selector}");
                                if (!el) return;
                                const setter = Object.getOwnPropertyDescriptor(
                                    window.HTMLInputElement.prototype, 'value')?.set;
                                if (setter) setter.call(el, `{safe_val}`);
                                else el.value = `{safe_val}`;
                                el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                                el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                            }})()
                        """)
                    field_label = (field_el.get('type') or 'field').strip()
                    filled.append(field_label)

                return f"Filled in {' and '.join(filled)}."
        # ── End Deterministic Credential Pre-fill ─────────────────────────────

        # Build a richer description that includes field type/placeholder/context so LLM can route correctly
        desc_parts = []
        for el in inputs:
            el_type = el.get('type', '') or el.get('tag', '')
            placeholder = el.get('text', '') or el.get('aria', '') or ''
            context_text = el.get('context', '')
            desc_parts.append(f"[{el['id']}] type={el_type} label/placeholder='{placeholder}' context/label='{context_text}'")
        desc = "\n".join(desc_parts)

        prompt = f"""You are a form filling agent. The user provided this instruction: "{context}"

Here are the available form fields on the page:
{desc}

CRITICAL RULES — you MUST follow these exactly:
1. Map EACH value to EXACTLY ONE field. NEVER put two values in the same field.
2. A real email address has BOTH @ AND a domain with a dot (e.g. user@gmail.com). It goes into the field with type='email' or label containing 'email'/'username'.
3. A password goes into the field with type='password'. A string like "Pass@123" or "Nivin@0089" is a PASSWORD — NOT an email — because it has no proper domain after the @.
4. Preserve the EXACT casing of passwords and email addresses — do NOT lowercase them.
5. When in doubt: the value containing @gmail.com / @yahoo.com / @domain.com is the EMAIL. Everything else is the PASSWORD.

Reply strictly in JSON format where keys are the integer field IDs and values are the text to fill.
Example: {{"5": "user@example.com", "6": "MyPass@123"}}
Reply ONLY with the JSON object, nothing else."""

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
                        el = next((e for e in inputs if str(e['id']) == eid_str), None)
                        if not el: continue
                        el_type = el['tag']
                        
                        await self.animate_action(selector, "type" if el_type != 'select' else "select")
                        
                        if el_type == 'select':
                            match_script = f"""
                                (() => {{
                                    const select = document.querySelector("{selector}");
                                    if (!select) return null;
                                    const search = `{str(value)}`.toLowerCase();
                                    for (let opt of select.options) {{
                                        if (opt.text.toLowerCase().includes(search) || opt.value.toLowerCase().includes(search) || search.includes(opt.text.toLowerCase())) {{
                                            return opt.value;
                                        }}
                                    }}
                                    return null;
                                }})()
                            """
                            best_val = await self.page.evaluate(match_script)
                            if best_val:
                                await self.page.select_option(selector, value=best_val)
                            else:
                                await self.page.select_option(selector, label=str(value))
                        else:
                            text_to_type = str(value)
                            if el.get('type') == 'number':
                                import re
                                text_to_type = re.sub(r'[^\d.]', '', text_to_type)
                            
                            try:
                                await self.page.fill(selector, text_to_type, timeout=3000)
                            except Exception as e:
                                await self.page.evaluate(f"""
                                    (() => {{
                                        let targetEl = document.querySelector("{selector}");
                                        if (targetEl) {{
                                            if (targetEl.tagName.toLowerCase() !== 'input' && targetEl.tagName.toLowerCase() !== 'textarea') {{
                                                const childInput = targetEl.querySelector('input, textarea');
                                                if (childInput) targetEl = childInput;
                                            }}
                                            
                                            const nativeSetter = Object.getOwnPropertyDescriptor(
                                                window.HTMLInputElement.prototype, 'value'
                                            )?.set || Object.getOwnPropertyDescriptor(
                                                window.HTMLTextAreaElement.prototype, 'value'
                                            )?.set;
                                            
                                            if (nativeSetter) {{
                                                nativeSetter.call(targetEl, `{text_to_type}`);
                                            }} else {{
                                                targetEl.value = `{text_to_type}`;
                                            }}
                                            
                                            targetEl.dispatchEvent(new Event('input', {{ bubbles: true }}));
                                            targetEl.dispatchEvent(new Event('change', {{ bubbles: true }}));
                                        }} else {{
                                            throw new Error("Element " + "{selector}" + " no longer exists in DOM.");
                                        }}
                                    }})()
                                """)
                    except Exception as e:
                        logger.warning(f"Failed to fill field {eid_str}: {e}")

                # Build a human-readable summary of what was filled (without exposing credential values)
                filled_labels = []
                for eid_str in mapping.keys():
                    el = next((e for e in inputs if str(e['id']) == eid_str), None)
                    if not el:
                        continue
                    el_input_type = el.get('type', '')
                    label = el.get('text', '') or el.get('aria', '') or el_input_type or 'field'
                    label = label.strip().lower()
                    if not label or label.startswith('enter') or label.startswith('type'):
                        label = el_input_type or 'field'
                    filled_labels.append(label)

                if filled_labels:
                    fields_str = ' and '.join(filled_labels)
                    return f"Filled in {fields_str}."
                return "Form fields filled successfully."
            return "Could not determine which fields to fill. Please try rephrasing."
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

    async def animate_action(self, selector: str, action: str):
        """Injects visual feedback (CSS/JS) into the browser right before an action is performed."""
        if not settings.browser_animations_enabled:
            return
            
        script = f"""
        () => {{
            try {{
                const el = document.querySelector("{selector}");
                if (!el) return;
                const rect = el.getBoundingClientRect();
                if (rect.width === 0 || rect.height === 0) return;
                
                const x = rect.left + rect.width / 2 + window.scrollX;
                const y = rect.top + rect.height / 2 + window.scrollY;
                
                const anim = document.createElement('div');
                anim.style.position = 'absolute';
                anim.style.pointerEvents = 'none';
                anim.style.zIndex = '2147483647'; // max z-index
                
                if ("{action}" === "click" || "{action}" === "check") {{
                    // Cursor pointer with ripple
                    anim.style.left = x + 'px';
                    anim.style.top = y + 'px';
                    anim.style.width = '24px';
                    anim.style.height = '36px';
                    anim.style.transition = 'opacity 0.3s ease-out';
                    
                    anim.innerHTML = `
                    <div id="ace-ripple" style="position: absolute; top: -8px; left: -8px; width: 20px; height: 20px; border-radius: 50%; background-color: rgba(255, 255, 255, 0.6); border: 2px solid rgba(0, 0, 0, 0.2); transform: scale(0); transition: transform 0.4s ease-out, opacity 0.4s ease-out;"></div>
                    <svg id="ace-cursor-svg" width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="position: absolute; top: 0; left: 0; filter: drop-shadow(0px 4px 10px rgba(0, 0, 0, 0.4)); transform-origin: top left; transition: transform 0.1s ease-in-out; color: black;">
                        <path d="m4 4 7.07 17 2.51-7.39L21 11.07z" fill="white" stroke="black" stroke-width="1.5"/>
                    </svg>`;
                    
                    document.body.appendChild(anim);
                    
                    const svg = anim.querySelector('#ace-cursor-svg');
                    const ripple = anim.querySelector('#ace-ripple');
                    
                    // Trigger "click press" and ripple animation
                    requestAnimationFrame(() => {{
                        requestAnimationFrame(() => {{
                            svg.style.transform = 'scale(0.85)';
                            ripple.style.transform = 'scale(3.5)';
                            ripple.style.opacity = '0';
                            
                            setTimeout(() => {{
                                svg.style.transform = 'scale(1)';
                                setTimeout(() => {{
                                    anim.style.opacity = '0';
                                }}, 150);
                            }}, 100);
                        }});
                    }});
                    setTimeout(() => anim.remove(), 700);
                    
                }} else if ("{action}" === "type" || "{action}" === "select") {{
                    // Highlight box
                    anim.style.left = (rect.left + window.scrollX) + 'px';
                    anim.style.top = (rect.top + window.scrollY) + 'px';
                    anim.style.width = rect.width + 'px';
                    anim.style.height = rect.height + 'px';
                    anim.style.borderRadius = '4px';
                    anim.style.border = '2px solid rgba(34, 197, 94, 0.8)'; // Tailwind green-500
                    anim.style.backgroundColor = 'rgba(34, 197, 94, 0.2)';
                    anim.style.transition = 'opacity 0.2s';
                    
                    document.body.appendChild(anim);
                    
                    // Pulse
                    let count = 0;
                    const pulse = setInterval(() => {{
                        anim.style.opacity = (count % 2 === 0) ? '0.3' : '1';
                        count++;
                    }}, 150);
                    
                    setTimeout(() => {{
                        clearInterval(pulse);
                        anim.style.opacity = '0';
                        setTimeout(() => anim.remove(), 200);
                    }}, 1500);
                }}
            }} catch (e) {{
                console.error("Animation error", e);
            }}
        }}
        """
        try:
            await self.page.evaluate(script)
            # Give a tiny delay for the user to see the animation begin before the page potentially navigates away
            import asyncio
            await asyncio.sleep(0.3)
        except Exception as e:
            logger.debug(f"Animation failed: {{e}}")
