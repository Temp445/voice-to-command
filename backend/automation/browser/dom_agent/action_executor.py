import re
import asyncio
import datetime
from loguru import logger
from playwright.async_api import Page
from app.services.llm.llm_service import llm_service
from app.config import settings
from app.services.page_context_service import page_context_service, find_best_element, PageElement
from automation.browser.browser_engine import BrowserEngine

MONTHS_MAP = {
    "january": "01", "jan": "01", "1": "01", "01": "01",
    "february": "02", "feb": "02", "2": "02", "02": "02",
    "march": "03", "mar": "03", "3": "03", "03": "03",
    "april": "04", "apr": "04", "4": "04", "04": "04",
    "may": "05", "5": "05", "05": "05",
    "june": "06", "jun": "06", "6": "06", "06": "06",
    "july": "07", "jul": "07", "7": "07", "07": "07",
    "august": "08", "aug": "08", "8": "08", "08": "08",
    "september": "09", "sep": "09", "sept": "09", "9": "09", "09": "09",
    "october": "10", "oct": "10", "10": "10",
    "november": "11", "nov": "11", "11": "11",
    "december": "12", "dec": "12", "12": "12",
}

def parse_month_value(fill_value: str, current_value: str = None) -> str | None:
    now = datetime.datetime.now()
    curr_year = now.year
    curr_month = now.month
    
    if current_value:
        m_year = re.match(r'^(\d{4})', current_value.strip())
        if m_year:
            curr_year = int(m_year.group(1))
            
    val_clean = fill_value.lower().strip()
    
    year_match = re.search(r'\b(20\d{2})\b', val_clean)
    target_year = curr_year
    if year_match:
        target_year = int(year_match.group(1))
        val_clean = val_clean.replace(year_match.group(1), "").strip()
        
    target_month = None
    if "this month" in val_clean:
        target_month = now.month
        target_year = now.year
    elif "next month" in val_clean:
        target_month = now.month + 1
        target_year = now.year
        if target_month > 12:
            target_month = 1
            target_year += 1
    elif "last month" in val_clean or "previous month" in val_clean:
        target_month = now.month - 1
        target_year = now.year
        if target_month < 1:
            target_month = 12
            target_year -= 1
    else:
        val_words = re.findall(r'[a-z0-9]+', val_clean)
        for w in val_words:
            if w in MONTHS_MAP:
                target_month = int(MONTHS_MAP[w])
                break
                
    if target_month is not None:
        return f"{target_year:04d}-{target_month:02d}"
        
    m_slash = re.search(r'\b(0?[1-9]|1[0-2])[-/](20\d{2})\b', val_clean)
    if m_slash:
        return f"{int(m_slash.group(2)):04d}-{int(m_slash.group(1)):02d}"
        
    m_iso = re.search(r'\b(20\d{2})[-/](0?[1-9]|1[0-2])\b', val_clean)
    if m_iso:
        return f"{int(m_iso.group(1)):04d}-{int(m_iso.group(2)):02d}"
        
    return None

def parse_date_value(fill_value: str, current_value: str = None) -> str | None:
    now = datetime.datetime.now()
    curr_year = now.year
    curr_month = now.month
    curr_day = now.day
    
    if current_value:
        m_date = re.match(r'^(\d{4})-(\d{2})-(\d{2})', current_value.strip())
        if m_date:
            curr_year = int(m_date.group(1))
            curr_month = int(m_date.group(2))
            curr_day = int(m_date.group(3))
            
    val_clean = fill_value.lower().strip()
    
    if "today" in val_clean:
        return now.strftime("%Y-%m-%d")
    elif "tomorrow" in val_clean:
        tomorrow = now + datetime.timedelta(days=1)
        return tomorrow.strftime("%Y-%m-%d")
    elif "yesterday" in val_clean:
        yesterday = now - datetime.timedelta(days=1)
        return yesterday.strftime("%Y-%m-%d")
        
    year_match = re.search(r'\b(20\d{2})\b', val_clean)
    target_year = curr_year
    if year_match:
        target_year = int(year_match.group(1))
        val_clean = val_clean.replace(year_match.group(1), "").strip()
        
    day_match = re.search(r'\b(\d{1,2})(?:st|nd|rd|th)?\b', val_clean)
    target_day = curr_day
    if day_match:
        target_day = int(day_match.group(1))
        val_clean = val_clean.replace(day_match.group(0), "").strip()
        
    target_month = curr_month
    val_words = re.findall(r'[a-z0-9]+', val_clean)
    for w in val_words:
        if w in MONTHS_MAP:
            target_month = int(MONTHS_MAP[w])
            break
            
    try:
        dt = datetime.date(target_year, target_month, target_day)
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        pass
        
    m_iso = re.search(r'\b(20\d{2})[-/](0?[1-9]|1[0-2])[-/](0?[1-9]|[12]\d|3[01])\b', fill_value)
    if m_iso:
        return f"{int(m_iso.group(1)):04d}-{int(m_iso.group(2)):02d}-{int(m_iso.group(3)):02d}"
        
    m_us = re.search(r'\b(0?[1-9]|1[0-2])[-/](0?[1-9]|[12]\d|3[01])[-/](20\d{2})\b', fill_value)
    if m_us:
        return f"{int(m_us.group(3)):04d}-{int(m_us.group(1)):02d}-{int(m_us.group(2)):02d}"
        
    m_eu = re.search(r'\b(0?[1-9]|[12]\d|3[01])[-/](0?[1-9]|1[0-2])[-/](20\d{2})\b', fill_value)
    if m_eu:
        return f"{int(m_eu.group(3)):04d}-{int(m_eu.group(2)):02d}-{int(m_eu.group(1)):02d}"
        
    return None

def parse_week_value(fill_value: str, current_value: str = None) -> str | None:
    now = datetime.datetime.now()
    curr_year = now.year
    
    val_clean = fill_value.lower().strip()
    year_match = re.search(r'\b(20\d{2})\b', val_clean)
    target_year = curr_year
    if year_match:
        target_year = int(year_match.group(1))
        val_clean = val_clean.replace(year_match.group(1), "").strip()
        
    week_match = re.search(r'\b(?:week\s+)?(\d{1,2})\b', val_clean)
    if week_match:
        week_num = int(week_match.group(1))
        if 1 <= week_num <= 53:
            return f"{target_year:04d}-W{week_num:02d}"
            
    return None

def _get_element_label(el) -> str:
    """Get a user-friendly label for the element."""
    label = (el.text or el.name or el.placeholder or el.el_id or "").strip()
    label = " ".join(label.split())
    if not label:
        return f"{el.role or el.tag or 'element'}"
    if len(label) > 40:
        label = label[:37] + "..."
    return f"'{label}'"


class ActionExecutorMixin:
    async def _click_element(self, handle, timeout: int = 2000) -> None:
        """
        Click an element with a timeout, falling back to force=True if intercepted or failing.
        """
        try:
            await handle.click(timeout=timeout)
        except Exception as e:
            logger.debug(f"Normal click failed, retrying with force=True: {e}")
            await handle.click(timeout=timeout, force=True)

    async def _fill_input(self, handle, el, raw_value: str) -> str:
        """
        Fills an input element, formatting the value if it's a special type
        (month, date, week) to prevent malformed value errors.
        Also triggers a success chime and visual highlight on success.
        """
        el_type = getattr(el, "el_type", "").lower()
        if not el_type:
            try:
                el_type = await handle.evaluate("el => el.type || ''")
                el_type = el_type.lower()
            except Exception:
                pass

        formatted_value = raw_value
        current_value = None
        try:
            current_value = await handle.evaluate("el => el.value")
        except Exception:
            pass

        if current_value:
            # Check if raw_value is a case modifier (e.g. "nsmall", "r caps", "r capital")
            raw_value_spaced = re.sub(
                r'\b([a-zA-Z])(caps|capital|small|lowercase|lower)\b',
                r'\1 \2', raw_value, flags=re.IGNORECASE
            ).strip()
            if re.match(r'^[a-zA-Z]\s+(caps|capital|small|lowercase|lower)s?$', raw_value_spaced, re.IGNORECASE):
                from app.services.spelling_service import apply_caps_modifier
                combined = f"{current_value} {raw_value_spaced}"
                modified = apply_caps_modifier(combined).strip()
                if modified and modified != current_value and modified != raw_value:
                    logger.info(f"Modifier applied to existing value in _fill_input: '{current_value}' + '{raw_value}' → '{modified}'")
                    formatted_value = modified

        if el_type in ("month", "date", "week"):

            if el_type == "month":
                parsed = parse_month_value(raw_value, current_value)
                if parsed:
                    formatted_value = parsed
            elif el_type == "date":
                parsed = parse_date_value(raw_value, current_value)
                if parsed:
                    formatted_value = parsed
            elif el_type == "week":
                parsed = parse_week_value(raw_value, current_value)
                if parsed:
                    formatted_value = parsed

        logger.info(f"Filling input of type '{el_type}' with value '{formatted_value}' (raw: '{raw_value}')")
        
        # Step 1: Attempt native fill on the underlying input element.
        # This works for native <input type="month">, <input type="date">, and plain text inputs.
        fill_succeeded = False
        try:
            await handle.fill(formatted_value, timeout=2000)
            fill_succeeded = True
        except Exception as fill_err:
            logger.debug(f"Direct fill failed on '{el_type}' input: {fill_err}")

        # Step 2: For date/month/week types, also try to interact with any custom JS picker
        # popup that may be open (opened by the preceding click). This handles cases where
        # the site uses a custom calendar widget that doesn't respond to input.value changes.
        if el_type in ("month", "date", "week"):
            picker_interacted = await self._interact_with_calendar_picker(formatted_value, el_type)
            if picker_interacted:
                logger.info(f"Custom calendar picker interaction succeeded for '{formatted_value}'")
            elif not fill_succeeded:
                # Native fill also failed — try keyboard fallback
                logger.debug(f"Picker interaction skipped or failed. Trying keyboard fallback.")
                try:
                    await handle.focus()
                    await handle.evaluate("el => el.value = ''")
                    await self.page.keyboard.type(formatted_value)
                    await self.page.keyboard.press("Enter")
                except Exception as type_err:
                    logger.warning(f"Keyboard fallback failed: {type_err}")
        elif not fill_succeeded:
            # Non-date field where fill failed — try keyboard
            try:
                await handle.focus()
                await handle.evaluate("el => el.value = ''")
                await self.page.keyboard.type(formatted_value)
                await self.page.keyboard.press("Enter")
            except Exception as type_err:
                logger.warning(f"Keyboard fallback failed: {type_err}")

        # Provide immediate auditory and visual feedback upon successful fill
        try:
            feedback_js = """
            async (el) => {
                // 1. Play a subtle, pleasant chime using Web Audio API
                try {
                    const ctx = new (window.AudioContext || window.webkitAudioContext)();
                    const osc = ctx.createOscillator();
                    const gain = ctx.createGain();
                    osc.connect(gain);
                    gain.connect(ctx.destination);
                    osc.type = 'sine';
                    osc.frequency.setValueAtTime(523.25, ctx.currentTime);
                    gain.gain.setValueAtTime(0, ctx.currentTime);
                    gain.gain.linearRampToValueAtTime(0.08, ctx.currentTime + 0.04);
                    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.12);
                    osc.frequency.setValueAtTime(659.25, ctx.currentTime + 0.12);
                    gain.gain.linearRampToValueAtTime(0.08, ctx.currentTime + 0.16);
                    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.30);
                    osc.start();
                    osc.stop(ctx.currentTime + 0.35);
                } catch (e) {
                    console.warn("Failed to play audio chime:", e);
                }

                // 2. Visual green checkmark/glow feedback
                const origOutline = el.style.outline;
                const origTransition = el.style.transition;
                el.style.transition = 'outline 0.15s ease, box-shadow 0.15s ease';
                el.style.outline = '3px solid rgba(46, 204, 113, 0.8)';
                el.style.boxShadow = '0 0 8px rgba(46, 204, 113, 0.6)';
                
                setTimeout(() => {
                    el.style.outline = origOutline;
                    el.style.boxShadow = '';
                    setTimeout(() => {
                        el.style.transition = origTransition;
                    }, 150);
                }, 1000);
            }
            """
            await handle.evaluate(feedback_js)
        except Exception as e:
            logger.debug(f"Failed to show feedback on element: {e}")

        return formatted_value

    async def _interact_with_calendar_picker(self, formatted_value: str, el_type: str) -> bool:
        """
        Detect and interact with a custom JS calendar picker popup.
        Called after a native fill() so the underlying input value is already set.
        Handles:
          - Month-grid pickers (Jan/Feb/... grid, e.g. ACE Payroll Deduction Start Month)
          - Date-grid pickers (standard month/year + day grid)
          - Year navigation for both types
        Returns True if picker interaction was performed.
        """
        try:
            await asyncio.sleep(0.25)  # Brief wait for picker animation

            if el_type == "month" and re.match(r'^\d{4}-\d{2}$', formatted_value):
                year_str, month_str = formatted_value.split("-")
                target_year = int(year_str)
                target_month = int(month_str)
                MONTH_ABBRS = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
                               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
                target_abbr = MONTH_ABBRS[target_month]

                result = await self.page.evaluate("""
                (args) => {
                    const { targetAbbr, targetYear } = args;
                    const MONTH_ABBRS = ['Jan','Feb','Mar','Apr','May','Jun',
                                        'Jul','Aug','Sep','Oct','Nov','Dec'];

                    const isVisible = el => {
                        const s = window.getComputedStyle(el);
                        return s.display !== 'none' && s.visibility !== 'hidden' && el.offsetWidth > 0;
                    };

                    // Confirm a month-grid picker is open
                    const allVisible = Array.from(document.querySelectorAll('*')).filter(isVisible);
                    const monthButtons = allVisible.filter(el => {
                        const text = (el.innerText || el.textContent || '').trim();
                        return MONTH_ABBRS.includes(text) && el.children.length === 0;
                    });
                    if (monthButtons.length < 3) return false;  // No month picker visible

                    // Navigate year if current displayed year differs from target
                    const yearEls = allVisible.filter(el => {
                        const text = (el.innerText || el.textContent || '').trim();
                        return /^20\\d{2}$/.test(text) && el.children.length === 0;
                    });
                    if (yearEls.length > 0) {
                        const currentYear = parseInt(yearEls[0].textContent.trim(), 10);
                        const diff = targetYear - currentYear;
                        if (diff !== 0) {
                            // Find prev/next year nav buttons near the year display
                            const parent = yearEls[0].parentElement || document.body;
                            const navCandidates = Array.from(parent.querySelectorAll(
                                'button, [role="button"], [class*="prev"], [class*="next"], [class*="arrow"]'
                            )).filter(isVisible);

                            // Heuristic: left-side candidate = prev, right-side = next
                            const yearX = yearEls[0].getBoundingClientRect().left;
                            const prevBtn = navCandidates.find(b => b.getBoundingClientRect().right < yearX);
                            const nextBtn = [...navCandidates].reverse().find(b => b.getBoundingClientRect().left > yearX + yearEls[0].offsetWidth);

                            const btn = diff < 0 ? prevBtn : nextBtn;
                            if (btn) {
                                for (let i = 0; i < Math.abs(diff); i++) btn.click();
                            }
                        }
                    }

                    // Click the target month abbreviation
                    const target = allVisible.find(el => {
                        const text = (el.innerText || el.textContent || '').trim();
                        return text === targetAbbr && el.children.length === 0;
                    });
                    if (target) { target.click(); return true; }
                    return false;
                }
                """, {"targetAbbr": target_abbr, "targetYear": target_year})

                if result:
                    await asyncio.sleep(0.3)
                    return True

            elif el_type == "date" and re.match(r'^\d{4}-\d{2}-\d{2}$', formatted_value):
                year_str, month_str, day_str = formatted_value.split("-")
                target_year = int(year_str)
                target_month = int(month_str)
                target_day = int(day_str)
                MONTH_NAMES_FULL = ["", "January", "February", "March", "April", "May", "June",
                                    "July", "August", "September", "October", "November", "December"]
                MONTH_NAMES_SHORT = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
                                     "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

                result = await self.page.evaluate("""
                (args) => {
                    const { targetYear, targetMonth, targetDay, fullNames, shortNames } = args;

                    const isVisible = el => {
                        const s = window.getComputedStyle(el);
                        return s.display !== 'none' && s.visibility !== 'hidden' && el.offsetWidth > 0;
                    };

                    const allVisible = Array.from(document.querySelectorAll('*')).filter(isVisible);

                    // Detect date picker: look for gridcells or day-number table cells
                    const hasDayGrid = allVisible.some(el =>
                        el.getAttribute('role') === 'gridcell' ||
                        (el.tagName === 'TD' && /^\\d{1,2}$/.test((el.innerText || '').trim()))
                    );
                    if (!hasDayGrid) return false;

                    // Navigate to the correct month/year using prev/next buttons
                    const allNames = [...fullNames.slice(1), ...shortNames.slice(1)];
                    const monthHeaderEls = allVisible.filter(el => {
                        const text = (el.innerText || el.textContent || '').trim();
                        return allNames.some(name => text.includes(name)) && el.offsetHeight < 60;
                    });

                    if (monthHeaderEls.length > 0) {
                        const header = monthHeaderEls[0];
                        const headerText = header.innerText || header.textContent || '';
                        const isTargetMonth =
                            headerText.includes(fullNames[targetMonth]) ||
                            headerText.includes(shortNames[targetMonth]);
                        const isTargetYear = headerText.includes(String(targetYear));

                        if (!isTargetMonth || !isTargetYear) {
                            // Find navigation buttons
                            const navArea = header.parentElement || header.closest('[class*="header"]') || document.body;
                            const navBtns = Array.from(navArea.querySelectorAll(
                                'button, [role="button"]'
                            )).filter(isVisible);
                            const headerX = header.getBoundingClientRect().left + header.offsetWidth / 2;
                            const prevBtn = navBtns.find(b => b.getBoundingClientRect().right < headerX - 20);
                            const nextBtn = [...navBtns].reverse().find(b => b.getBoundingClientRect().left > headerX + 20);

                            // Simple month offset navigation (max 24 months to avoid infinite loop)
                            const currentMonthIdx = allNames.findIndex(n => headerText.includes(n));
                            let attempts = 24;
                            while (attempts-- > 0) {
                                const txt = (header.innerText || header.textContent || '');
                                const matchMonth = fullNames.slice(1).findIndex(n => txt.includes(n)) + 1 ||
                                                  shortNames.slice(1).findIndex(n => txt.includes(n)) + 1;
                                const matchYear = parseInt((txt.match(/20\\d{2}/) || ['0'])[0], 10);
                                if (matchMonth === targetMonth && matchYear === targetYear) break;
                                const needNext = (matchYear < targetYear) ||
                                                 (matchYear === targetYear && matchMonth < targetMonth);
                                const btn = needNext ? nextBtn : prevBtn;
                                if (!btn) break;
                                btn.click();
                            }
                        }
                    }

                    // Click the target day cell
                    const dayCells = allVisible.filter(el => {
                        const text = (el.innerText || el.textContent || '').trim();
                        return text === String(targetDay) &&
                            (el.tagName === 'TD' || el.tagName === 'BUTTON' ||
                             el.getAttribute('role') === 'gridcell') &&
                            el.children.length === 0;
                    });
                    if (dayCells.length > 0) {
                        dayCells[0].click();
                        return true;
                    }
                    return false;
                }
                """, {
                    "targetYear": target_year,
                    "targetMonth": target_month,
                    "targetDay": target_day,
                    "fullNames": MONTH_NAMES_FULL,
                    "shortNames": MONTH_NAMES_SHORT
                })

                if result:
                    await asyncio.sleep(0.3)
                    return True

            # For week pickers or unmatched types, attempt to close any open popup via Escape
            # so the native fill value takes effect without UI interference.
            try:
                await self.page.keyboard.press("Escape")
            except Exception:
                pass

        except Exception as e:
            logger.debug(f"Calendar picker interaction error: {e}")

        return False

    async def execute_intent(self, intent_text: str) -> str:

        """
        Main entry point for executing an intent on the DOM.
        """
        logger.info(f"DOMAgent executing intent: '{intent_text}'")
        
        # Dismiss open notification popover if present before any interaction
        try:
            view_all_loc = self.page.locator("button:has-text('View all notifications'), a:has-text('View all notifications')").first
            if await view_all_loc.count() > 0 and await view_all_loc.is_visible():
                logger.info("Notifications popover detected open. Dismissing it by clicking the notifications bell.")
                bell_loc = self.page.locator("button:has-text('View notifications'), button[aria-label*='notification' i]").first
                if await bell_loc.count() > 0:
                    await bell_loc.click(timeout=1000)
                    await asyncio.sleep(0.3)
                else:
                    await self.page.keyboard.press("Escape")
                    await asyncio.sleep(0.3)
        except Exception as e:
            logger.debug(f"Error dismissing notifications popover: {e}")
        
        # 1. Fetch current snapshot
        page_context_service.invalidate()
        snapshot = await page_context_service.get_snapshot()
        if not snapshot or not snapshot.elements:
            return "Failed to get interactive elements from page."

        # 2. Try deterministic local execution first for quick, high-precision actions
        det_res = await self.execute_intent_deterministically(intent_text, snapshot)
        if not det_res.startswith("Could not determine DOM action"):
            return det_res

        # 3. Try LLM-based execution if enabled and ready
        if llm_service.is_ready:
            filtered_elements = snapshot.elements
            cmd = intent_text.lower().strip()
            # Stricter filtering: exclude header/navigation/notification elements if targeting a specific record/request generically
            is_targeting_record = False
            _words = cmd.split()
            if len(_words) >= 2:
                _action_verbs = {"view", "edit", "update", "delete", "show", "inspect", "open", "change"}
                if _words[0] in _action_verbs:
                    _target_phrase = " ".join(_words[1:])
                    _nav_notif_words = {"notification", "bell", "profile", "header", "navbar", "navigation", "nav", "menu", "sidebar", "toast", "alert"}
                    if not any(w in _target_phrase for w in _nav_notif_words):
                        is_targeting_record = True

            if is_targeting_record:
                filtered_elements = [
                    el for el in snapshot.elements
                    if not getattr(el, "is_nav_header_or_notification", False)
                ]
            res = await self.execute_intent_with_llm(intent_text, filtered_elements)
            if res:
                return res

        # 4. Fallback to the message returned by deterministic execution
        return det_res

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
                if getattr(el, "context", ""): desc += f", context='{el.context}'"
                elements_desc.append(desc)
                
            elements_str = "\n".join(elements_desc)
            
            system_prompt = (
                "You are an AI assistant controlling a web browser. Your job is to select the correct elements to interact with based on the user's command.\n"
                "Each element is listed with its attributes, including an optional 'context' attribute which contains the text of its surrounding table row, list item, or container.\n"
                "If the user command references specific data (such as an employee's name, an amount, a status, or a date), look for elements where the 'context' attribute contains those values, and choose the action (e.g. click 'View' or 'Edit') associated with that context.\n"
                "Do not click header/navigation bar buttons or global profile/notification menus (like 'View notifications' or profile dropdowns) when the user specifies a specific item, record, request, or row.\n\n"
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
                "IMPORTANT CONSTRAINT:\n"
                "Do NOT perform any actions that are not explicitly requested by the user's command.\n"
                "For example, if the user command is 'Advance amount ten thousand', you should ONLY generate actions to fill the 'Advance Amount' field with '10000'.\n"
                "Do NOT click any 'Submit', 'Request', or 'Save' buttons, do NOT fill other fields like 'Justification', and do NOT click any container buttons like '+ New Advance Request' unless the user explicitly requested that action.\n"
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
                    
                lbl = _get_element_label(el)
                if action_type == "click":
                    await BrowserEngine()._animate_action(self.page, handle, "click")
                    await self._click_element(handle)
                    results.append(f"Clicked {lbl}")
                elif action_type == "fill":
                    val = act.get("value", "")
                    await BrowserEngine()._animate_action(self.page, handle, "click")
                    await self._click_element(handle)
                    actual_filled = await self._fill_input(handle, el, val)
                    results.append(f"Entered '{actual_filled}' into {lbl}")
                elif action_type == "select":
                    await BrowserEngine()._animate_action(self.page, handle, "click")
                    await self._click_element(handle)
                    await asyncio.sleep(0.5)
                    val = act.get("value", "")
                    loc = self.page.get_by_role("option", name=re.compile(val, re.IGNORECASE)).first
                    if await loc.count() > 0:
                        await self._click_element(loc)
                        results.append(f"Selected option '{val}' in {lbl}")
                    else:
                        await self.page.keyboard.type(val)
                        await self.page.keyboard.press("Enter")
                        results.append(f"Typed option '{val}' into {lbl}")
                        
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
                    await BrowserEngine()._animate_action(self.page, handle, "click")
                    await self._click_element(handle)
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
                                await BrowserEngine()._animate_action(self.page, opt_handle, "click")
                                await self._click_element(opt_handle)
                                return f"Selected option '{option}' from '{dropdown}'."
                    
                    # Direct click fallback
                    try:
                        loc = self.page.get_by_role("option", name=re.compile(option, re.IGNORECASE)).first
                        if await loc.count() > 0:
                            await self._click_element(loc)
                            return f"Selected option '{option}' from '{dropdown}'."
                        loc = self.page.locator(f"li:has-text('{option}')").first
                        if await loc.count() > 0:
                            await self._click_element(loc)
                            return f"Selected option '{option}' from '{dropdown}'."
                    except Exception:
                        pass
            
            # Direct clickable option fallback (segmented control / tabs / tab buttons)
            clickable_candidates = snapshot.clickable()
            direct_el = find_best_element(clickable_candidates, option, min_score=50)
            if direct_el:
                direct_handle = await self.get_element_handle(direct_el)
                if direct_handle:
                    await BrowserEngine()._animate_action(self.page, direct_handle, "click")
                    await self._click_element(direct_handle)
                    return f"Clicked '{option}' directly."
  
        # 2. Check type/fill/write/set target patterns (e.g. "type text into field", "set field to value", "deduction start month jun")
        field_target = None
        fill_value = None
        
        # Pattern A: explicit verbs like "set deduction start month to jun" or "type jun in deduction start month"
        m = re.match(r'^(?:set|change|fill)\s+(.+?)\s+(?:to|with|as)\s+(.+)$', cmd)
        if m:
            field_target = m.group(1).strip()
            fill_value = m.group(2).strip()
        else:
            m = re.match(r'^(?:type|write|enter)\s+(.+?)\s+(?:into|in|to)\s+(?:the\s+)?(.+)$', cmd)
            if m:
                fill_value = m.group(1).strip()
                field_target = m.group(2).strip()
            else:
                m = re.match(r'^(.+?)\s+(?:is|to|set\s+to)\s+(.+)$', cmd)
                if m:
                    field_target = m.group(1).strip()
                    fill_value = m.group(2).strip()

        # Pattern B: implicit matching of "[field_label] [value]" (e.g. "deduction start month jun")
        if not field_target and not fill_value:
            for el in snapshot.inputs():
                label = (el.text or el.name or el.placeholder or el.el_id or "").lower().strip()
                if label and len(label) >= 3:
                    # Check if cmd starts with label (e.g. "deduction start month jun" starts with "deduction start month")
                    if cmd.startswith(label + " "):
                        field_target = label
                        fill_value = cmd[len(label):].strip()
                        break
                    # Also check without common filler words in the label
                    clean_label = label.replace("optional", "").replace("*", "").strip()
                    if clean_label and len(clean_label) >= 3 and cmd.startswith(clean_label + " "):
                        field_target = clean_label
                        fill_value = cmd[len(clean_label):].strip()
                        break

        if field_target and fill_value:
            # Clean up target and value
            field_target = field_target.replace("the", "").strip()
            # Find the best input/select element
            candidates = [el for el in snapshot.elements if el.role in ("input", "textbox", "textarea", "combobox", "select") or el.tag in ("input", "textarea", "select")]
            el = find_best_element(candidates, field_target, min_score=40, roles=None)
            if el:
                handle = await self.get_element_handle(el)
                
                # Fallback: if element_handle lookup failed (e.g. label-derived name doesn't match
                # any HTML name/aria-label attribute), try Playwright's get_by_label directly.
                if not handle and el.name:
                    try:
                        label_loc = self.page.get_by_label(el.name, exact=False).first
                        if await label_loc.count() > 0:
                            handle = await label_loc.element_handle()
                            logger.info(f"Resolved '{el.name}' via get_by_label fallback")
                    except Exception as e:
                        logger.debug(f"get_by_label fallback failed for '{el.name}': {e}")
                
                if handle:
                    await BrowserEngine()._animate_action(self.page, handle, "click")
                    await self._click_element(handle)
                    
                    # If it's a select/combobox, handle option selection
                    if el.role in ("combobox", "select") or el.tag == "select":
                        await asyncio.sleep(0.5)
                        # Check for matching options in the DOM
                        page_context_service.invalidate()
                        fresh_snapshot = await page_context_service.get_snapshot()
                        if fresh_snapshot:
                            opt_candidates = [o for o in fresh_snapshot.elements if o.role in ("option", "listitem") or o.tag in ("option", "li")]
                            opt_el = find_best_element(opt_candidates, fill_value, min_score=40, roles=None)
                            if opt_el:
                                opt_handle = await self.get_element_handle(opt_el)
                                if opt_handle:
                                    await BrowserEngine()._animate_action(self.page, opt_handle, "click")
                                    await self._click_element(opt_handle)
                                    return f"Selected '{fill_value}' for '{field_target}'."
                        
                        # Fallback: type and enter
                        await self.page.keyboard.type(fill_value)
                        await self.page.keyboard.press("Enter")
                        return f"Typed '{fill_value}' and pressed Enter for '{field_target}'."
                    else:
                        # Otherwise fill the input
                        actual_filled = await self._fill_input(handle, el, fill_value)
                        return f"Filled '{field_target}' with '{actual_filled}'."
  
        # 3. Check click target pattern (e.g. "click submit")
        m = re.match(r'^(?:click|tap|press|hit|view|show|inspect|edit|update)\s+(?:on\s+)?(?:the\s+)?(.+)$', cmd)
        if m:
            action_verb = cmd.split()[0]
            target = m.group(1).strip()
            
            # Try to find a contextual match for lists/tables first
            best_el = None
            if action_verb in ("view", "show", "inspect", "edit", "update"):
                q_clean = target.replace("employee", "").replace("request", "").replace("the", "").replace("advance", "").strip()
                q_words = [w for w in q_clean.split() if w]
                if q_words:
                    candidates = [
                        el for el in snapshot.clickable()
                        if (
                            el.text.lower().strip() == action_verb
                            or el.name.lower().strip() == action_verb
                            or el.text.lower().strip().startswith(action_verb + " ")
                            or el.name.lower().strip().startswith(action_verb + " ")
                        )
                    ]
                    best_score = 0
                    for el in candidates:
                        # Exclude navigation and notification elements when looking for a specific table record
                        if getattr(el, "is_nav_header_or_notification", False):
                            continue
                            
                        context = getattr(el, "context", "").lower()
                        if context:
                            score = 0
                            for w in q_words:
                                if w in context:
                                    score += 2
                                elif any(len(part) > 2 and (part in w or w in part) for part in context.split()):
                                    score += 1
                            if score > best_score:
                                best_score = score
                                best_el = el
                                
            if best_el:
                logger.info(f"Deterministic contextual match found for '{action_verb}' with context matching '{target}'")
                el = best_el
            else:
                el = find_best_element(snapshot.clickable(), target, min_score=40)
                
            if el:
                handle = await self.get_element_handle(el)
                if handle:
                    await BrowserEngine()._animate_action(self.page, handle, "click")
                    await self._click_element(handle)
                    lbl = _get_element_label(el)
                    return f"Clicked {lbl}."

        # 4. Check bare type pattern (e.g. "type hello")
        m = re.match(r'^(?:type|write|enter)\s+(.+)$', cmd)
        if m:
            value = m.group(1).strip()
            await self.page.keyboard.type(value)
            return f"Typed '{value}' into focused element."

        return f"Could not determine DOM action to execute for command: '{intent_text}'."

    async def fill_form(self, context: str = "") -> str:
        """
        Fills the form on the active page based on the provided context.
        """
        prompt = f"fill the form with: {context}" if context else "fill the form"
        return await self.execute_intent(prompt)
