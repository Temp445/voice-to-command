"""
ACE Voice Controller — Command Intent Registry
Defines all built-in intents with regex patterns and wires them to the automation executor.
"""

import re
from app.services.command_service import Intent, command_service
from loguru import logger


# ─── Lazy import executor to avoid circular deps ─────────────────────────────
async def _get_executor():
    from automation.executor import ActionExecutor
    return ActionExecutor()


# ─── Intent Handlers ─────────────────────────────────────────────────────────

# ── Known Web App URL Mappings ───────────────────────────────────────────────
# If a desktop app is not found, check this table and open the URL in the browser instead.
WEB_APP_URLS: dict[str, str] = {
    "gmail":         "https://mail.google.com/",
    "google sheets": "https://sheets.google.com/",
    "google docs":   "https://docs.google.com/",
    "youtube":       "https://www.youtube.com/",
    "notion":        "https://www.notion.so/",
    "figma":         "https://www.figma.com/",
    "jira":          "https://jira.atlassian.com/",
    "github":        "https://github.com/",
    "slack":         "https://slack.com/",
    "whatsapp":      "https://web.whatsapp.com/",
}

async def handle_open_app(app: str = "", text: str = "", **_) -> str:
    from automation.desktop.app_controller import AppController
    ctrl = AppController()
    app_name = app.strip()
    try:
        res = await ctrl.open_application(app_name)
    except Exception as e:
        res = str(e)
    
    if "not found" in res.lower() or "could not find" in res.lower() or "application" in res.lower():
        # Check if it's a known web app
        app_lower = app_name.lower()
        url = None
        for key, web_url in WEB_APP_URLS.items():
            if key in app_lower or app_lower in key:
                url = web_url
                break
        
        if url:
            logger.info(f"Desktop app '{app_name}' not found. Opening web URL: {url}")
            from automation.browser.browser_controller import BrowserController
            bc = BrowserController()
            nav_result = await bc.navigate(url)
            return f"'{app_name}' is not installed. Opened {url} in browser instead."
            
        # Fallback to conversational search prompt
        return f"PENDING_SEARCH_APP:{app_name}"

    return res


async def handle_dynamic_dom_action(action: str = "", **_) -> str:
    from automation.browser.browser_controller import BrowserController
    try:
        from automation.browser.dom_agent import DOMAgent
        bc = BrowserController()
        if bc.engine._playwright is None:
            return "No active browser session to perform dynamic action."
        page = await bc._ensure_page()
        agent = DOMAgent(page)
        return await agent.execute_intent(action)
    except Exception as e:
        return f"Failed to execute dynamic DOM action: {e}"



async def handle_close_app(app: str = "", **_) -> str:
    from automation.desktop.app_controller import AppController
    return await AppController().close_application(app.strip())


async def handle_close_heavy_apps(**_) -> str:
    from automation.desktop.app_controller import AppController
    return await AppController().close_heavy_applications(threshold_mb=500)


async def handle_search_google(query: str = "", browser: str | None = None, text: str = "", **_) -> str:
    from automation.browser.browser_controller import BrowserController
    from automation.browser.browser_engine import BrowserEngine
    import re
    
    ctrl = BrowserController()
    query = query.strip()
    
    tab_match = re.search(r'(?:\s+)?in\s+(?:a\s+|the\s+)?new\s+tab$', query, re.IGNORECASE)
    text_tab_match = re.search(r'in\s+(?:a\s+|the\s+)?new\s+tab', text, re.IGNORECASE)
    
    if tab_match or text_tab_match:
        if tab_match:
            query = query[:tab_match.start()].strip()
        await ctrl.new_tab()
    
    # If the user says "search [URL]", just navigate to it directly
    if re.match(r"^(?:https?://)?[\w\-\.]+\.\w{2,}(?:/\S*)?$", query):
        url = query if query.startswith("http") else f"https://{query}"
        logger.info(f"Query looks like a URL, navigating directly to: {url}")
        return await BrowserEngine().navigate(url)
        
    logger.info(f"Searching Google for: '{query}'")
    return await ctrl.search_google(query)


async def handle_search_youtube(query: str = "", text: str = "", **_) -> str:
    from automation.browser.browser_controller import BrowserController
    import re
    ctrl = BrowserController()
    query = query.strip()
    
    tab_match = re.search(r'(?:\s+)?in\s+(?:a\s+|the\s+)?new\s+tab$', query, re.IGNORECASE)
    text_tab_match = re.search(r'in\s+(?:a\s+|the\s+)?new\s+tab', text, re.IGNORECASE)
    
    if tab_match or text_tab_match:
        if tab_match:
            query = query[:tab_match.start()].strip()
        await ctrl.new_tab()
        
    logger.info(f"Searching YouTube for: '{query}'")
    return await ctrl.search_youtube(query)


async def handle_open_website(url: str = "", **_) -> str:
    from automation.browser.browser_engine import BrowserEngine
    url = url.strip()
    if not url:
        return "Please specify a website to open."
    if "." not in url and not url.startswith("http"):
        url = url + ".com"
    return await BrowserEngine().navigate(url)

async def handle_browser_play_pause(**_) -> str:
    from automation.browser.browser_engine import BrowserEngine
    return await BrowserEngine().play_pause()

async def handle_browser_go_back(**_) -> str:
    from automation.browser.browser_engine import BrowserEngine
    return await BrowserEngine().go_back()

async def handle_browser_refresh(**_) -> str:
    from automation.browser.browser_controller import BrowserController
    try:
        ctrl = BrowserController()
        page = await ctrl._ensure_page()
        await page.reload()
        return "Page refreshed."
    except Exception as e:
        return f"Failed to refresh the page: {e}"

async def handle_browser_click_result(index: str = "first", **_) -> str:
    from automation.browser.browser_controller import BrowserController
    
    mapping = {
        "first": 0, "1st": 0, "1": 0,
        "second": 1, "2nd": 1, "2": 1,
        "third": 2, "3rd": 2, "3": 2,
        "fourth": 3, "4th": 3, "4": 3,
        "fifth": 4, "5th": 4, "5": 4,
        "sixth": 5, "6th": 5, "6": 5,
        "seventh": 6, "7th": 6, "7": 6,
        "eighth": 7, "8th": 7, "8": 7,
        "ninth": 8, "9th": 8, "9": 8,
        "tenth": 9, "10th": 9, "10": 9
    }
    idx = mapping.get(index.lower().strip(), 0)
    return await BrowserController().click_search_result(idx)

async def handle_browser_new_tab(**_) -> str:
    from automation.browser.browser_controller import BrowserController
    return await BrowserController().new_tab()

async def handle_browser_switch_tab(tab_identifier: str = "last", **_) -> str:
    from automation.browser.browser_controller import BrowserController
    import re
    ctrl = BrowserController()
    
    tid = tab_identifier.lower().strip()
    if tid == "last":
        return await ctrl.switch_to_last_tab()
        
    mapping = {
        "first": 0, "1st": 0, "1": 0,
        "second": 1, "2nd": 1, "2": 1,
        "third": 2, "3rd": 2, "3": 2,
        "fourth": 3, "4th": 3, "4": 3,
        "fifth": 4, "5th": 4, "5": 4,
        "sixth": 5, "6th": 5, "6": 5,
        "seventh": 6, "7th": 6, "7": 6,
        "eighth": 7, "8th": 7, "8": 7,
        "ninth": 8, "9th": 8, "9": 8,
        "tenth": 9, "10th": 9, "10": 9
    }
    
    m = re.match(r'^(\d+)', tid)
    if m:
        idx = int(m.group(1)) - 1
    else:
        idx = mapping.get(tid)
        
    if idx is not None:
        return await ctrl.engine.switch_tab(idx)
        
    return f"Could not determine which tab to switch to from '{tab_identifier}'"

async def handle_browser_close_all_tabs(**_) -> str:
    from automation.browser.browser_controller import BrowserController
    return await BrowserController().close_all_tabs()

async def handle_browser_hover(selector: str = "", **_) -> str:
    from automation.browser.browser_controller import BrowserController
    return await BrowserController().hover(selector)

async def handle_browser_clipboard(action: str = "", **_) -> str:
    from automation.browser.browser_controller import BrowserController
    clean_action = action.strip().lower().replace(" ", "_")
    return await BrowserController().clipboard_action(clean_action)

async def handle_browser_scroll_variable(direction: str = "", magnitude: str = "", **_) -> str:
    from automation.browser.browser_controller import BrowserController
    return await BrowserController().scroll_amount(direction.strip(), magnitude.strip())

async def handle_browser_fill_form(context: str = "", **_) -> str:
    from automation.browser.dom_agent import DOMAgent
    from automation.browser.browser_controller import BrowserController
    ctrl = BrowserController()
    page = await ctrl._ensure_page()
    return await DOMAgent(page).fill_form(context)

async def handle_browser_interact_checkbox(action: str = "", **_) -> str:
    from automation.browser.dom_agent import DOMAgent
    from automation.browser.browser_controller import BrowserController
    ctrl = BrowserController()
    page = await ctrl._ensure_page()
    return await DOMAgent(page).execute_intent(f"{action} the checkbox")

async def handle_browser_list_options(element: str = "", **_) -> str:
    from automation.browser.browser_controller import BrowserController
    import re
    ctrl = BrowserController()
    page = await ctrl._ensure_page()
    
    try:
        # 1. Try semantic combobox
        combobox = page.get_by_role('combobox', name=re.compile(element, re.IGNORECASE))
        if await combobox.count() == 1:
            await combobox.first.click(force=True)
            return f"Opened {element} dropdown."
        # 2. Ultimate fallback to DOM Agent
        from automation.browser.dom_agent import DOMAgent
        agent = DOMAgent(page)
        res = await agent.execute_intent(f"click the {element} dropdown")
        if "couldn't find" not in res.lower() and "failed" not in res.lower():
            return res
            
        return f"Could not find a dropdown matching '{element}' on the page."
    except Exception as e:
        return f"Failed to open options for {element}: {str(e)}"

async def handle_browser_select_option(option: str = "", **_) -> str:
    from automation.desktop.app_controller import AppController
    import re
    
    clean_option = re.sub(r"^\s*(the file|file|the folder|folder)\s+", "", option, flags=re.IGNORECASE).strip()
    if AppController().navigate_file_dialog(clean_option):
        return f"Selected '{clean_option}' in the file dialog."

    from automation.browser.browser_controller import BrowserController
    ctrl = BrowserController()
    page = await ctrl._ensure_page()
    
    try:
        opt_lower = option.strip().lower()
        
        # Look for standard accessible dropdown options (React/MUI/custom)
        options = page.get_by_role('option')
        count = await options.count()
        
        if count == 0:
            # Fallback to general list items if ARIA roles are missing
            options = page.locator('li')
            count = await options.count()
            
        if count == 0:
            from automation.browser.dom_agent import DOMAgent
            agent = DOMAgent(page)
            dom_res = await agent.execute_intent(f"select {option}")
            if "couldn't find" not in dom_res.lower() and "failed" not in dom_res.lower():
                return dom_res
            return "No dropdown options are currently visible on the screen. Please open the dropdown first."
            
        async def _click_or_select(loc):
            import asyncio
            tag_name = await loc.evaluate("el => el.tagName")
            if tag_name.upper() == "OPTION":
                val = await loc.get_attribute("value")
                parent = page.locator("select").filter(has=loc)
                if await parent.count() > 0:
                    if val is not None:
                        await parent.first.select_option(value=val)
                    else:
                        await parent.first.select_option(label=await loc.inner_text())
                else:
                    await loc.evaluate("""(el) => {
                        const select = el.closest('select');
                        if (select) {
                            select.value = el.value;
                            select.dispatchEvent(new Event('change', { bubbles: true }));
                        }
                    }""")
            else:
                await loc.click(force=True)
                
            # Auto-close any lingering custom dropdowns (like MUI or React-Select)
            await asyncio.sleep(0.1)
            await page.keyboard.press("Escape")

        # Positional selection
        if opt_lower in ["last", "last option", "the last"]:
            await _click_or_select(options.last)
            return "Selected the last option."
        elif opt_lower in ["first", "first option", "the first"]:
            await _click_or_select(options.first)
            return "Selected the first option."
        else:
            # Text-based selection
            target = page.get_by_role('option', name=re.compile(opt_lower, re.IGNORECASE))
            if await target.count() > 0:
                await _click_or_select(target.first)
                return f"Selected option: {option}"
                
            # Fallback text search
            target = page.locator(f"text=/{opt_lower}/i").filter(has_not=page.locator("body"))
            if await target.count() > 0:
                await _click_or_select(target.last) # last usually hits the deepest element
                return f"Selected option: {option}"
                
            from automation.browser.dom_agent import DOMAgent
            agent = DOMAgent(page)
            dom_res = await agent.execute_intent(f"select {option}")
            if "couldn't find" not in dom_res.lower() and "failed" not in dom_res.lower():
                return dom_res
                
            return f"Could not find an option matching '{option}'."
            
    except Exception as e:
        return f"Failed to select option '{option}': {str(e)}"

async def handle_browser_summarize_page(**_) -> str:
    from automation.browser.browser_controller import BrowserController
    from app.services.llm.llm_service import llm_service
    content = await BrowserController().extract_page_content()
    prompt = f"Please summarize the following webpage content:\n\n{content[:5000]}"
    summary = await llm_service.generate(prompt)
    return f"Summary:\n{summary}"

async def handle_browser_full_screenshot(**_) -> str:
    from automation.browser.browser_controller import BrowserController
    import os
    path = os.path.join(os.path.expandvars(r"%LOCALAPPDATA%\ACE\BrowserProfile"), "screenshots", "full_page.png")
    return await BrowserController().screenshot(path, full_page=True)

async def handle_browser_window_state(state: str = "", **_) -> str:
    from automation.browser.browser_controller import BrowserController
    state = state.strip().lower()
    if state == "restart":
        return await BrowserController().restart_browser()
    return await BrowserController().set_window_state(state)

async def handle_browser_clear_marks(**_) -> str:
    from automation.browser.browser_controller import BrowserController
    return await BrowserController().clear_marks()

async def handle_crm_clear_search(text: str = "", **_) -> str:
    """
    Clears the active search / filter input or date filter on the current CRM page.
    Prioritizes 'Clear dates' if the user specifically asked to clear dates.
    """
    import asyncio
    from automation.browser.browser_controller import BrowserController
    from loguru import logger

    ctrl = BrowserController()
    page = await ctrl._ensure_page()

    text_lower = text.lower()
    is_date_clear = "date" in text_lower

    # ── Layer 1: Date Filter Priority ─────────────────────────────────────────
    if is_date_clear:
        date_clear_candidates = [
            "text='Clear dates'",
            "text='Clear Dates'",
            "button:has-text('Clear dates')",
            "[aria-label*='clear date' i]"
        ]
        for sel in date_clear_candidates:
            try:
                loc = page.locator(sel).first
                if await loc.is_visible():
                    await loc.click(timeout=2000)
                    await asyncio.sleep(0.4)
                    logger.info("[ClearSearch] Cleared dates via button: %s", sel)
                    return "Date filter cleared."
            except Exception as e:
                logger.error(f"Error: {e}")
                pass

    # ── Layer 2: Direct clear of the text search input ────────────────────────
    # Only run this if we aren't specifically targeting dates, or if the date clear failed
    if not is_date_clear or "search" in text_lower:
        selectors = [
            "input[type='search']",
            "input[placeholder*='Search' i]",
            "input[placeholder*='search' i]",
            "input[class*='search' i]",
            "input[id*='search' i]",
            "input[name*='search' i]",
        ]
        for sel in selectors:
            try:
                loc = page.locator(sel).first
                if await loc.is_visible():
                    await loc.click(click_count=3, timeout=2000)
                    await loc.fill("", timeout=2000)
                    await page.keyboard.press("Enter")
                    await asyncio.sleep(0.4)
                    logger.info("[ClearSearch] Cleared search input via selector: %s", sel)
                    return "Search cleared."
            except Exception as e:
                logger.error(f"Error: {e}")
                pass

    # ── Layer 3: Look for a general close / clear / reset button ──────────────
    clear_candidates = [
        "button:has-text('Clear')",
        "button:has-text('Reset')",
        "[aria-label*='clear' i]",
        "[aria-label*='reset' i]",
        "[title*='clear' i]",
        ".clear-btn", ".reset-btn",
        "button >> text=×",
        "button >> text=✕",
    ]
    for sel in clear_candidates:
        try:
            loc = page.locator(sel).first
            if await loc.is_visible():
                await loc.click(timeout=2000)
                await asyncio.sleep(0.4)
                logger.info("[ClearSearch] Cleared via button: %s", sel)
                return "Filter cleared."
        except Exception as e:
            logger.error(f"Error: {e}")
            pass

    # ── Layer 4: DOMAgent fallback ────────────────────────────────────────────
    try:
        from automation.browser.dom_agent import DOMAgent
        agent = DOMAgent(page)
        fallback_prompt = "click the clear dates text button" if is_date_clear else "clear the search input or click the clear search button"
        res = await agent.execute_intent(fallback_prompt)
        if res and not any(x in res.lower() for x in ["couldn't", "failed", "could not"]):
            return "Filter cleared via agent."
    except Exception as e:
        logger.warning("[ClearSearch] DOMAgent fallback failed: %s", e)

    return "Could not find a search input or filter to clear on this page."

async def handle_browser_double_click(**_) -> str:
    from automation.browser.browser_controller import BrowserController
    return await BrowserController().double_click()

async def handle_browser_right_click(**_) -> str:
    from automation.browser.browser_controller import BrowserController
    return await BrowserController().right_click()

async def handle_browser_press_key(key: str = "", **_) -> str:
    from automation.browser.browser_controller import BrowserController
    return await BrowserController().press_key(key.strip())

async def handle_browser_wait_for(target: str = "", **_) -> str:
    from automation.browser.browser_controller import BrowserController
    return await BrowserController().wait_for(target.strip())

async def handle_browser_download(**_) -> str:
    from automation.browser.browser_controller import BrowserController
    return await BrowserController().download_file()

async def handle_browser_upload(**_) -> str:
    from automation.browser.dom_agent import DOMAgent
    from automation.browser.browser_controller import BrowserController
    ctrl = BrowserController()
    try:
        page = await ctrl._ensure_page()
        agent = DOMAgent(page)
        # Force a click on the file area to open the native OS file dialog for visual browsing
        # Do NOT use the word "upload" in this string, or DOMAgent will intercept it as an auto-upload action!
        res = await agent.execute_intent("click the file drop area")
        if "couldn't find" not in res.lower() and "failed" not in res.lower():
            return "Opened file upload dialog."
        return res
    except Exception as e:
        return f"Failed to open upload dialog: {e}"

# ---> ADD THE NEW FUNCTION HERE <---
async def handle_browser_paginate(direction: str = "", page_num: str = "", **_) -> str:
    from automation.browser.browser_controller import BrowserController
    from loguru import logger
    import asyncio

    ctrl = BrowserController()
    page = await ctrl._ensure_page()

    direction = direction.lower().strip()
    page_num = page_num.strip()

    target_selectors = []
    action_desc = ""

    if page_num:
        target_selectors = [
            f"button:has-text('{page_num}')",
            f"a:has-text('{page_num}')",
            f"[aria-label*='page {page_num}' i]",
            f"[title*='page {page_num}' i]"
        ]
        action_desc = f"page {page_num}"
    elif direction in ["next", "forward"]:
        target_selectors = [
            "[aria-label*='next page' i]",
            "[title*='next page' i]",
            "button:has-text('>')",
            "button:has-text('Next')",
            ".next-page"
        ]
        action_desc = "next page"
    elif direction in ["prev", "previous", "back"]:
        target_selectors = [
            "[aria-label*='previous page' i]",
            "[title*='previous page' i]",
            "button:has-text('<')",
            "button:has-text('Prev')",
            ".prev-page"
        ]
        action_desc = "previous page"
    elif direction == "first":
        target_selectors = [
            "[aria-label*='first page' i]",
            "[title*='first page' i]",
            "button:has-text('<<')",
            "button:has-text('First')"
        ]
        action_desc = "first page"
    elif direction == "last":
        target_selectors = [
            "[aria-label*='last page' i]",
            "[title*='last page' i]",
            "button:has-text('>>')",
            "button:has-text('Last')"
        ]
        action_desc = "last page"

    # Layer 1: Try native selectors
    for sel in target_selectors:
        try:
            loc = page.locator(sel)
            count = await loc.count()
            for i in range(count):
                el = loc.nth(i)
                if await el.is_visible() and not await el.is_disabled():
                    await el.click(timeout=1500)
                    await asyncio.sleep(0.5)
                    logger.info(f"[Paginate] Clicked {action_desc} via {sel}")
                    return f"Navigated to {action_desc}."
        except Exception as e:
            logger.error(f"Error: {e}")
            continue

    # Layer 2: DOMAgent Fallback
    try:
        from automation.browser.dom_agent import DOMAgent
        agent = DOMAgent(page)
        res = await agent.execute_intent(f"click the {action_desc} button in the pagination area")
        if "couldn't find" not in res.lower() and "failed" not in res.lower():
            return f"Navigated to {action_desc}."
    except Exception as e:
        logger.warning(f"[Paginate] DOMAgent fallback failed: {e}")

    return f"Could not find or click the {action_desc} button. It might be disabled or hidden."        

async def handle_crm_action(text: str = "", **_) -> str:
    from automation.browser.browser_controller import VoiceBrowserCommands
    cmd = VoiceBrowserCommands()
    return await cmd.execute(text)
async def handle_browser_date_filter(start_date: str = "", end_date: str = "", text: str = "", **kwargs) -> str:
    """
    Set a date range filter on ANY website (CRM, analytics, booking, reporting).
    Fast 3-layer strategy:
      1. Native HTML date/text inputs (direct fill)
      2. JS scan → find date display elements → click → navigate calendar → click day
      3. DOMAgent targeted prompt as last resort
    """
    import re
    import asyncio
    from automation.browser.browser_controller import BrowserController
    import logging

    logger = logging.getLogger(__name__)

    # ── Date Parsing ──────────────────────────────────────────────────────────
    MONTHS_MAP = {"jan":1,"feb":2,"mar":3,"apr":4,"may":5,"jun":6,
                  "jul":7,"aug":8,"sep":9,"oct":10,"nov":11,"dec":12}
    MONTH_NAMES = ["","January","February","March","April","May","June",
                   "July","August","September","October","November","December"]

    def _parse_date(raw: str):
        """
        Returns {dmy, iso, d, m, y} on success, or None on failure.
        """
        raw = raw.strip()
        # Strip ordinal suffixes: "4th" -> "4", "21st" -> "21"
        raw = re.sub(r"\b(\d{1,2})(st|nd|rd|th)\b", r"\1", raw, flags=re.IGNORECASE)
        # Normalize commas/extra whitespace: "May 4, 2026" -> "May 4 2026"
        raw = re.sub(r"\s*,\s*", " ", raw)
        raw = re.sub(r"\s+", " ", raw).strip()

        d = mo = y = None

        # 1. ISO: YYYY-MM-DD / YYYY/MM/DD
        m = re.match(r"^(\d{4})[\-/](\d{1,2})[\-/](\d{1,2})$", raw)
        if m:
            y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))

        # 2. DD-MM-YYYY / DD/MM/YYYY
        if d is None:
            m = re.match(r"^(\d{1,2})[\-/](\d{1,2})[\-/](\d{4})$", raw)
            if m:
                d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))

        # 3. "DD MonthName YYYY"  e.g. "4 may 2026"
        if d is None:
            m = re.match(r"^(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})$", raw, re.IGNORECASE)
            if m and m.group(2)[:3].lower() in MONTHS_MAP:
                d, mo, y = int(m.group(1)), MONTHS_MAP[m.group(2)[:3].lower()], int(m.group(3))

        # 4. "MonthName DD YYYY"  e.g. "May 4 2026"
        if d is None:
            m = re.match(r"^([A-Za-z]+)\s+(\d{1,2})\s+(\d{4})$", raw, re.IGNORECASE)
            if m and m.group(1)[:3].lower() in MONTHS_MAP:
                mo, d, y = MONTHS_MAP[m.group(1)[:3].lower()], int(m.group(2)), int(m.group(3))

        if d is None or mo is None or y is None or not (1 <= mo <= 12) or not (1 <= d <= 31):
            return None

        return {"dmy": f"{d:02d}-{mo:02d}-{y}", "iso": f"{y}-{mo:02d}-{d:02d}",
                "d": d, "m": mo, "y": y}

    # ── Spelled-out date words ───────────────────────────────────────────────
    _NUM_ONES = {"zero":0,"one":1,"two":2,"three":3,"four":4,"five":5,"six":6,"seven":7,
                 "eight":8,"nine":9,"ten":10,"eleven":11,"twelve":12,"thirteen":13,
                 "fourteen":14,"fifteen":15,"sixteen":16,"seventeen":17,"eighteen":18,
                 "nineteen":19}
    _NUM_TENS = {"twenty":20,"thirty":30,"forty":40,"fifty":50,"sixty":60,"seventy":70,
                 "eighty":80,"ninety":90}
    _ORD_ONES = {"first":1,"second":2,"third":3,"fourth":4,"fifth":5,"sixth":6,"seventh":7,
                 "eighth":8,"ninth":9,"tenth":10,"eleventh":11,"twelfth":12,"thirteenth":13,
                 "fourteenth":14,"fifteenth":15,"sixteenth":16,"seventeenth":17,
                 "eighteenth":18,"nineteenth":19}
    _ORD_TENS = {"twentieth":20,"thirtieth":30}
    _ORD_SUFFIX = {1:"first",2:"second",3:"third",4:"fourth",5:"fifth",6:"sixth",
                   7:"seventh",8:"eighth",9:"ninth"}
    _MONTH_NAME_SET = {"january","february","march","april","may","june","july",
                        "august","september","october","november","december"}
    _NUMBER_WORD_SET = set(_NUM_ONES) | set(_NUM_TENS) | {"hundred", "thousand", "and"}

    _DAY_WORDS = {}
    for _w, _v in _NUM_ONES.items():
        if 1 <= _v <= 19:
            _DAY_WORDS[_w] = _v
    for _w, _v in _NUM_TENS.items():
        _DAY_WORDS[_w] = _v
    for _w, _v in _ORD_ONES.items():
        _DAY_WORDS[_w] = _v
    for _w, _v in _ORD_TENS.items():
        _DAY_WORDS[_w] = _v
    for _tw, _tv in _NUM_TENS.items():
        for _ow, _ov in _NUM_ONES.items():
            if 1 <= _ov <= 9:
                _DAY_WORDS[f"{_tw} {_ow}"] = _tv + _ov
                _DAY_WORDS[f"{_tw} {_ORD_SUFFIX[_ov]}"] = _tv + _ov

    def _year_from_words(words):
        def parse_chunk(toks):
            if not toks:
                return None
            w0 = toks[0]
            if w0 in _NUM_TENS:
                v = _NUM_TENS[w0]
                if len(toks) > 1 and toks[1] in _NUM_ONES and 1 <= _NUM_ONES[toks[1]] <= 9:
                    return v + _NUM_ONES[toks[1]], 2
                return v, 1
            if w0 in _NUM_ONES:
                return _NUM_ONES[w0], 1
            return None

        c1 = parse_chunk(words)
        if c1:
            v1, n1 = c1
            rest = words[n1:]
            c2 = parse_chunk(rest)
            if c2 and n1 + c2[1] == len(words):
                v2, _ = c2
                year = v1 * 100 + v2
                if 1000 <= year <= 2200:
                    return year

        if "thousand" in words:
            ti = words.index("thousand")
            left = [w for w in words[:ti] if w != "and"]
            right = [w for w in words[ti + 1:] if w != "and"]
            left_val = sum(_NUM_ONES.get(w, 0) for w in left) or 1
            rc = parse_chunk(right) if right else None
            right_val = rc[0] if rc else 0
            year = left_val * 1000 + right_val
            if 1000 <= year <= 2200:
                return year
        return None

    def _normalize_spelled_dates(s_text: str) -> str:
        if not s_text:
            return s_text
        word_tokens = re.findall(r"[A-Za-z]+|\d+", s_text)
        spans = [m.span() for m in re.finditer(r"[A-Za-z]+|\d+", s_text)]
        lower_tokens = [t.lower() for t in word_tokens]

        replacements = []
        i = 0
        while i < len(lower_tokens):
            if lower_tokens[i] in _MONTH_NAME_SET:
                month_word = word_tokens[i]
                day_val, day_start = None, i

                # Pass 1: look BACKWARDS
                for back in (2, 1):
                    if i - back >= 0:
                        cand = " ".join(lower_tokens[i - back:i])
                        if cand in _DAY_WORDS:
                            day_val = _DAY_WORDS[cand]
                            day_start = i - back
                            break

                if day_val is not None:
                    j = i + 1
                    year_word_tokens = []
                    while j < len(lower_tokens) and j < i + 6 and lower_tokens[j] in _NUMBER_WORD_SET:
                        year_word_tokens.append(lower_tokens[j])
                        j += 1
                    year_val = _year_from_words(year_word_tokens) if year_word_tokens else None
                    if year_val:
                        replacements.append((day_start, j, f"{day_val} {month_word} {year_val}"))
                        i = j
                        continue
                    day_val = None

                # Pass 2: look FORWARDS
                if day_val is None:
                    matched_fwd = False
                    for fwd in (2, 1):
                        if i + fwd < len(lower_tokens):
                            cand = " ".join(lower_tokens[i + 1: i + 1 + fwd])
                            if cand in _DAY_WORDS:
                                day_val = _DAY_WORDS[cand]
                                day_start = i            
                                i_after_day = i + 1 + fwd
                                j = i_after_day
                                year_word_tokens = []
                                while (j < len(lower_tokens) and
                                       j < i_after_day + 6 and
                                       lower_tokens[j] in _NUMBER_WORD_SET):
                                    year_word_tokens.append(lower_tokens[j])
                                    j += 1
                                year_val = _year_from_words(year_word_tokens) if year_word_tokens else None
                                if year_val:
                                    replacements.append(
                                        (day_start, j, f"{day_val} {month_word} {year_val}")
                                    )
                                    i = j
                                    matched_fwd = True
                                break   
                    if matched_fwd:
                        continue
            i += 1

        if not replacements:
            return s_text

        pieces, last_end, idx, ri = [], 0, 0, 0
        while idx < len(word_tokens):
            if ri < len(replacements) and idx == replacements[ri][0]:
                start_c, end_c_idx, repl_str = replacements[ri]
                start_char = spans[start_c][0]
                end_char = spans[end_c_idx - 1][1]
                pieces.append(s_text[last_end:start_char])
                pieces.append(repl_str)
                last_end = end_char
                idx = end_c_idx
                ri += 1
            else:
                idx += 1
        pieces.append(s_text[last_end:])
        return "".join(pieces)

    text = _normalize_spelled_dates(text)
    if start_date:
        start_date = _normalize_spelled_dates(start_date)
    if end_date:
        end_date = _normalize_spelled_dates(end_date)

    if not text:
        for alt_key in ("message", "query", "utterance", "raw_text", "user_text",
                         "user_input", "input", "prompt", "command", "raw_query", "msg"):
            val = kwargs.get(alt_key)
            if isinstance(val, str) and val.strip():
                text = val
                logger.info(f"[DateFilter] Recovered text from kwarg '{alt_key}': {text!r}")
                break
        else:
            for k, v in kwargs.items():
                if isinstance(v, str) and re.search(r"\bto\b|\bthru\b|\btill\b", v, re.IGNORECASE) and re.search(r"\d{4}", v):
                    text = v
                    logger.info(f"[DateFilter] Recovered text from unrecognized kwarg '{k}': {text!r}")
                    break

    logger.info(f"[DateFilter] RAW INPUT start_date={start_date!r} end_date={end_date!r} text={text!r}")

    _DATE_TOKEN = (
        r"(?:\d{4}[-/]\d{1,2}[-/]\d{1,2}"
        r"|\d{1,2}[-/]\d{1,2}[-/]\d{4}"
        r"|\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+\d{4}"
        r"|[A-Za-z]+\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4})"
    )
    _RANGE_RE = re.compile(
        rf"({_DATE_TOKEN})\s*(?:to|thru|through|till|until|[-–—])\s*({_DATE_TOKEN})",
        re.IGNORECASE
    )

    def _try_text_extraction():
        if not text:
            return None, None
        m = _RANGE_RE.search(text)
        if m:
            return m.group(1), m.group(2)
        return None, None

    s = _parse_date(start_date) if start_date else None
    e = _parse_date(end_date) if end_date else None

    if s is None or e is None:
        ext_start, ext_end = _try_text_extraction()
        if s is None and ext_start:
            s = _parse_date(ext_start)
            if s:
                start_date = ext_start
        if e is None and ext_end:
            e = _parse_date(ext_end)
            if e:
                end_date = ext_end

    if s is None or e is None:
        logger.warning(f"[DateFilter] Extraction/parse failed.")
        bad = start_date if s is None else end_date
        return (f"Couldn't understand the date '{bad}'. Try formats like "
                f"'4-5-2026', '4 May 2026', or '2026-05-04'.")

    ctrl = BrowserController()
    page = await ctrl._ensure_page()

    # ── Popup Closer Helper ──────────────────────────────────────────────────
    async def _close_calendar_popup():
        """Force close lingering calendars via Escape and an 'outside click' blur."""
        try:
            await page.keyboard.press("Escape")
            await asyncio.sleep(0.1)
            # Click empty space (top left) to trigger blur on date pickers that ignore Escape
            await page.mouse.click(10, 10)
            await asyncio.sleep(0.2)
        except Exception as err:
            logger.debug(f"[DateFilter] Close popup error: {err}")

    # ── Layer 1: Native HTML date / labelled text inputs ─────────────────────
    async def _get_visible_date_inputs_sorted_by_x():
        combined = (
            "input[type='date'],"
            "input[placeholder*='yyyy' i],"
            "input[placeholder*='dd-mm' i],"
            "input[placeholder*='mm/dd' i],"
            "input[placeholder*='mm-dd' i],"
            "input[placeholder*='dd/mm' i],"
            "input[placeholder*='date' i]"
        )
        items = []
        try:
            handles = await page.query_selector_all(combined)
            for h in handles:
                try:
                    if not await h.is_visible():
                        continue
                    box = await h.bounding_box()
                    if box and box["width"] > 0:
                        itype = await h.get_attribute("type") or "text"
                        items.append((box["x"], h, itype))
                except Exception as e:
                    logger.error(f"Error: {e}")
                    pass
        except Exception as e:
            logger.error(f"Error: {e}")
            pass
        items.sort(key=lambda t: t[0])
        return [(h, itype) for _, h, itype in items]

    async def _fill_native(value_dmy: str, value_iso: str, index: int = 0) -> bool:
        try:
            sorted_inputs = await _get_visible_date_inputs_sorted_by_x()
            if len(sorted_inputs) >= 2 and index < len(sorted_inputs):
                el, itype = sorted_inputs[index]
                val = value_iso if itype == "date" else value_dmy
                await el.click(click_count=3, timeout=1500)
                await el.fill(val, timeout=1500)
                await page.keyboard.press("Tab")
                logger.info(f"[DateFilter] Layer 1a filled index={index} type={itype} val={val}")
                return True
        except Exception as _err:
            logger.debug(f"[DateFilter] Layer 1a failed: {_err}")

        sel_groups = [
            [
                "input[placeholder*='yyyy' i]",
                "input[placeholder*='dd-mm' i]",
                "input[placeholder*='mm/dd' i]",
                "input[placeholder*='date' i]",
                "input[class*='date' i]",
            ],
            [
                f"input[id*='{'start' if index==0 else 'end'}' i]",
                f"input[id*='{'from' if index==0 else 'to'}' i]",
                f"input[name*='{'start' if index==0 else 'end'}' i]",
            ],
        ]
        for grp in sel_groups:
            for sel in grp:
                try:
                    loc = page.locator(sel)
                    n = await loc.count()
                    for i in range(index, min(n, index + 3)):
                        el = loc.nth(i)
                        if await el.is_visible():
                            itype = await el.get_attribute("type") or "text"
                            val = value_iso if itype == "date" else value_dmy
                            await el.triple_click(timeout=1500)
                            await el.fill(val, timeout=1500)
                            await page.keyboard.press("Tab")
                            logger.info(f"[DateFilter] Layer 1b filled sel={sel} i={i} val={val}")
                            return True
                except Exception as e:
                    logger.error(f"Error: {e}")
                    pass
        return False

    s_ok = await _fill_native(s["dmy"], s["iso"], 0)
    await asyncio.sleep(0.2)
    e_ok = await _fill_native(e["dmy"], e["iso"], 1)
    if s_ok and e_ok:
        await _close_calendar_popup()
        await page.keyboard.press("Enter")
        logger.info("[DateFilter] Layer 1 success")
        return f"Date filter set: {s['dmy']} to {e['dmy']}."

    # ── Layer 2: TreeWalker JS scan + JS calendar navigation ──────────────────
    logger.info("[DateFilter] Layer 1 failed → comprehensive JS scan (Layer 2)")

    date_els_info = await page.evaluate("""() => {
        const dateRe = /\\d{1,2}[-\\/]\\d{1,2}[-\\/]\\d{4}/;
        const results = [];

        try {
            const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
            let node;
            while (node = walker.nextNode()) {
                const t = node.textContent.trim();
                if (t.length > 0 && t.length <= 15 && dateRe.test(t)) {
                    const el = node.parentElement;
                    if (!el) continue;
                    const r = el.getBoundingClientRect();
                    if (r.width > 0 && r.height > 0 && r.top >= 0 && r.top < window.innerHeight) {
                        results.push({x: r.left + r.width/2, y: r.top + r.height/2,
                                      tag: el.tagName, cls: el.className.substring(0,60), text: t});
                    }
                }
            }
        } catch(e) {}

        document.querySelectorAll('input').forEach(el => {
            const val = (el.value || el.getAttribute('data-value') || '').trim();
            if (!dateRe.test(val)) return;
            const r = el.getBoundingClientRect();
            if (r.width > 0)
                results.push({x: r.left + r.width/2, y: r.top + r.height/2,
                              tag: 'INPUT', cls: el.className.substring(0,60), text: val, id: el.id});
        });

        document.querySelectorAll('[aria-label]').forEach(el => {
            const label = el.getAttribute('aria-label') || '';
            if (!dateRe.test(label)) return;
            const r = el.getBoundingClientRect();
            if (r.width > 0 && r.height > 0)
                results.push({x: r.left + r.width/2, y: r.top + r.height/2,
                              tag: el.tagName, cls: el.className.substring(0,60), text: label.substring(0,20)});
        });

        const out = [];
        for (const item of results) {
            if (!out.some(d => Math.abs(d.x - item.x) < 10 && Math.abs(d.y - item.y) < 10))
                out.push(item);
        }
        return out.slice(0, 10);
    }""")

    async def _js_find_calendar_header() -> dict | None:
        return await page.evaluate("""() => {
            const months = ['january','february','march','april','may','june',
                            'july','august','september','october','november','december'];
            let best = null, bestLen = 999;
            document.querySelectorAll('*').forEach(el => {
                const r = el.getBoundingClientRect();
                if (r.width === 0 || r.height === 0) return;
                const t = (el.innerText || '').trim();
                if (t.length === 0 || t.length > 25) return;
                const hasMonth = months.some(m => t.toLowerCase().includes(m));
                if (hasMonth && /\\d{4}/.test(t) && t.length < bestLen) {
                    bestLen = t.length;
                    best = {text: t, cls: el.className.substring(0,60),
                            x: r.left + r.width/2, y: r.top + r.height/2};
                }
            });
            return best;
        }""")

    async def _js_click_nav(direction: str) -> bool:
        return bool(await page.evaluate(f"""(dir) => {{
            const isNext = dir === 'next';
            const ariaRe = isNext ? /next|forward|right/i : /prev|back|left/i;
            const textRe = isNext ? /^[>›»▶→]$/ : /^[<‹«◄←]$/;
            const btns = [...document.querySelectorAll('button,[role="button"]')];
            for (const el of btns) {{
                const r = el.getBoundingClientRect();
                if (r.width === 0 || r.height === 0) return false;
                const label = el.getAttribute('aria-label') || '';
                const txt = (el.innerText || el.textContent || '').trim();
                if (ariaRe.test(label) || textRe.test(txt) ||
                    (isNext ? el.className.match(/next/i) : el.className.match(/prev/i))) {{
                    el.click();
                    return true;
                }}
            }}
            return false;
        }}""", direction))

    async def _js_click_day(target_day: int, target_month: int) -> bool:
        month_name = MONTH_NAMES[target_month]
        return bool(await page.evaluate(f"""(day, monthName) => {{
            const dayRe = new RegExp('^' + day + '$');
            const cells = [...document.querySelectorAll(
                'td,button,[role="gridcell"],[role="button"],[class*="day"],[class*="Day"]'
            )];
            for (const el of cells) {{
                const r = el.getBoundingClientRect();
                if (r.width === 0 || r.height === 0) return false;
                if (el.getAttribute('aria-disabled') === 'true') continue;
                if (el.className && el.className.match(/outside|disabled|other.month/i)) continue;
                const txt = (el.innerText || el.textContent || '').trim();
                const label = el.getAttribute('aria-label') || '';
                if (dayRe.test(txt) || label.includes(monthName + ' ' + day)
                        || label.includes(day + ' ' + monthName)) {{
                    el.click();
                    return true;
                }}
            }}
            return false;
        }}""", target_day, month_name))

    async def _navigate_to_and_pick(target: dict) -> bool:
        header = await _js_find_calendar_header()
        if not header:
            return False

        hm = re.search(r'(\w+)\s+(\d{4})', header["text"])
        hm2 = re.search(r'(\d{4})[^\d]+(\d{1,2})', header["text"])
        current_m, current_y = None, None
        if hm:
            current_m = MONTHS_MAP.get(hm.group(1)[:3].lower())
            current_y = int(hm.group(2))
        elif hm2:
            current_y, current_m = int(hm2.group(1)), int(hm2.group(2))

        if not current_m or not current_y:
            return False

        delta = (target["y"] - current_y) * 12 + (target["m"] - current_m)
        direction = "next" if delta >= 0 else "prev"

        for _ in range(min(abs(delta), 24)):
            if not await _js_click_nav(direction):
                break
            await asyncio.sleep(0.15)

        return await _js_click_day(target["d"], target["m"])

    date_els_info = sorted(date_els_info, key=lambda el: el["x"])

    start_done, end_done = False, False
    used = set()
    for info in date_els_info:
        key = (round(info["x"]/10), round(info["y"]/10))
        if key in used:
            continue
        used.add(key)

        if not start_done:
            await page.mouse.click(info["x"], info["y"])
            await asyncio.sleep(0.5)
            start_done = await _navigate_to_and_pick(s)
            if start_done:
                await _close_calendar_popup()
            continue

        if start_done and not end_done:
            await page.mouse.click(info["x"], info["y"])
            await asyncio.sleep(0.5)
            end_done = await _navigate_to_and_pick(e)
            if end_done:
                await _close_calendar_popup()
            break

    if start_done and end_done:
        return f"Date filter set: {s['dmy']} to {e['dmy']}."

    # ── Layer 3: DOMAgent targeted prompts ────────────────────────────────────
    logger.warning("[DateFilter] Layer 2 failed → DOMAgent (Layer 3)")
    from automation.browser.dom_agent import DOMAgent
    agent = DOMAgent(page)
    res_s = await agent.execute_intent(
        f"Click the start date field (shows a past date near a calendar icon at the top). "
        f"After the calendar opens, navigate to {MONTH_NAMES[s['m']]} {s['y']} and click day {s['d']}."
    )
    await asyncio.sleep(0.4)
    res_e = await agent.execute_intent(
        f"Click the end date field (shows a later date near a calendar icon). "
        f"After the calendar opens, navigate to {MONTH_NAMES[e['m']]} {e['y']} and click day {e['d']}."
    )
    
    ok = lambda r: r and not any(x in r.lower() for x in ["couldn't","failed","could not"])
    if ok(res_s) or ok(res_e):
        await _close_calendar_popup()
        return f"Date filter set: {s['dmy']} to {e['dmy']}."

    return (
        f"The date picker needs manual interaction. "
        f"Click the start date → navigate to {MONTH_NAMES[s['m']]} {s['y']} → click {s['d']}. "
        f"Then end date → {MONTH_NAMES[e['m']]} {e['y']} → click {e['d']}."
    )

async def handle_smart_logout(text: str = "", **_) -> str:
    """
    Smart multi-layer logout handler.
    - If the user is on the CRM site → delegates to CRM logout.
    - Otherwise → uses LogoutHandler (5-layer progressive detection).
    This avoids the empty-string problem of handle_crm_action for logout.
    """
    from automation.browser.browser_controller import BrowserController
    from app.config import settings
    ctrl = BrowserController()
    try:
        url = await ctrl.engine.get_url()
        crm_host = settings.crm_url.replace("https://", "").replace("http://", "").split("/")[0]
        is_on_crm = bool(url and crm_host and crm_host in url)
        wants_crm = "crm" in (text or "").lower()

        if is_on_crm or wants_crm:
            from automation.browser.crm_workflows import CRMMacros
            crm = CRMMacros(ctrl.engine)
            return await crm.logout()
    except Exception as e:
        logger.error(f"Error: {e}")
        pass  # If URL check fails, fall through to smart logout

    # Generic site — use the 5-layer smart logout handler
    page = await ctrl._ensure_page()
    from automation.browser.logout_handler import LogoutHandler
    handler = LogoutHandler(page)
    return await handler.smart_logout()

async def handle_browser_autonomous_action(text: str = "", task: str = "", **_) -> str:
    from automation.browser.browser_controller import BrowserController
    from automation.browser.dom_agent import DOMAgent
    from automation.browser.browser_agent import AutonomousBrowserAgent
    from loguru import logger
    
    action_text = task if task else text
    if not action_text:
        return "No task specified."
        
    ctrl = BrowserController()
    engine = ctrl.engine
    
    # Fast Path: Try DOMAgent (single-step interaction on current page)
    try:
        if engine._playwright is not None:
            page = await ctrl._ensure_page()
            agent = DOMAgent(page)
            logger.info(f"Attempting fast-path DOMAgent for task: '{action_text}'")
            res = await agent.execute_intent(action_text)
            
            # If it succeeded (didn't return 'couldn't find' or 'Failed'), we're done!
            if res and "couldn't find" not in res.lower() and "failed" not in res.lower():
                return res
            logger.info(f"DOMAgent skipped or failed: {res}. Falling back to full autonomous agent.")
    except Exception as e:
        logger.warning(f"DOMAgent threw an error: {e}")
        
    # Slow Path: Full Autonomous Agent (browser-use)
    logger.info(f"Escalating '{action_text}' to AutonomousBrowserAgent...")
    return await AutonomousBrowserAgent.run_task(action_text, engine)

async def handle_read_page_title(**_) -> str:
    from automation.browser.browser_engine import BrowserEngine
    title = await BrowserEngine().get_page_title()
    return f"The page title is: {title}"

async def handle_extract_page_content(**_) -> str:
    from automation.browser.browser_engine import BrowserEngine
    content = await BrowserEngine().extract_page_content()
    if len(content) > 500:
        content = content[:500] + "... [Content truncated]"
    return f"Here is the page content:\n{content}"
async def handle_analyze_screen(query: str = "", **_) -> str:
    from app.services.vision_service import VisionService
    if not query:
        query = "Describe what is currently visible on my screen."
    return await VisionService.describe_screen(query)

async def handle_open_folder(path: str = "", disambiguation: str | None = None, **_) -> str:
    from automation.desktop.file_operations import FileOperations
    return FileOperations().open_folder(path.strip(), disambiguation)


async def handle_close_folder(path: str = "", **_) -> str:
    from automation.desktop.window_manager import WindowManager
    folder_name = path.strip()
    if WindowManager().close_window_by_title(folder_name):
        return f"Closed folder: {folder_name}"
    return f"Folder '{folder_name}' is not currently open."


async def handle_open_project(project_name: str = "", **_) -> str:
    from app.services.context_state import get_context
    import subprocess
    import os
    
    clean = project_name.replace("project", "").strip()
    
    # 1. Try to fetch from explicit projects.json mapping
    ctx = get_context()
    project_path = ctx.get_project_path(clean)
    
    if not project_path:
        # 2. Fallback to Windows Search API
        from automation.desktop.file_indexer import get_indexer
        indexer = get_indexer()
        results = indexer.search(clean, is_folder=True, limit=5)
        if results:
            project_path = results[0]["path"]
            
    if not project_path:
        return f"Could not find a project folder named {clean}"
        
    ctx.set("active_project_path", project_path)
    
    # Open in VS Code (assuming code is in PATH)
    try:
        subprocess.Popen(["code", project_path], cwd=project_path, shell=True)
        return f"Opened project '{clean}' in VS Code"
    except Exception as e:
        return f"Found project but failed to open in VS Code: {e}"


async def handle_create_project(project_type: str = "", project_name: str = "", **_) -> str:
    from app.services.context_manager import context_manager
    import subprocess
    import os
    
    # Clean inputs
    project_type = project_type.lower().strip() if project_type else ""
    project_name = project_name.lower().strip() if project_name else "my-app"
    project_name = project_name.replace(" ", "-") # normalize for npm
    
    desktop = os.path.expanduser("~/Desktop")
    target_path = os.path.join(desktop, project_name)
    
    original_project_name = project_name
    counter = 1
    while os.path.exists(target_path):
        project_name = f"{original_project_name}-{counter}"
        target_path = os.path.join(desktop, project_name)
        counter += 1
    # Determine scaffolding command
    if "react" in project_type or "vite" in project_type:
        scaffold_cmd = f"npm create vite@latest {project_name} --yes -- --template react"
        post_cmd = "npm install"
    elif "next" in project_type:
        scaffold_cmd = f"npx create-next-app@latest {project_name} --yes --use-npm --eslint --tailwind --app"
        post_cmd = "" # Next.js does npm install automatically
    else:
        # Generic fallback
        scaffold_cmd = f"mkdir {project_name}"
        post_cmd = ""
        
    try:
        # 1. Run the fast scaffold command
        # 2. IMMEDIATELY open VS Code so the user isn't waiting
        # 3. CD into the directory and run the slow `npm install` (so the user has a fully working project)
        full_cmd = f"echo Scaffolding {project_type} project (downloading template)... && {scaffold_cmd} && echo Opening VS Code... && code {project_name}"
        if post_cmd:
            full_cmd += f" && echo. && echo Installing dependencies from npm (this may take 2-5 minutes depending on network)... && cd {project_name} && {post_cmd}"
            
        full_cmd += " && echo. && echo Finished! You can now close this terminal."
        
        # Spawn terminal to show progress
        subprocess.Popen(f"start cmd /k \"cd /d {desktop} && {full_cmd}\"", shell=True)
        
        # Track context
        context_manager.last_project_path = target_path
        
        return f"Creating a new {project_type} project named {project_name} on your Desktop..."
    except Exception as e:
        return f"Failed to create project: {e}"


async def handle_run_dev_server(cmd: str = "", **_) -> str:
    from app.services.context_manager import context_manager
    import subprocess
    import os
    
    if not context_manager.last_project_path:
        return "I don't know which project to run. Please open a project first."
        
    project_path = context_manager.last_project_path
    
    # Simple detection logic
    if os.path.exists(os.path.join(project_path, "package.json")):
        start_cmd = "npm run dev"
        context_manager.last_dev_server_url = "http://localhost:3000"
    elif os.path.exists(os.path.join(project_path, "requirements.txt")) or os.path.exists(os.path.join(project_path, "main.py")):
        start_cmd = "python main.py" # Simple fallback
        context_manager.last_dev_server_url = "http://localhost:8000"
    else:
        start_cmd = cmd or "npm start"
        
    try:
        # We spawn in a new console window so the user can see the dev server
        subprocess.Popen(f"start cmd /k \"cd /d {project_path} && {start_cmd}\"", shell=True)
        return f"Started dev server in {os.path.basename(project_path)}"
    except Exception as e:
        return f"Failed to start dev server: {e}"


async def handle_open_dev_server(**_) -> str:
    from app.services.context_manager import context_manager
    from automation.browser.browser_controller import BrowserController as BrowserController
    
    url = context_manager.last_dev_server_url
    if not url:
        return "I don't have a dev server URL tracked in context."
        
    bc = BrowserController()
    await bc.navigate(url)
    return f"Opened application in browser at {url}"


async def handle_search_file(file_name: str = "", explicit_type: str = None, **_) -> str:
    from automation.desktop.file_operations import FileOperations
    from app.services.intent_registry import handle_open_app
    query = file_name.strip()
    
    if explicit_type:
        explicit_type = explicit_type.lower()
        if explicit_type in ("folder", "directory"):
            return FileOperations().open_folder(query)
        elif explicit_type in ("app", "application", "program"):
            return await handle_open_app(query)
        else:
            return FileOperations().search_file(query)
            
    # Omni Search
    from automation.desktop.file_indexer import get_indexer
    from automation.desktop.app_scanner import get_scanner
    from rapidfuzz import process, fuzz
    
    indexer = get_indexer()
    scanner = get_scanner()
    
    found_files = indexer.search(query, is_folder=False, limit=3)
    found_folders = indexer.search(query, is_folder=True, limit=3)
    
    found_apps = []
    if scanner.apps:
        choices = list(scanner.apps.keys())
        matches = process.extract(query.lower(), choices, scorer=fuzz.WRatio, limit=3)
        for m in matches:
            if m[1] > 75:
                found_apps.append(scanner.apps[m[0]].name)
                
    if not found_files and not found_folders and not found_apps:
        raise FileNotFoundError(f"Could not find any file, folder, or application named '{query}'")
        
    options = []
    if found_files: options.append("files")
    if found_folders: options.append("folders")
    if found_apps: options.append("applications")
    
    opts_str = ", ".join(options)
    
    # Replace last comma with 'and' if multiple
    if len(options) > 1:
        opts_str = " and ".join(opts_str.rsplit(", ", 1))
    
    from app.services.command_service import command_service
    command_service._pending_action = {
        "intent": "omni_search_disambiguate",
        "params": {
            "query": query,
            "files": [f['path'] for f in found_files],
            "folders": [f['path'] for f in found_folders],
            "apps": [a for a in found_apps]
        }
    }
    
    return f"I found matching {opts_str}. Would you like to open a file, folder, application, or search Google?"


async def handle_create_folder(folder_name: str = "", drive: str | None = None, **_) -> str:
    from automation.desktop.file_operations import FileOperations
    return FileOperations().create_folder(folder_name.strip(), drive)


async def handle_run_command(cmd: str = "", **_) -> str:
    from automation.desktop.app_controller import AppController
    return await AppController().run_terminal_command(cmd.strip())


async def handle_volume_up(**_) -> str:
    from automation.input.keyboard_controller import KeyboardController
    KeyboardController().volume_up()
    return "Volume increased"


async def handle_volume_down(**_) -> str:
    from automation.input.keyboard_controller import KeyboardController
    KeyboardController().volume_down()
    return "Volume decreased"


async def handle_mute(**_) -> str:
    from automation.input.keyboard_controller import KeyboardController
    KeyboardController().mute()
    return "Muted"


async def handle_minimize_window(**_) -> str:
    from automation.desktop.window_manager import WindowManager
    WindowManager().minimize_active()
    return "Window minimized"


async def handle_maximize_window(**_) -> str:
    from automation.desktop.window_manager import WindowManager
    WindowManager().maximize_active()
    return "Window maximized"


async def handle_minimize_app(app: str = "", **_) -> str:
    from automation.desktop.app_controller import AppController
    from automation.desktop.window_manager import WindowManager
    import pywinauto
    
    clean = app.strip()
    candidates = AppController()._resolve_candidates(clean.lower())
    
    for exe in candidates:
        try:
            win_app = pywinauto.Application(backend="uia").connect(path=exe, timeout=1)
            win_app.top_window().minimize()
            return f"Minimized {clean}"
        except Exception as e:
            logger.error(f"Error: {e}")
            pass

    if WindowManager().minimize_by_title(clean):
        return f"Minimized {clean}"
    return f"Could not find open window for {clean}"


async def handle_save(app_name: str = "", **_) -> str:
    from automation.input.keyboard_controller import KeyboardController
    KeyboardController().press_enter()
    return "Saving..."


async def handle_dont_save(app_name: str = "", **_) -> str:
    from automation.input.keyboard_controller import KeyboardController
    from pynput.keyboard import Key
    KeyboardController().press(Key.alt, 'n')
    return "Changes discarded."


async def handle_cancel(app_name: str = "", **_) -> str:
    from automation.input.keyboard_controller import KeyboardController
    KeyboardController().press_escape()
    return "Canceled."


async def handle_maximize_app(app: str = "", **_) -> str:
    from automation.desktop.app_controller import AppController
    from automation.desktop.window_manager import WindowManager
    import pywinauto
    
    clean = app.strip()
    candidates = AppController()._resolve_candidates(clean.lower())
    
    for exe in candidates:
        try:
            win_app = pywinauto.Application(backend="uia").connect(path=exe, timeout=1)
            win_app.top_window().maximize()
            return f"Maximized {clean}"
        except Exception as e:
            logger.error(f"Error: {e}")
            pass

    if WindowManager().maximize_by_title(clean):
        return f"Maximized {clean}"
    return f"Could not find open window for {clean}"


async def handle_close_window(**_) -> str:
    from automation.desktop.window_manager import WindowManager
    WindowManager().close_active()
    return "Window closed"


async def handle_clipboard_copy(**_) -> str:
    from automation.input.keyboard_controller import KeyboardController
    KeyboardController().copy()
    return "Copied to clipboard"


async def handle_clipboard_paste(**_) -> str:
    from automation.input.keyboard_controller import KeyboardController
    KeyboardController().paste()
    return "Pasted from clipboard"


async def handle_screenshot(**_) -> str:
    from automation.system.clipboard import ClipboardManager
    path = ClipboardManager().screenshot()
    return f"Screenshot saved to {path}"


async def handle_system_sleep(**_) -> str:
    from automation.system.power import PowerManager
    PowerManager().sleep()
    return "System going to sleep"


async def handle_system_shutdown(**_) -> str:
    from automation.system.power import PowerManager
    PowerManager().shutdown()
    return "System shutting down"


async def handle_system_restart(**_) -> str:
    from automation.system.power import PowerManager
    PowerManager().restart()
    return "System restarting"


async def handle_type_text(text: str = "", **_) -> str:
    try:
        from automation.browser.browser_controller import BrowserController
        bc = BrowserController()
        if bc.engine._playwright is not None:
            # Try to type via DOMAgent first
            from automation.browser.dom_agent import DOMAgent
            page = await bc.engine.ensure_browser()
            agent = DOMAgent(page)
            dom_res = await agent.execute_intent(f"type {text}")
            if "couldn't find" not in dom_res.lower() and "failed" not in dom_res.lower():
                return dom_res
    except Exception as e:
        logger.error(f"Error: {e}")
        pass
        
    from automation.input.keyboard_controller import KeyboardController
    ctrl = KeyboardController()
    res = ctrl.type_text(text)
    if res:
        return f"Typed '{text}'."
    return f"Failed to type '{text}'."


async def handle_lock_screen(**_) -> str:
    from automation.system.power import PowerManager
    PowerManager().lock_screen()
    return "Screen locked"


async def handle_click(**_) -> str:
    from automation.input.mouse_controller import MouseController
    MouseController().click()
    return "Clicked"


async def handle_double_click(**_) -> str:
    from automation.input.mouse_controller import MouseController
    MouseController().double_click()
    return "Double clicked"

async def handle_click_text(text: str = "", **_) -> str:
    """
    Priority order for clicking text:
    1. DOMAgent (browser-based) — precise, targets only the browser page, not the whole screen.
    2. VoiceBrowserCommands — legacy browser commands.
    3. OCR (last resort) — scans the entire screen. Only used when no browser session is active.
    """
    clean_text = text.strip()
    
    # ── Priority 1: DOMAgent (Browser-First) ────────────────────────────────
    # If the browser engine is running (even via CDP reconnect), always try this first.
    # This guarantees we click the website, not any screen overlay like the command console.
    try:
        from automation.browser.browser_controller import BrowserController
        from automation.browser.dom_agent import DOMAgent
        bc = BrowserController()
        # Attempt to get/reconnect to browser. This also tries CDP reconnect.
        page = await bc.engine.ensure_browser()
        if page is not None:
            agent = DOMAgent(page)
            dom_res = await agent.execute_intent(f"click {clean_text}")
            if "couldn't find" not in dom_res.lower() and "failed" not in dom_res.lower():
                return dom_res
            # If DOMAgent couldn't find the element, fall through to OCR
            logger.warning(f"DOMAgent could not find '{clean_text}' on page. Falling back to OCR.")
    except Exception as e:
        logger.warning(f"DOMAgent click failed for '{clean_text}': {e}. Falling back to OCR.")

    # ── Last Resort: Desktop OCR ─────────────────────────────────────────────
    # Only reaches here if no browser session is active OR the element was not found in DOM.
    # This scans the full screen — avoid when browser is visible to prevent clicking console UI.
    from automation.desktop.ocr_controller import OCRController
    return await OCRController().find_and_click_text(clean_text)


async def handle_right_click(**_) -> str:
    from automation.input.mouse_controller import MouseController
    MouseController().right_click()
    return "Right clicked"


async def handle_scroll_up(**_) -> str:
    try:
        from automation.browser.browser_controller import BrowserController
        ctrl = BrowserController()
        if ctrl.engine._playwright is not None:
            await ctrl.scroll("up")
            return "Scrolled up in browser"
    except Exception as e:
        logger.error(f"Error: {e}")
        pass
        
    from automation.input.mouse_controller import MouseController
    MouseController().scroll_up()
    return "Scrolled up"


async def handle_scroll_down(**_) -> str:
    try:
        from automation.browser.browser_controller import BrowserController
        ctrl = BrowserController()
        if ctrl.engine._playwright is not None:
            await ctrl.scroll("down")
            return "Scrolled down in browser"
    except Exception as e:
        logger.error(f"Error: {e}")
        pass
        
    from automation.input.mouse_controller import MouseController
    MouseController().scroll_down()
    return "Scrolled down"

async def handle_scroll_top(**_) -> str:
    try:
        from automation.browser.browser_controller import BrowserController
        ctrl = BrowserController()
        if ctrl.engine._playwright is not None:
            await ctrl.scroll_to_top()
            return "Scrolled to top in browser"
    except Exception as e:
        logger.error(f"Error: {e}")
        pass
    
    # Fallback to mouse scroll if not in browser (rough approximation)
    from automation.input.mouse_controller import MouseController
    for _ in range(5):
        MouseController().scroll_up()
    return "Scrolled up"

async def handle_scroll_bottom(**_) -> str:
    try:
        from automation.browser.browser_controller import BrowserController
        ctrl = BrowserController()
        if ctrl.engine._playwright is not None:
            await ctrl.scroll_to_bottom()
            return "Scrolled to bottom in browser"
    except Exception as e:
        logger.error(f"Error: {e}")
        pass
    
    # Fallback to mouse scroll if not in browser (rough approximation)
    from automation.input.mouse_controller import MouseController
    for _ in range(5):
        MouseController().scroll_down()
    return "Scrolled down"



async def handle_submit(app_name: str = "", **_) -> str:
    import asyncio
    import pywinauto
    from automation.desktop.window_manager import WindowManager
    from automation.input.keyboard_controller import KeyboardController

    typed_via_pywinauto = False
    if app_name:
        try:
            win = WindowManager()._find_window_by_title(app_name)
            if win:
                app = pywinauto.Application(backend="uia").connect(process=win.process_id())
                top_win = app.top_window()
                top_win.set_focus()
                top_win.type_keys("{ENTER}")
                typed_via_pywinauto = True
        except Exception as e:
            logger.error(f"Error: {e}")
            pass
            
    if not typed_via_pywinauto:
        if app_name:
            WindowManager().focus_by_title(app_name)
        await asyncio.sleep(0.5)
        KeyboardController().press_enter()
        
    return f"Submitted {f'in {app_name}' if app_name else ''}"


async def handle_dont_save(app_name: str = "", **_) -> str:
    if app_name:
        from automation.desktop.app_controller import AppController
        await AppController().close_application(app_name, force=True)
        return f"Closed {app_name} without saving"
    else:
        from automation.input.keyboard_controller import KeyboardController
        KeyboardController().press("n")
        return "Pressed Don't Save"


async def handle_save(app_name: str = "", **_) -> str:
    from automation.input.keyboard_controller import KeyboardController
    if app_name:
        from automation.desktop.window_manager import WindowManager
        WindowManager().focus_by_title(app_name)
    import asyncio; await asyncio.sleep(0.5)
    KeyboardController().save()
    return f"PENDING_FILENAME: Pressed Save{f' in {app_name}' if app_name else ''}. What should I name the file?"


async def handle_set_filename(text: str = "", app_name: str = "", **_) -> str:
    from automation.input.keyboard_controller import KeyboardController
    import asyncio
    import pywinauto
    from automation.desktop.window_manager import WindowManager
    
    typed_via_pywinauto = False
    top_win = None
    
    try:
        desktop = pywinauto.Desktop(backend="win32")
        
        # 1. Check if a Save dialog is ALREADY open
        dialogs = [w for w in desktop.windows() if w.window_text() in ("Save As", "Save", "Open", "Confirm Save As")]
        
        # 2. If not open, trigger it (handles one-shot commands like "save the file as demo44")
        if not dialogs:
            if app_name:
                WindowManager().focus_by_title(app_name)
            KeyboardController().save() # Presses Ctrl+S
            await asyncio.sleep(0.5)
            
        # 3. Poll for up to 1.5 seconds to allow the dialog to spawn
        for _ in range(15):
            dialogs = [w for w in desktop.windows() if w.window_text() in ("Save As", "Save", "Open", "Confirm Save As")]
            if dialogs:
                break
            await asyncio.sleep(0.1)
            
        if dialogs:
            top_win = dialogs[0]
            top_win.set_focus()
            top_win.type_keys(text.strip() + "{ENTER}", with_spaces=True)
            typed_via_pywinauto = True
        elif app_name:
            # Fallback to application's top window via uia if no explicit dialog is found
            win = WindowManager()._find_window_by_title(app_name)
            if win:
                app = pywinauto.Application(backend="uia").connect(process=win.process_id())
                top_win = app.top_window()
                top_win.set_focus()
                top_win.type_keys(text.strip() + "{ENTER}", with_spaces=True)
                typed_via_pywinauto = True
    except Exception as e:
        pass
            
    if not typed_via_pywinauto:
        # Fallback to physical keyboard if pywinauto failed
        if app_name:
            WindowManager().focus_by_title(app_name)
        await asyncio.sleep(0.5)
        KeyboardController().type_text(text.strip())
        await asyncio.sleep(0.3)
        KeyboardController().press_enter()
        
    await asyncio.sleep(0.8) # Wait for potential conflict dialog to appear
    
    # Check for conflict dialog
    conflict_found = False
    try:
        # Check if a "Confirm Save As" dialog popped up
        desktop = pywinauto.Desktop(backend="win32")
        conflict_dialogs = [w for w in desktop.windows() if "confirm save as" in w.window_text().lower()]
        if conflict_dialogs:
            conflict_found = True
            top_win = conflict_dialogs[0]
            
        if not conflict_found and app_name and top_win:
            # Re-fetch top window in case a new modal appeared in UIA
            app = pywinauto.Application(backend="uia").connect(process=win.process_id())
            new_top = app.top_window()
            title = new_top.window_text().lower()
            if "confirm" in title or "already exists" in title or "replace" in title:
                conflict_found = True
    except Exception as e:
        logger.error(f"Error: {e}")
        pass
        
    if conflict_found:
        KeyboardController().press_escape() # Cancel the conflict dialog
        return f"PENDING_FILENAME: A file named '{text}' already exists. Please tell me a different file name."
        
    return f"File saved as '{text}'."

async def handle_cancel(app_name: str = "", **_) -> str:
    import asyncio
    import re
    import pywinauto
    from automation.desktop.window_manager import WindowManager
    from automation.input.keyboard_controller import KeyboardController
    from loguru import logger

    # ── Step 1: Browser popup/overlay dismissal ───────────────────────────────
    try:
        from automation.browser.browser_controller import BrowserController
        bc = BrowserController()
        if bc.engine._context is not None:
            page = await bc._ensure_page()
            if page:
                # 1a. Look for explicit close / dismiss / × buttons
                CLOSE_SELECTORS = [
                    "[aria-label*='close' i]",
                    "[aria-label*='dismiss' i]",
                    "[aria-label*='cancel' i]",
                    "button.close",
                    ".close",               # Added: Generic close class
                    ".btn-close",           # Added: Bootstrap close class
                    ".modal-close",
                    ".popup-close",
                    ".dialog-close",
                    "[class*='close-btn' i]",
                    "[class*='closeBtn' i]",
                    "[class*='close-button' i]",
                    "button:has-text('×')",
                    "button:has-text('✕')",
                    "span:has-text('×')",   # Added: Spans with X
                    "i:has-text('×')",      # Added: Icons with X
                    "button:has-text('X')",
                    "[role='button'][aria-label*='close' i]",
                ]
                for sel in CLOSE_SELECTORS:
                    try:
                        loc = page.locator(sel)
                        count = await loc.count()
                        for i in range(min(count, 5)):
                            el = loc.nth(i)
                            if await el.is_visible():
                                await el.click(timeout=1500)
                                logger.info(f"[Cancel] Closed overlay via selector: {sel}")
                                return "Closed the popup."
                    except Exception as e:
                        logger.error(f"Error: {e}")
                        pass

                # 1b. Text-based: Cancel / Close / Dismiss buttons
                for label in ["cancel", "close", "dismiss", "no thanks", "not now"]:
                    try:
                        cancel_button = page.locator(
                            "button, a, input[type='button'], [role='button']"
                        ).filter(has_text=re.compile(re.escape(label), re.IGNORECASE))
                        for i in range(await cancel_button.count()):
                            btn = cancel_button.nth(i)
                            if await btn.is_visible():
                                await btn.click(timeout=1500)
                                logger.info(f"[Cancel] Clicked '{label}' button on webpage.")
                                return f"Clicked {label.capitalize()} on webpage."
                    except Exception as e:
                        logger.error(f"Error: {e}")
                        pass

                # 1c. DOMAgent Fallback (Before pressing Escape)
                try:
                    from automation.browser.dom_agent import DOMAgent
                    agent = DOMAgent(page)
                    res = await agent.execute_intent("click the 'x' close button on the popup")
                    if "couldn't find" not in res.lower() and "failed" not in res.lower():
                        logger.info("[Cancel] Closed popup via DOMAgent.")
                        return "Closed the popup."
                except Exception as e:
                    logger.debug(f"[Cancel] DOMAgent fallback failed: {e}")

                # 1d. Press Escape in browser context
                try:
                    await page.keyboard.press("Escape")
                    await asyncio.sleep(0.3)
                    logger.info("[Cancel] Pressed Escape in browser.")
                    return "Canceled."
                except Exception as e:
                    logger.error(f"Error: {e}")
                    pass

    except Exception as e:
        logger.debug(f"Browser cancel failed: {e}")

    # ── Step 2: Desktop / Win32 Fallback ──────────────────────────────────────
    typed_via_pywinauto = False
    try:
        desktop = pywinauto.Desktop(backend="win32")
        dialogs = [w for w in desktop.windows() if w.window_text() in ("Save As", "Open", "Confirm Save As", "Notepad", app_name, app_name.title())]
        
        if dialogs:
            dialogs.sort(key=lambda w: w.rectangle().width() * w.rectangle().height())
            top_win = dialogs[0]
            top_win.set_focus()
            top_win.type_keys("{ESC}")
            typed_via_pywinauto = True
            
        if not typed_via_pywinauto and app_name:
            win = WindowManager()._find_window_by_title(app_name)
            if win:
                app = pywinauto.Application(backend="uia").connect(process=win.process_id())
                top_win = app.top_window()
                top_win.set_focus()
                top_win.type_keys("{ESC}")
                typed_via_pywinauto = True
    except Exception as e:
        logger.error(f"Error: {e}")
        pass
            
    if not typed_via_pywinauto:
        if app_name:
            WindowManager().focus_by_title(app_name)
        await asyncio.sleep(0.5)
        KeyboardController().press_escape()
        
    return f"Canceled {f'in {app_name}' if app_name else ''}"

async def handle_ask_llm(question: str = "", **_) -> str:
    from app.services.llm.llm_service import llm_service
    question = question.strip()
    if not llm_service.is_ready:
        return "AI assistant is not configured. Please go to Settings → AI Assistant to set up a provider."
    return await llm_service.chat(question)


async def handle_ask_and_type(question: str = "", **_) -> str:
    """Ask the LLM to draft content, then physically type it via the keyboard."""
    from app.services.llm.llm_service import llm_service
    from automation.input.keyboard_controller import KeyboardController
    question = question.strip()
    if not llm_service.is_ready:
        return "AI assistant is not configured. Please go to Settings → AI Assistant."
    generated = await llm_service.chat(question)
    KeyboardController().type_text(generated)
    return f"Drafted and typed: {generated[:80]}{'...' if len(generated) > 80 else ''}"


async def handle_vscode_terminal(**_) -> str:
    from automation.desktop.window_manager import WindowManager
    from automation.input.keyboard_controller import KeyboardController
    import asyncio
    
    wm = WindowManager()
    # Try to focus VS Code or a popular fork
    if (wm.focus_by_title("Visual Studio Code") or 
        wm.focus_by_title("Cursor") or 
        wm.focus_by_title("Windsurf") or 
        wm.focus_by_title("Antigravity") or 
        wm.focus_by_title("Voice_Controller_v1")):
        await asyncio.sleep(0.5)
        # Ctrl + ` shortcut for terminal
        KeyboardController().press_keys(["ctrl", "`"])
        return "Opened terminal in the code editor."
    return "Could not find an active code editor window."

# ─── New Integrations Handlers (Audio, Clipboard, Trash, Summary) ────────────

async def handle_delete_file(target: str = "", **_) -> str:
    from automation.desktop.file_operations import FileOperations
    return FileOperations().delete_target(target.strip())

async def handle_clipboard_copy(text: str = "", **_) -> str:
    from automation.system.clipboard import ClipboardManager
    return ClipboardManager().write_text(text)

async def handle_clipboard_read(**_) -> str:
    from automation.system.clipboard import ClipboardManager
    return ClipboardManager().read_text()

async def handle_browser_extract_text(**_) -> str:
    from automation.browser.browser_engine import BrowserEngine
    return await BrowserEngine().extract_clean_text()

async def handle_set_volume(level: str = "", **_) -> str:
    from automation.system.audio import AudioController
    import re
    match = re.search(r'\d+', level)
    if match:
        return AudioController().set_system_volume(int(match.group(0)))
    return "Please specify a volume level."

async def handle_mute(**_) -> str:
    from automation.system.audio import AudioController
    return AudioController().mute_system(mute=True)

async def handle_unmute(**_) -> str:
    from automation.system.audio import AudioController
    return AudioController().mute_system(mute=False)

async def handle_set_app_volume(app_name: str = "", level: str = "", **_) -> str:
    from automation.system.audio import AudioController
    import re
    match = re.search(r'\d+', level)
    if match:
        return AudioController().set_app_volume(app_name, int(match.group(0)))
    return f"Please specify a volume level for {app_name}."

async def handle_mute_app(app_name: str = "", **_) -> str:
    from automation.system.audio import AudioController
    return AudioController().mute_app(app_name, mute=True)

# ─── Register All Intents ────────────────────────────────────────────────────

def register_all_intents() -> None:
    """Registers all built-in commands with the CommandService."""
    from app.config import settings
    command_service._intents.clear()
    
    intents = [
        # Browser Autonomous Action (Fallback to LLM agent)
        Intent(
            name="browser_autonomous_action",
            domain="browser",
            patterns=[r"^(?:autonomous\s+)?(?:run|do|execute)\s+(?P<task>.+)$"], # Handled mostly by LLM fallback
            handler=handle_browser_autonomous_action,
            description="Use an autonomous AI agent to interact with a complex webpage",
            examples=["go to amazon and add a red umbrella to my cart", "find the cheapest flight to tokyo on google flights", "scrape the table on this page"],
            param_names=["task"],
            is_fallback=True
        ),
        # CRM Actions
        Intent(
            name="crm_login",
            domain="browser",
            patterns=[r"^(?:log\s*in|login|sign\s*in)(?:\s+to\s+(?:the\s+)?crm)?$"],
            handler=handle_crm_action,
            description="Log into the ACE CRM system",
            examples=["log in", "login", "sign in", "login to crm", "authenticate me into the system"],
        ),
        Intent(
            name="crm_logout",
            domain="browser",
            patterns=[
                r"^(?:log\s*out|logout|sign\s*out|signout|sign\s*off|log\s*off)(?:\s+of\s+(?:the\s+)?(?:crm|site|page|account|this))?$",
                r"^(?:log\s*me\s*out|sign\s*me\s*out)$",
            ],
            handler=handle_smart_logout,
            description="Log out of the current website or the ACE CRM system",
            examples=["log out", "logout", "sign out", "sign off", "log off", "log me out"],
        ),
        Intent(
            name="crm_navigate",
            domain="browser",
            patterns=[r"^(?:go\s+to|open|show)\s+(?P<module>leads|contacts|opportunities|accounts|customers|quotes|quotations|orders|products|dashboard|tasks|reports|home)$"],
            handler=handle_crm_action,
            description="Navigate to a specific module in the CRM",
            examples=["go to leads", "open contacts", "show dashboard"],
            param_names=["module"],
        ),
        Intent(
            name="crm_create_entity",
            domain="browser",
            patterns=[r"^(?:create|add|make|generate|new)\s+(?:a\s+)?(?:new\s+)?(?P<entity>lead|quote|quotation|contact|customer|account|opportunity|order|product|task)$"],
            handler=handle_crm_action,
            description="Create a new entity/record in the CRM",
            examples=["create a new lead", "new quote", "add contact"],
            param_names=["entity"],
        ),
        Intent(
            name="browser_date_filter",
            domain="browser",
            patterns=[
                # numeric-only dates:  filter date 1-4-2026 to 20-5-2026
                r"^(?:filter|set|change|update)\s+(?:the\s+)?date(?:\s+(?:range|filter|from))?\s+(?P<start_date>[\d][\d\-/]*(?:\s+\w+\s+\d{4})?)\s+to\s+(?P<end_date>[\d][\d\-/]*(?:\s+\w+\s+\d{4})?)$",
                # word-month dates:  filter date 4 may 2026 to 10 jun 2026
                r"^(?:filter|set|change|update)\s+(?:the\s+)?date(?:\s+(?:range|filter|from))?\s+(?P<start_date>\d{1,2}\s+\w+\s+\d{4})\s+to\s+(?P<end_date>\d{1,2}\s+\w+\s+\d{4})$",
                r"^(?:from|between)\s+(?P<start_date>[\d][\d\-/]*(?:\s+\w+\s+\d{4})?)\s+to\s+(?P<end_date>[\d][\d\-/]*(?:\s+\w+\s+\d{4})?)$",
                r"^(?:from|between)\s+(?P<start_date>\d{1,2}\s+\w+\s+\d{4})\s+to\s+(?P<end_date>\d{1,2}\s+\w+\s+\d{4})$",
                r"^(?:date\s+from|date\s+range)\s+(?P<start_date>[\d][\d\-/]*(?:\s+\w+\s+\d{4})?)\s+to\s+(?P<end_date>[\d][\d\-/]*(?:\s+\w+\s+\d{4})?)$",
                r"^(?:set|change)\s+(?:the\s+)?(?:date\s+)?(?:start|from)\s+(?P<start_date>[\d\-/]+(?:\s+\w+\s+\d{4})?)(?:\s+(?:and\s+)?(?:end|to)\s+(?P<end_date>[\d\-/]+(?:\s+\w+\s+\d{4})?))?$",
            ],
            handler=handle_browser_date_filter,
            description="Set a date range filter on any website (CRM, analytics, booking, reporting)",
            examples=[
                "filter date 1-4-2026 to 20-5-2026",
                "set date 1-4-2026 to 20-5-2026",
                "filter date 4 may 2026 to 10 jun 2026",
                "set date 4 may 2026 to 10 jun 2026",
                "from 1-4-2026 to 20-5-2026",
                "change date 1 April 2026 to 20 May 2026",
                "date range 1-1-2026 to 30-6-2026",
            ],
            param_names=["start_date", "end_date"],
        ),
        # Audio Control
        Intent(
            name="set_volume",
            domain="system",
            patterns=[
                r"^set\s+(?:the\s+)?(?:system\s+)?volume\s+(?:to\s+)?(?P<level>\d+(?:\s*(?:percent|%))?)$",
                r"^(?:volume\s+(?:up|down)\s+to|change\s+volume\s+to)\s+(?P<level>\d+(?:\s*(?:percent|%))?)$",
            ],
            handler=handle_set_volume,
            description="Set system volume to a specific percentage",
            examples=["set volume to 50%", "change volume to 30"],
            param_names=["level"],
        ),
        Intent(
            name="mute_system",
            domain="system",
            patterns=[r"^mute\s+(?:the\s+)?(?:system|audio|sound)?$"],
            handler=handle_mute,
            description="Mute the system audio",
            examples=["mute", "mute system"],
        ),
        Intent(
            name="unmute_system",
            domain="system",
            patterns=[r"^unmute\s+(?:the\s+)?(?:system|audio|sound)?$"],
            handler=handle_unmute,
            description="Unmute the system audio",
            examples=["unmute", "unmute system"],
        ),
        Intent(
            name="set_app_volume",
            domain="system",
            patterns=[r"^set\s+(?:the\s+)?volume\s+(?:of|for)\s+(?P<app_name>.+?)\s+(?:to\s+)?(?P<level>\d+(?:\s*(?:percent|%))?)$"],
            handler=handle_set_app_volume,
            description="Set volume for a specific application",
            examples=["set volume of spotify to 20%"],
            param_names=["app_name", "level"],
        ),
        Intent(
            name="mute_app",
            domain="system",
            patterns=[r"^mute\s+(?P<app_name>(?!the\s+system|audio|sound).+)$"],
            handler=handle_mute_app,
            description="Mute a specific application",
            examples=["mute spotify", "mute chrome"],
            param_names=["app_name"],
        ),
        # Safe Delete
        Intent(
            name="delete_file",
            domain="desktop",
            patterns=[r"^delete\s+(?:the\s+)?(?:file|folder\s+)?(?P<target>.+)$"],
            handler=handle_delete_file,
            description="Safely delete a file or folder by moving it to the Recycle Bin",
            examples=["delete the demo file", "delete reports folder"],
            param_names=["target"],
        ),
        # Clipboard
        Intent(
            name="clipboard_copy",
            domain="system",
            patterns=[
                r"^copy\s+(?P<text>.+?)\s+(?:to\s+(?:the\s+)?clipboard)$",
            ],
            handler=handle_clipboard_copy,
            description="Copy specific text to the clipboard",
            examples=["copy this is a test to clipboard"],
            param_names=["text"],
        ),
        Intent(
            name="clipboard_read",
            domain="system",
            patterns=[r"^read\s+(?:the\s+)?clipboard$", r"what(?:\s+is|'s)\s+on\s+(?:the\s+)?clipboard\??$"],
            handler=handle_clipboard_read,
            description="Read the current contents of the clipboard",
            examples=["read the clipboard"],
        ),
        # Web Summarize
        Intent(
            name="browser_extract_text",
            domain="browser",
            patterns=[
                r"^(?:extract|read|summarize)\s+(?:the\s+)?(?:text|content|page|website|article)(?:\s+from\s+(?:the\s+)?(?:page|browser))?$",
            ],
            handler=handle_browser_extract_text,
            description="Extract and purify all readable text from the current webpage",
            examples=["read the article", "extract text from the page", "summarize the website"],
        ),
        # search_google MUST be registered before search_youtube so explicit 'search <query>' always routes to Google
        Intent(
            name="search_google",
            domain="browser",
            patterns=[
                r"^search\s+(?:google|the\s+web)\s+(?:for\s+)?(?P<query>.+)$",
                r"^google\s+(?:for\s+)?(?P<query>.+)$",
                r"^find\s+(?!.*\byoutube\b)(?P<query>.+)\s+on\s+google$",
                r"^open\s+(?:the\s+)?(?:chrome|browser|edge|google\s+chrome)\s+(?:and\s+)?search\s+(?:for\s+)?(?P<query>.+)$",
                r"^search\s+(?:for\s+)?(?P<query>.+?)\s+(?:in|on)\s+(?:the\s+)?(?:chrome|browser|edge|google\s+chrome)$",
                r"^search\s+(?:for\s+)?(?P<query>(?!lead\b|leads\b|opportunity\b|opportunities\b|customer\b|customers\b|order\b|orders\b|quote\b|quotes\b|quotation\b|quotations\b|task\b|tasks\b|account\b|accounts\b|contact\b|contacts\b|product\b|products\b).+)$",
            ],
            handler=handle_search_google,
            description="Search Google in the browser",
            examples=["search for python tutorials", "google the weather", "search ace crm", "open chrome search ace payroll"],
            param_names=["query"],
        ),
        Intent(
            name="search_youtube",
            domain="browser",
            patterns=[
                r"(?:search|find|play)\s+(?P<query>.+)\s+on\s+youtube",
                r"(?:open\s+)?youtube\s+(?:and\s+)?(?:search|find|play)\s+(?:for\s+)?(?P<query>.+)",
                r"(?:search|find|play)\s+on\s+youtube\s+(?:for\s+)?(?P<query>.+)",
                r"youtube\s+(?:search\s+)?(?P<query>.+)",
            ],
            handler=handle_search_youtube,
            description="Search YouTube in the browser",
            examples=["search lofi music on youtube", "youtube python tutorial"],
            param_names=["query"],
        ),

        Intent(
            name="open_website",
            domain="browser",
            patterns=[
                r"(?:open|go to|visit|navigate to)\s+(?P<url>(?:https?://)?[\w\-\.]+\.\w{2,}(?:/\S*)?)",
                r"(?:open|go to|visit)\s+(?P<url>youtube|google|github|netflix|spotify|twitter|facebook|gmail|amazon|reddit|linkedin)"
            ],
            handler=handle_open_website,
            description="Open a website URL in the browser",
            examples=["open github.com", "go to youtube.com", "visit google.com"],
            param_names=["url"],
        ),
        Intent(
            name="browser_play_pause",
            patterns=[
                r"(?:play|pause)\s+(?:the\s+)?(?:video|music|song)",
            ],
            handler=handle_browser_play_pause,
            description="Play or pause media in the browser",
            examples=["play the video", "pause music"],
        ),
        Intent(
            name="browser_go_back",
            domain="browser",
            patterns=[
                r"go\s+back",
                r"previous\s+page",
            ],
            handler=handle_browser_go_back,
            description="Navigate back in the browser",
            examples=["go back", "go to previous page"],
        ),
        Intent(
            name="browser_refresh",
            domain="browser",
            patterns=[
                r"^(?:refresh|reload)(?:\s+(?:this|the\s+)?(?:page|tab|website))?$",
            ],
            handler=handle_browser_refresh,
            description="Refresh or reload the current webpage",
            examples=["refresh the page", "reload", "refresh", "reload the tab"],
        ),
        Intent(
            name="browser_click_result",
            domain="browser",
            patterns=[
                r"(?:click|open)\s+(?:the\s+)?(?P<index>first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|\d+(?:st|nd|rd|th)?)\s+(?:result|link|video|item)",
            ],
            handler=handle_browser_click_result,
            description="Click the nth search result on Google or YouTube",
            examples=["click the first result", "open the fourth link", "click the 2nd video"],
            param_names=["index"]
        ),
        Intent(
            name="read_page_title",
            patterns=[
                r"(?:what is|read|get)\s+(?:the\s+)?page\s+title",
                r"what page am i on",
                r"read\s+title"
            ],
            handler=handle_read_page_title,
            description="Read the title of the current webpage",
            examples=["what is the page title", "read the page title"],
        ),
        Intent(
            name="extract_page_content",
            patterns=[
                r"(?:extract|read|get)\s+(?:the\s+)?(?:page\s+)?content",
                r"(?:extract|read|get)\s+(?:the\s+)?(?:page\s+)?text",
                r"what does this page say"
            ],
            handler=handle_extract_page_content,
            description="Extract readable text from the current webpage",
            examples=["extract the page content", "read the page text"],
        ),
        Intent(
            name="analyze_screen",
            patterns=[
                r"(?:what\s+is|what's|describe)\s+(?:on\s+)?(?:my\s+)?screen",
                r"read\s+(?:the\s+)?(?:my\s+)?screen",
            ],
            handler=handle_analyze_screen,
            description="Use AI vision to describe what is currently on the screen",
            examples=["what is on my screen?", "read my screen"],
        ),
        Intent(
            name="open_folder",
            domain="desktop",
            patterns=[
                # "open folder <name>" or "open directory <name>" — keyword FIRST (highest priority)
                r"open\s+(?:the\s+)?(?:folder|directory)\s+(?P<path>.+)",
                # "show me <name> folder"
                r"show\s+(?:me\s+)?(?:the\s+)?(?P<path>[\w\s]+?)\s+(?:folder|directory)",
                # "open <name> folder" — keyword at END; guard ensures path doesn't start with 'folder'
                r"open\s+(?:the\s+)?(?P<path>(?!folder\b|directory\b)[\w\s]+?)\s+(?:folder|directory)",
                # "go to downloads", "go to documents"
                r"go\s+to\s+(?P<path>downloads|documents|desktop|pictures|music|videos|home)",
            ],
            handler=handle_open_folder,
            description="Open a folder in Windows Explorer",
            examples=["open the payroll folder", "open folder downloads", "show me documents folder"],
            param_names=["path"],
        ),
        Intent(
            name="search_file",
            domain="desktop",
            is_fallback=True,
            patterns=[
                r"^(?:search|find|locate|open)\s+(?:for\s+)?(?:the\s+)?(?P<explicit_type>file|folder|app|application|program|pdf|document|doc|image|video|spreadsheet|notepad|excel|word|powerpoint|text)\s+(?P<file_name>.+)$",
                r"^(?:search|find|locate)\s+(?:for\s+)?(?:the\s+)?(?P<file_name>.+)$",
            ],
            handler=handle_search_file,
            description="Search for a file, folder, or application",
            examples=["search for invoice pdf", "find the file report.docx", "search payroll"],
            param_names=["file_name", "explicit_type"],
        ),
        Intent(
            name="open_project",
            patterns=[
                r"open\s+(?:the\s+)?(?:my\s+)?(?P<project_name>.+?)\s+project",
                r"open\s+(?:the\s+)?(?:my\s+)?project\s+(?P<project_name>.+)",
            ],
            handler=handle_open_project,
            description="Open a software project in VS Code",
            examples=["open my react project", "open the website project"],
            param_names=["project_name"],
        ),
        Intent(
            name="vscode_terminal",
            patterns=[
                r"open\s+(?:the\s+)?terminal",
                r"show\s+(?:the\s+)?terminal",
            ],
            handler=handle_vscode_terminal,
            description="Open the VS Code integrated terminal",
            examples=["open the terminal", "show terminal"],
        ),
        Intent(
            name="create_project",
            patterns=[
                r"create\s+(?:a\s+)?(?:the\s+)?(?:new\s+)?(?P<project_type>\w+)\s+project(?:\s+(?:called|named)\s+(?P<project_name>.+))?",
                r"make\s+(?:a\s+)?(?:the\s+)?(?:new\s+)?(?P<project_type>\w+)\s+project(?:\s+(?:called|named)\s+(?P<project_name>.+))?",
            ],
            handler=handle_create_project,
            description="Create a new software project (like React, Next.js) on the Desktop",
            examples=["create a new react project", "create a next project called my website"],
            param_names=["project_type", "project_name"],
        ),
        Intent(
            name="browser_new_tab",
            domain="browser",
            patterns=[
                r"^(?:(?:open|create|make)\s+(?:a\s+)?)?(?:new|another)\s+tab$"
            ],
            handler=handle_browser_new_tab,
            description="Open a new browser tab",
            examples=["open a new tab", "create a new tab", "new tab", "create another tab"]
        ),
        Intent(
            name="browser_switch_tab",
            domain="browser",
            patterns=[
                r"^(?:switch|go)\s+to\s+(?:the\s+)?(?P<tab_identifier>first|second|third|fourth|fifth|last|next|previous|\d+(?:st|nd|rd|th)?)\s+tab$",
                r"^(?:switch|go)\s+to\s+tab\s+(?P<tab_identifier>\d+)$",
                r"^switch\s+(?P<tab_identifier>.+)\s+tab$"
            ],
            handler=handle_browser_switch_tab,
            description="Switch to a specific browser tab by number or position",
            examples=["switch to the first tab", "switch to tab 2", "switch last tab", "switch next tab"],
            param_names=["tab_identifier"]
        ),
        Intent(
            name="browser_close_all_tabs",
            domain="browser",
            patterns=[r"^close\s+all\s+tabs$"],
            handler=handle_browser_close_all_tabs,
            description="Close all browser tabs",
            examples=["close all tabs"]
        ),
        Intent(
            name="browser_hover",
            patterns=[r"hover\s+over\s+(?:the\s+)?(?P<selector>.+)"],
            handler=handle_browser_hover,
            description="Hover over an element in the browser",
            examples=["hover over the menu"],
            param_names=["selector"]
        ),
        Intent(
            name="browser_clipboard",
            patterns=[
                r"(?P<action>copy|cut|paste|select all)\s+(?:the\s+)?(?:selected\s+)?(?:text)?",
            ],
            handler=handle_browser_clipboard,
            description="Perform clipboard actions in browser",
            examples=["copy selected text", "paste", "select all"],
            param_names=["action"]
        ),
        Intent(
            name="browser_scroll_variable",
            patterns=[r"scroll\s+(?P<direction>down|up)\s+(?:a\s+)?(?P<magnitude>little|lot|more)"],
            handler=handle_browser_scroll_variable,
            description="Scroll the browser by a variable amount",
            examples=["scroll down a little", "scroll up more"],
            param_names=["direction", "magnitude"]
        ),
        Intent(
            name="browser_fill_form",
            patterns=[r"fill\s+(?:the\s+)?form(?:\s+with\s+(?P<context>.+))?"],
            handler=handle_browser_fill_form,
            description="Use AI to fill out a form based on context",
            examples=["fill the form with my details"],
            param_names=["context"]
        ),
        Intent(
            name="browser_interact_checkbox",
            patterns=[r"(?P<action>check|uncheck)\s+(?:the\s+)?checkbox"],
            handler=handle_browser_interact_checkbox,
            description="Check or uncheck a checkbox",
            examples=["check the checkbox", "uncheck the checkbox"],
            param_names=["action"]
        ),
        Intent(
            name="browser_list_options",
            patterns=[
                r"(?:list\s+out|display|show)(?:\s+the)?\s+(?P<element>.+?)(?:\s+(?:options|list|dropdown))?$",
            ],
            handler=handle_browser_list_options,
            description="Click a dropdown or select menu to display its options",
            examples=["list out the product", "display the options", "show product list"],
            param_names=["element"]
        ),
        Intent(
            name="browser_select_option",
            patterns=[
                r"select\s+(?:the\s+)?(?P<option>.+?)(?:\s+(?:option|from\s+dropdown|from\s+list))?$",
            ],
            handler=handle_browser_select_option,
            description="Select a specific option from a dropdown or list",
            examples=["select the first option", "select warm", "select last option"],
            param_names=["option"]
        ),
        Intent(
            name="browser_summarize_page",
            patterns=[r"summarize\s+(?:this\s+)?page", r"extract\s+(?:all\s+)?headings", r"read\s+(?:the\s+)?first\s+paragraph"],
            handler=handle_browser_summarize_page,
            description="Summarize the current page using AI",
            examples=["summarize this page"]
        ),
        Intent(
            name="browser_full_screenshot",
            patterns=[r"take\s+(?:a\s+)?full\s+page\s+screenshot"],
            handler=handle_browser_full_screenshot,
            description="Take a full page screenshot",
            examples=["take a full page screenshot"]
        ),
        Intent(
            name="browser_window_state",
            patterns=[r"(?P<state>restart|maximize|minimize|restore)\s+(?:the\s+)?(?:browser|window)"],
            handler=handle_browser_window_state,
            description="Change browser window state or restart",
            examples=["restart browser", "maximize window"],
            param_names=["state"]
        ),
        Intent(
            name="crm_clear_search",
            domain="browser",
            patterns=[
                r"^(?:clear|reset|remove|erase|wipe)\s+(?:the\s+)?(?:search|filter|query|results?|dates?|date\s+filter)$",
                r"^(?:clear|reset)\s+(?:search|date)(?:\s+(?:bar|box|field|input|filter))?$",
                r"^(?:show|display)\s+all\s+(?:leads|records|results|entries|contacts|accounts|orders|quotes)$",
            ],
            handler=handle_crm_clear_search,
            description="Clear the search/filter input or date filter on the current CRM page",
            examples=["clear search", "reset search", "clear filter", "clear dates", "reset date filter"],
        ),
        Intent(
            name="browser_clear_marks",
            domain="browser",
            patterns=[r"clear\s+highlights", r"remove\s+marks"],
            handler=handle_browser_clear_marks,
            description="Clear all element highlights",
            examples=["clear highlights", "remove marks"]
        ),
        Intent(
            name="browser_double_click",
            patterns=[r"double\s+click"],
            handler=handle_browser_double_click,
            description="Double click the mouse",
            examples=["double click the image"]
        ),
        Intent(
            name="browser_right_click",
            patterns=[r"right\s+click"],
            handler=handle_browser_right_click,
            description="Right click the mouse",
            examples=["right click here"]
        ),
        Intent(
            name="browser_press_key",
            patterns=[r"press\s+(?P<key>enter|escape|tab|space|backspace)"],
            handler=handle_browser_press_key,
            description="Press a specific key",
            examples=["press escape", "press tab"],
            param_names=["key"]
        ),
        Intent(
            name="browser_wait_for",
            patterns=[r"wait\s+for\s+(?:the\s+)?(?P<target>.+)"],
            handler=handle_browser_wait_for,
            description="Wait for an element or condition",
            examples=["wait for login button", "wait for search results"],
            param_names=["target"]
        ),
        Intent(
            name="browser_download",
            domain="browser",
            patterns=[r"download\s+(?:this\s+)?file"],
            handler=handle_browser_download,
            description="Handle file download",
            examples=["download this file"]
        ),
        Intent(
            name="browser_upload",
            domain="browser",
            patterns=[r"upload\s+(?:a\s+)?file"],
            handler=handle_browser_upload,
            description="Handle file upload",
            examples=["upload a file"]
        ),
        # ---> ADD THE NEW INTENT HERE <---
        Intent(
            name="browser_paginate",
            domain="browser",
            patterns=[
                r"^(?:go\s+to|click|navigate\s+to)\s+(?:the\s+)?(?P<direction>next|previous|prev|first|last)\s+page$",
                r"^(?P<direction>next|previous|prev|first|last)\s+page$",
                r"^(?:go\s+to|click|navigate\s+to)\s+page\s+(?P<page_num>\d+)$",
                r"^page\s+(?P<page_num>\d+)$"
            ],
            handler=handle_browser_paginate,
            description="Navigate through pagination controls (next, previous, specific page)",
            examples=["go to next page", "go to page 3", "previous page", "first page"],
            param_names=["direction", "page_num"]
        ),
        # ── Dismiss / Cancel / Close Popup — HIGH PRIORITY (before crm_workflow) ──
       Intent(
            name="dismiss_overlay",
            domain="browser",
            patterns=[
                r"^(?:cancel|escape|close\s+(?:the\s+)?(?:popup|overlay|modal|dialog|video|window|ad|card|box|banner)|dismiss|press\s+escape|close\s+it)(?:\s+.*)?$",
            ],
            handler=handle_cancel,
            description="Close a popup, overlay, modal, or dialog by pressing Escape or clicking X",
            examples=["cancel", "escape", "close the popup", "close the overlay card"],
        ),
        Intent(
            name="crm_workflow",
            patterns=[
                r"^(?P<action>(?:open|launch|start|go\s+to)\s+(?:my\s+)?(?:ace\s+)?crm)$",
                r"^(?P<action>log\s*(?:in|into)(?:\s+(?:to\s+)?(?:ace\s+)?crm)?)$",
                r"^(?P<action>(?:create|add|make|generate)(?:\s+(?:a\s+)?(?:new\s+)?)?\s+(?:lead|quote|quotation|contact|customer|account|opportunity|order|product|task)(?:\s+.*)?)$",
                r"^(?P<action>new\s+(?:lead|quote|quotation|contact|customer|account|opportunity|order|product|task)(?:\s+.*)?)$",
                r"^(?P<action>(?:go\s+to|open|show)\s+(?:the\s+)?(?:leads|contacts|opportunities|accounts|customers|quotes|quotations|orders|products|dashboard|tasks|reports|home)(?:\s+module|page)?)$",
                r"^(?P<action>(?:leads|contacts|opportunities|accounts|customers|quotes|quotations|orders|products|dashboard|tasks|reports|home))$",
                r"^(?P<action>search\s+(?:lead|opportunity|customer|order|quote|task|account|contact)\s+(?:.+))$",
                r"^(?P<action>(?:open|select|click)\s+(?:first|top)\s+(?:record|row|lead|opportunity|customer|order|quote|task|account|contact))$",
                r"^(?P<action>(?:edit|assign)\s+(?:lead|opportunity|customer|order|quote|task|account|contact)(?:\s+.*)?)$",
                r"^(?P<action>update\s+(?:status|lead|opportunity|customer|order|quote|task|account|contact)(?:\s+.*)?)$",
                # NOTE: "cancel" removed — handled by cancel_dialog intent (presses Escape instantly)
            ],
            handler=handle_crm_action,
            description="Automate CRM workflows in the browser",
            examples=["open my crm", "create a new lead", "open ace crm", "login", "create new quote", "search lead john"],
            param_names=["action"]
        ),
        Intent(
            name="run_dev_server",
            patterns=[
                r"run\s+(?:the\s+)?(?:dev\s+)?(?:server|project|app)",
                r"start\s+(?:the\s+)?(?:dev\s+)?(?:server|project|app)",
                r"run\s+it",
                r"start\s+it"
            ],
            handler=handle_run_dev_server,
            description="Run the development server for the currently active project",
            examples=["run the dev server", "start the project", "run it"],
        ),
        Intent(
            name="open_dev_server",
            patterns=[
                r"open\s+(?:the\s+)?(?:dev\s+)?(?:server|app|project)\s+(?:in\s+)?(?:the\s+)?browser",
                r"open\s+it\s+(?:in\s+)?(?:the\s+)?browser",
            ],
            handler=handle_open_dev_server,
            description="Open the currently running dev server in the web browser",
            examples=["open it in browser", "open the dev server in the browser"],
        ),

        Intent(
            name="open_app",
            domain="desktop",
            is_fallback=True,
            patterns=[
                r"^(?:open|launch|start)\s+(?!(?:my\s+)?(?:ace\s+)?crm\b)(?P<app>.+)$",
            ],
            handler=handle_open_app,
            description="Open a desktop application",
            examples=["open notepad", "launch vs code", "start chrome", "open spotify"],
            param_names=["app"],
        ),
        Intent(
            name="close_heavy_apps",
            domain="desktop",
            patterns=[
                r"close\s+(?:all\s+)?heavy\s+(?:applications|apps)",
                r"free\s+(?:up\s+)?(?:some\s+)?(?:memory|ram)",
                r"kill\s+heavy\s+(?:applications|apps)"
            ],
            handler=handle_close_heavy_apps,
            description="Close heavy applications taking up excessive memory",
            examples=["close heavy applications", "free up some memory", "kill heavy apps"],
        ),
        Intent(
            name="close_folder",
            patterns=[
                r"close\s+(?:the\s+)?(?:folder|directory)\s+(?P<path>.+)",
                r"close\s+(?:the\s+)?(?P<path>[\w\s]+?)\s+(?:folder|directory)",
            ],
            handler=handle_close_folder,
            description="Close an open folder window",
            examples=["close the folder friday", "close downloads folder"],
            param_names=["path"],
        ),
        Intent(
            name="close_app",
            domain="desktop",
            patterns=[
                r"close\s+(?P<app>.+)",
                r"quit\s+(?P<app>.+)",
                r"exit\s+(?P<app>.+)",
                r"kill\s+(?P<app>.+)",
            ],
            handler=handle_close_app,
            description="Close a running application",
            examples=["close notepad", "quit chrome", "kill explorer"],
            param_names=["app"],
        ),

        Intent(
            name="create_folder",
            patterns=[
                r"(?:create|make)\s+(?:a\s+|the\s+)?(?:new\s+)?(?:folder|directory)(?:\s+(?:named|name))?\s+(?P<folder_name>.+?)(?:\s+(?:in|on)\s+(?:the\s+)?(?:drive\s+)?(?P<drive>[A-Za-z])(?:\s+drive)?)?$",
            ],
            handler=handle_create_folder,
            description="Create a new folder on the Desktop or a specific drive",
            examples=["create a new folder demo45 on drive E", "make directory test in D drive", "create folder my docs"],
            param_names=["folder_name", "drive"],
        ),
        Intent(
            name="run_command",
            patterns=[
                r"run\s+(?:command\s+)?(?P<cmd>.+)",
                r"execute\s+(?P<cmd>.+)",
                r"terminal\s+(?P<cmd>.+)",
            ],
            handler=handle_run_command,
            description="Run a terminal command",
            examples=["run ipconfig", "execute ping google.com", "run dir"],
            param_names=["cmd"],
        ),
        Intent(
            name="volume_up",
            domain="desktop",
            patterns=[r"(?:volume|turn)\s+up", r"increase\s+volume", r"louder"],
            handler=handle_volume_up,
            description="Increase system volume",
            examples=["volume up", "turn up the volume", "louder"],
        ),
        Intent(
            name="volume_down",
            domain="desktop",
            patterns=[r"(?:volume|turn)\s+down", r"decrease\s+volume", r"quieter"],
            handler=handle_volume_down,
            description="Decrease system volume",
            examples=["volume down", "turn down the volume", "quieter"],
        ),
        Intent(
            name="mute",
            patterns=[r"mute", r"silence", r"shut up"],
            handler=handle_mute,
            description="Mute system audio",
            examples=["mute", "silence", "mute volume"],
        ),
        Intent(
            name="minimize_window",
            patterns=[r"minimize\s+(?:window|this|the window)?$"],
            handler=handle_minimize_window,
            description="Minimize the active window",
            examples=["minimize window", "minimize this"],
        ),
        Intent(
            name="minimize_app",
            domain="desktop",
            patterns=[r"minimize\s+(?:the\s+)?(?P<app>.+)"],
            handler=handle_minimize_app,
            description="Minimize a specific application by name",
            examples=["minimize vscode", "minimize chrome"],
            param_names=["app"],
        ),
        Intent(
            name="maximize_window",
            patterns=[r"maximize\s+(?:window|this|the window)?$"],
            handler=handle_maximize_window,
            description="Maximize the active window",
            examples=["maximize window", "fullscreen"],
        ),
        Intent(
            name="maximize_app",
            domain="desktop",
            patterns=[r"maximize\s+(?:the\s+)?(?P<app>.+)"],
            handler=handle_maximize_app,
            description="Maximize a specific application by name",
            examples=["maximize vscode", "maximize chrome"],
            param_names=["app"],
        ),
        Intent(
            name="close_window",
            domain="desktop",
            patterns=[r"close\s+(?:this\s+)?window", r"close\s+tab"],
            handler=handle_close_window,
            description="Close the active window",
            examples=["close window", "close this window"],
        ),
        Intent(
            name="copy",
            patterns=[r"copy\s+(?:that|this|selection)?", r"ctrl\s*\+?\s*c"],
            handler=handle_clipboard_copy,
            description="Copy selected text to clipboard",
            examples=["copy that", "copy this", "copy"],
        ),
        Intent(
            name="paste",
            patterns=[r"paste\s+(?:that|this|it)?", r"ctrl\s*\+?\s*v"],
            handler=handle_clipboard_paste,
            description="Paste from clipboard",
            examples=["paste", "paste that", "paste it"],
        ),
        Intent(
            name="screenshot",
            patterns=[r"(?:take\s+a?\s*)?screenshot", r"capture\s+screen"],
            handler=handle_screenshot,
            description="Take a screenshot",
            examples=["take a screenshot", "screenshot", "capture screen"],
        ),
        Intent(
            name="sleep",
            patterns=[r"(?:put\s+)?(?:the\s+)?(?:computer|system|pc)\s+(?:to\s+)?sleep", r"sleep\s+(?:mode|now)?"],
            handler=handle_system_sleep,
            description="Put the system to sleep",
            examples=["sleep", "sleep now", "put the computer to sleep"],
        ),
        Intent(
            name="shutdown",
            patterns=[r"shut\s*down\s+(?:the\s+)?(?:computer|system|pc|now)?", r"power\s+off"],
            handler=handle_system_shutdown,
            description="Shut down the system",
            examples=["shutdown", "shut down the computer", "power off"],
        ),
        Intent(
            name="restart",
            patterns=[r"restart\s+(?:the\s+)?(?:computer|system|pc|now)?", r"reboot"],
            handler=handle_system_restart,
            description="Restart the system",
            examples=["restart", "restart the computer", "reboot"],
        ),
        Intent(
            name="set_filename",
            patterns=[
                r"save\s+(?:the\s+)?(?P<app_name>(?!file\b|document\b|changes\b)[\w\s]+?)\s+(?:as|name\s+it|call\s+it)\s+(?P<text>.+)",
                r"(?:save\s+(?:the\s+)?(?:file|document|changes)?\s*)?(?:as|name\s+it|call\s+it)\s+(?P<text>.+)",
                r"(?:name|call)\s+(?:it|the\s+file)\s+(?P<text>.+)",
                r"(?:enter|set|give)\s+(?:the\s+)?(?:file\s+name|name)\s+(?:to\s+)?(?:as\s+)?(?P<text>.+)",
                r"file\s+name\s+(?P<text>.+)",
            ],
            handler=handle_set_filename,
            description="Type a file name and confirm the save",
            examples=["save the file as document1", "name it report", "set the file name to report"],
            param_names=["text", "app_name"],
        ),
        Intent(
            name="type_text",
            domain="desktop",
            patterns=[
                r"type\s+(?:the\s+)?(?:text\s+)?(?P<text>.+)",
                r"write\s+(?P<text>.+)",
                r"enter\s+(?P<text>.+)",
            ],
            handler=handle_type_text,
            description="Type specific text using the keyboard or browser DOM",
            examples=["type hello world", "enter ace into company name"],
            param_names=["text", "app_name"],
        ),
        Intent(
            name="lock_screen",
            domain="desktop",
            patterns=[r"lock\s+(?:the\s+)?(?:screen|computer|pc)?", r"lock\s+now"],
            handler=handle_lock_screen,
            description="Lock the screen",
            examples=["lock screen", "lock the computer", "lock now"],
        ),
        Intent(
            name="click_text",
            domain="browser",
            patterns=[
                r"(?:click|tap)\s+(?:on\s+)?(?P<text>.+)",
                r"(?:go\s+to|navigate\s+to)\s+(?P<text>[^\.]+)$"
            ],
            handler=handle_click_text,
            description="Click on specific text on the screen using OCR",
            examples=["click on submit", "tap next", "click login"],
            param_names=["text"],
        ),
        Intent(
            name="click",
            patterns=[r"^click$", r"^left\s+click$", r"^tap$"],
            handler=handle_click,
            description="Left click the mouse",
            examples=["click", "left click"],
        ),
        Intent(
            name="double_click",
            patterns=[r"^double\s+click$"],
            handler=handle_double_click,
            description="Double click the mouse",
            examples=["double click"],
        ),
        Intent(
            name="right_click",
            patterns=[r"^right\s+click$"],
            handler=handle_right_click,
            description="Right click the mouse",
            examples=["right click"],
        ),
        Intent(
            name="scroll_up",
            patterns=[r"scroll\s+up", r"go\s+up"],
            handler=handle_scroll_up,
            description="Scroll up the screen",
            examples=["scroll up", "go up"],
        ),
        Intent(
            name="scroll_down",
            patterns=[r"scroll\s+down", r"go\s+down"],
            handler=handle_scroll_down,
            description="Scroll down the screen",
            examples=["scroll down", "go down"],
        ),
        Intent(
            name="scroll_top",
            patterns=[r"scroll\s+(?:to\s+)?(?:top|first)"],
            handler=handle_scroll_top,
            description="Scroll to the top of the screen",
            examples=["scroll top", "scroll to top", "scroll first"],
        ),
        Intent(
            name="scroll_bottom",
            patterns=[r"scroll\s+(?:to\s+)?(?:bottom|end|last)"],
            handler=handle_scroll_bottom,
            description="Scroll to the bottom of the screen",
            examples=["scroll bottom", "scroll last", "scroll end"],
        ),
        Intent(
            name="ask_llm",
            patterns=[
                r"(?:ask\s+(?:ai|jarvis|ace)|tell\s+me)\s+(?P<question>.+)",
                r"(?:what\s+(?:is|are|does|do)|how\s+(?:do|does|can|to))\s+(?P<question>.+)\??",
                r"(?:explain|describe|summarize)\s+(?P<question>.+)",
            ],
            handler=handle_ask_llm,
            description="Ask the AI assistant a question or have a conversation",
            examples=["tell me a joke", "ask ai what is Python", "explain machine learning"],
            param_names=["question"],
        ),
        Intent(
            name="ask_and_type",
            patterns=[
                r"(?:draft|write|compose|generate)\s+(?:and\s+type\s+)?(?P<question>(?:an?\s+)?(?:email|message|letter|report|code|essay|reply|response).+)",
            ],
            handler=handle_ask_and_type,
            description="Ask AI to draft content and physically type it in the active window",
            examples=["draft an email asking for Friday off", "write a professional response"],
            param_names=["question"],
        ),
        Intent(
            name="submit",
            domain="desktop",
            patterns=[
                r"(?:submit|press\s+enter)\s+(?:in\s+)?(?:the\s+)?(?P<app_name>.+)",
                r"submit", r"press\s+enter", r"^enter$"
            ],
            handler=handle_submit,
            description="Press the Enter key",
            examples=["submit", "press enter", "submit in notepad"],
            param_names=["app_name"],
        ),
        Intent(
            name="dont_save",
            domain="desktop",
            patterns=[
                r"(?:don't|do\s+not)\s+save\s+(?:in\s+)?(?:the\s+)?(?P<app_name>.+)",
                r"don't\s+save", r"do\s+not\s+save"
            ],
            handler=handle_dont_save,
            description="Press 'N' to select Don't Save in dialogs",
            examples=["don't save", "do not save", "don't save in notepad"],
            param_names=["app_name"],
        ),
        Intent(
            name="save_file",
            domain="desktop",
            patterns=[
                r"save\s+(?:the\s+)?(?:file|document|changes)\s+(?:in\s+)?(?:the\s+)?(?P<app_name>.+)",
                r"save\s+(?:the\s+)?(?P<app_name>(?!file|document|changes).+)",
                r"save\s+(?:the\s+)?(?:file|document|changes)?", r"save"
            ],
            handler=handle_save,
            description="Press Ctrl+S or Enter to save",
            examples=["save", "save file", "save the changes", "save the notepad"],
            param_names=["app_name"],
        ),
        Intent(
            name="greeting",
            patterns=[
                rf"^(?P<question>(?:hello|hi|hey|greetings)(?:\s+(?:{settings.wake_word}|ace|assistant|ai|there))?)$",
                rf"^(?P<question>{settings.wake_word}|hey\s+{settings.wake_word}|ace|assistant|ai)$"
            ],
            handler=handle_ask_llm,
            description="Respond to simple greetings conversationally",
            examples=["hello", "hi ace", "hey"],
            param_names=["question"],
        ),
        Intent(
            name="browser_click_link",
            domain="browser",
            patterns=[
                r"open\s+(?:the\s+)?(?P<text>.+?)\s+(?:link|tab|button|element)$"
            ],
            handler=handle_click_text,
            description="Open or click a specific link/tab in the browser using the DOM Agent",
            examples=["open the linkedin link", "open the fourth tab"],
            param_names=["text"],
        ),
    ]

    for intent in intents:
        command_service.register(intent)

    logger.info(f"✅ Registered {len(intents)} built-in command intents")
