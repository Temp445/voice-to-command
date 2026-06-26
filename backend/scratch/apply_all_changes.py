import os

def modify_intent_registry():
    path = "app/services/intent_registry.py"
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    replacements = [
        (
            """        # 1. Try semantic combobox
        combobox = page.get_by_role('combobox', name=re.compile(element, re.IGNORECASE))
        if await combobox.count() == 1:
            await combobox.first.click(force=True)
            return f"Opened {element} dropdown.\"""",
            """        # 1. Try semantic combobox
        combobox = page.get_by_role('combobox', name=re.compile(element, re.IGNORECASE))
        if await combobox.count() == 1:
            from automation.browser.browser_engine import BrowserEngine
            await BrowserEngine()._animate_action(page, combobox.first, "click")
            await combobox.first.click(force=True)
            return f"Opened {element} dropdown.\""""
        ),
        (
            """                else:
                    await loc.evaluate(\"\"\"(el) => {
                        const select = el.closest('select');
                        if (select) {
                            select.value = el.value;
                            select.dispatchEvent(new Event('change', { bubbles: true }));
                        }
                    }\"\"\")
            else:
                await loc.click(force=True)""",
            """                else:
                    await loc.evaluate(\"\"\"(el) => {
                        const select = el.closest('select');
                        if (select) {
                            select.value = el.value;
                            select.dispatchEvent(new Event('change', { bubbles: true }));
                        }
                    }\"\"\")
            else:
                from automation.browser.browser_engine import BrowserEngine
                await BrowserEngine()._animate_action(page, loc, "click")
                await loc.click(force=True)"""
        ),
        (
            """        for sel in date_clear_candidates:
            try:
                loc = page.locator(sel).first
                if await loc.is_visible():
                    await loc.click(timeout=2000)""",
            """        for sel in date_clear_candidates:
            try:
                loc = page.locator(sel).first
                if await loc.is_visible():
                    from automation.browser.browser_engine import BrowserEngine
                    await BrowserEngine()._animate_action(page, loc, "click")
                    await loc.click(timeout=2000)"""
        ),
        (
            """        for sel in selectors:
            try:
                loc = page.locator(sel).first
                if await loc.is_visible():
                    await loc.click(click_count=3, timeout=2000)""",
            """        for sel in selectors:
            try:
                loc = page.locator(sel).first
                if await loc.is_visible():
                    from automation.browser.browser_engine import BrowserEngine
                    await BrowserEngine()._animate_action(page, loc, "click")
                    await loc.click(click_count=3, timeout=2000)"""
        ),
        (
            """    for sel in clear_candidates:
        try:
            loc = page.locator(sel).first
            if await loc.is_visible():
                await loc.click(timeout=2000)""",
            """    for sel in clear_candidates:
        try:
            loc = page.locator(sel).first
            if await loc.is_visible():
                from automation.browser.browser_engine import BrowserEngine
                await BrowserEngine()._animate_action(page, loc, "click")
                await loc.click(timeout=2000)"""
        ),
        (
            """            for i in range(count):
                el = loc.nth(i)
                if await el.is_visible() and not await el.is_disabled():
                    await el.click(timeout=1500)
                    await asyncio.sleep(0.5)""",
            """            for i in range(count):
                el = loc.nth(i)
                if await el.is_visible() and not await el.is_disabled():
                    from automation.browser.browser_engine import BrowserEngine
                    await BrowserEngine()._animate_action(page, el, "click")
                    await el.click(timeout=1500)
                    await asyncio.sleep(0.5)"""
        ),
        (
            """            if len(sorted_inputs) >= 2 and index < len(sorted_inputs):
                el, itype = sorted_inputs[index]
                val = value_iso if itype == "date" else value_dmy
                await el.click(click_count=3, timeout=1500)
                await el.fill(val, timeout=1500)""",
            """            if len(sorted_inputs) >= 2 and index < len(sorted_inputs):
                el, itype = sorted_inputs[index]
                val = value_iso if itype == "date" else value_dmy
                from automation.browser.browser_engine import BrowserEngine
                await BrowserEngine()._animate_action(page, el, "click")
                await el.click(click_count=3, timeout=1500)
                await el.fill(val, timeout=1500)"""
        ),
        (
            """                        el = loc.nth(i)
                        if await el.is_visible():
                            itype = await el.get_attribute("type") or "text"
                            val = value_iso if itype == "date" else value_dmy
                            await el.triple_click(timeout=1500)
                            await el.fill(val, timeout=1500)""",
            """                        el = loc.nth(i)
                        if await el.is_visible():
                            itype = await el.get_attribute("type") or "text"
                            val = value_iso if itype == "date" else value_dmy
                            from automation.browser.browser_engine import BrowserEngine
                            await BrowserEngine()._animate_action(page, el, "click")
                            await el.triple_click(timeout=1500)
                            await el.fill(val, timeout=1500)"""
        ),
        (
            """        if not start_done:
            await page.mouse.click(info["x"], info["y"])
            await asyncio.sleep(0.5)
            start_done = await _navigate_to_and_pick(s)
            if start_done:
                await _close_calendar_popup()
            continue

        if start_done and not end_done:
            await page.mouse.click(info["x"], info["y"])
            await asyncio.sleep(0.5)""",
            """        if not start_done:
            from automation.browser.browser_engine import BrowserEngine
            await BrowserEngine()._animate_action(page, {"x": info["x"], "y": info["y"]}, "click")
            await page.mouse.click(info["x"], info["y"])
            await asyncio.sleep(0.5)
            start_done = await _navigate_to_and_pick(s)
            if start_done:
                await _close_calendar_popup()
            continue

        if start_done and not end_done:
            from automation.browser.browser_engine import BrowserEngine
            await BrowserEngine()._animate_action(page, {"x": info["x"], "y": info["y"]}, "click")
            await page.mouse.click(info["x"], info["y"])
            await asyncio.sleep(0.5)"""
        ),
        (
            """                        if await el.is_visible():
                            await el.scroll_into_view_if_needed(timeout=1000)
                            await el.click(timeout=2000)""",
            """                        if await el.is_visible():
                            await el.scroll_into_view_if_needed(timeout=1000)
                            from automation.browser.browser_engine import BrowserEngine
                            await BrowserEngine()._animate_action(page, el, "click")
                            await el.click(timeout=2000)"""
        ),
        (
            """                    try:
                        pos = await frame.evaluate(_js_broad, clean_text)
                        if pos and pos.get("x") is not None:
                            await page.mouse.click(pos["x"], pos["y"])""",
            """                    try:
                        pos = await frame.evaluate(_js_broad, clean_text)
                        if pos and pos.get("x") is not None:
                            from automation.browser.browser_engine import BrowserEngine
                            await BrowserEngine()._animate_action(page, {"x": pos["x"], "y": pos["y"]}, "click")
                            await page.mouse.click(pos["x"], pos["y"])"""
        ),
        (
            """                            el = loc.nth(i)
                            if await el.is_visible():
                                await el.click(timeout=1500)
                                logger.info(f"[Cancel] Closed overlay via selector: {sel}")
                                return "Closed the popup."
                    except Exception as e:
                        logger.error(f"[{__name__}] {type(e).__name__}: {e}")
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
                                await btn.click(timeout=1500)""",
            """                            el = loc.nth(i)
                            if await el.is_visible():
                                from automation.browser.browser_engine import BrowserEngine
                                await BrowserEngine()._animate_action(page, el, "click")
                                await el.click(timeout=1500)
                                logger.info(f"[Cancel] Closed overlay via selector: {sel}")
                                return "Closed the popup."
                    except Exception as e:
                        logger.error(f"[{__name__}] {type(e).__name__}: {e}")
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
                                from automation.browser.browser_engine import BrowserEngine
                                await BrowserEngine()._animate_action(page, btn, "click")
                                await btn.click(timeout=1500)"""
        )
    ]

    for target, replacement in replacements:
        if target in content:
            content = content.replace(target, replacement)
            print(f"Replaced target in {path}")
        else:
            print(f"Warning: target NOT found in {path}!")

    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

def modify_browser_engine():
    path = "automation/browser/browser_engine.py"
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    replacements = [
        (
            """            try:
                search_box = page.locator('textarea[name="q"], input[name="q"]').first
                await search_box.wait_for(state="visible", timeout=5000)
                await search_box.click()""",
            """            try:
                search_box = page.locator('textarea[name="q"], input[name="q"]').first
                await search_box.wait_for(state="visible", timeout=5000)
                await self._animate_action(page, search_box, "click")
                await search_box.click()"""
        ),
        (
            """            try:
                search_box = page.locator('input#search').first
                await search_box.wait_for(state="visible", timeout=5000)
                await search_box.click()""",
            """            try:
                search_box = page.locator('input#search').first
                await search_box.wait_for(state="visible", timeout=5000)
                await self._animate_action(page, search_box, "click")
                await search_box.click()"""
        ),
        (
            """                if 0 <= index < len(elements):
                    text = await elements[index].inner_text()
                    await elements[index].click()
                    return f"Clicked Google result: {text}\"""",
            """                if 0 <= index < len(elements):
                    text = await elements[index].inner_text()
                    await self._animate_action(page, elements[index], "click")
                    await elements[index].click()
                    return f"Clicked Google result: {text}\""""
        ),
        (
            """                if 0 <= index < len(elements):
                    text = await elements[index].inner_text()
                    await elements[index].click()
                    return f"Clicked YouTube result: {text}\"""",
            """                if 0 <= index < len(elements):
                    text = await elements[index].inner_text()
                    await self._animate_action(page, elements[index], "click")
                    await elements[index].click()
                    return f"Clicked YouTube result: {text}\""""
        ),
        (
            """                    if len(visible) > index:
                        await visible[index].click()
                        return f"Clicked search result {index + 1} via '{loc}'." """,
            """                    if len(visible) > index:
                        await self._animate_action(page, visible[index], "click")
                        await visible[index].click()
                        return f"Clicked search result {index + 1} via '{loc}'." """
        )
    ]

    for target, replacement in replacements:
        # Standardize newlines for match robustness
        target_norm = target.replace("\r\n", "\n")
        replacement_norm = replacement.replace("\r\n", "\n")
        content_norm = content.replace("\r\n", "\n")
        if target_norm in content_norm:
            content_norm = content_norm.replace(target_norm, replacement_norm)
            content = content_norm
            print(f"Replaced target in {path}")
        else:
            print(f"Warning: target NOT found in {path}!")

    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

if __name__ == "__main__":
    modify_intent_registry()
    modify_browser_engine()
