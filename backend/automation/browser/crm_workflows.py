import asyncio
from loguru import logger
from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError


class CRMMacros:
    """Macros for common workflows on the Acesoftcloud CRM.

    MULTI-TAB DESIGN
    ────────────────
    Every public method that needs to act on a specific site now accepts an
    optional `page` kwarg.  Callers that already know the target tab (e.g.
    VoiceBrowserCommands.execute()) pass it in directly — no second
    get_active_page() call, no race condition, no wrong-tab redirection.

    Helper: _crm_page()
    ───────────────────
    Scans all open Playwright pages and returns the one whose URL matches the
    configured CRM host.  Falls back to ensure_browser() only when no CRM tab
    exists yet (first open).  This is the single source-of-truth used by
    login() and navigate_to_module() so they ALWAYS land on the CRM tab, even
    when Payroll or any other site is currently in the foreground.
    """

    def __init__(self, engine):
        self.engine = engine
        from app.config import settings
        self.base_url = settings.crm_url if settings.crm_url.endswith('/') else settings.crm_url + '/'
        # Derive host for tab-matching (e.g. "crm.acesoftcloud.in")
        self._crm_host = (
            self.base_url
            .replace("https://", "")
            .replace("http://", "")
            .split("/")[0]
            .lower()
        )

    # ──────────────────────────────────────────────────────────────────────────
    # INTERNAL HELPERS
    # ──────────────────────────────────────────────────────────────────────────

    async def _crm_page(self) -> Page:
        """Return the Playwright Page for the CRM tab.

        Search order:
          1. Any open tab whose URL contains the CRM host  →  return it.
          2. No CRM tab exists yet                         →  ensure_browser()
             so the caller can navigate there fresh.

        This means login() and navigate_to_module() ALWAYS target the CRM tab
        regardless of which tab the user is currently looking at.
        """
        ctx = self.engine._context
        if ctx and not getattr(ctx, "is_closed", lambda: True)():
            for p in ctx.pages:
                if (
                    not p.is_closed()
                    and self._crm_host in p.url.lower()
                ):
                    logger.debug(f"[CRMMacros] Found CRM tab: {p.url}")
                    return p
        # No existing CRM tab — return a generic page; caller will navigate
        logger.debug("[CRMMacros] No CRM tab open — using ensure_browser()")
        return await self.engine.ensure_browser()

    def _host_matches(self, url: str) -> bool:
        """True when *url* belongs to the configured CRM."""
        return self._crm_host in url.lower()

    # ──────────────────────────────────────────────────────────────────────────
    # PUBLIC API
    # ──────────────────────────────────────────────────────────────────────────

    async def open_crm(
        self,
        transcript: str = None,
        target_url: str = None,
        dynamic_routes: dict = None,
        page: Page = None,
    ):
        """Navigate to the CRM homepage (or a specific site URL if provided)."""
        dest = target_url if target_url else self.base_url
        if dest and not dest.endswith('/'):
            dest += '/'
        t_lower = transcript.lower() if transcript else ""

        new_tab = "new tab" in t_lower or "another tab" in t_lower

        # Dynamic route matching
        if dynamic_routes:
            for key, route_path in dynamic_routes.items():
                if key.lower() in t_lower:
                    route = dest + route_path.lstrip('/')
                    logger.info(f"Dynamically redirecting to configured route: {route}")
                    await self.engine.navigate(route, new_tab=new_tab)
                    return f"Opened website and navigated to {route_path}."

        # Login-specific shortcut
        if "login" in t_lower or "log in" in t_lower or "sign in" in t_lower:
            if not target_url or dest.strip('/').lower() == self.base_url.strip('/').lower():
                await self.engine.navigate(dest, new_tab=new_tab)
                await self.login()
                return "Opened CRM and logged in."
            else:
                try:
                    await self.engine.navigate(dest, new_tab=new_tab)
                    from automation.browser.dom_agent import DOMAgent
                    pg = await self.engine.get_active_page()
                    agent = DOMAgent(pg)
                    await agent.execute_intent("click the login, sign in, or Site Admin link")
                    return "Opened website and initiated login."
                except AttributeError:
                    logger.warning("DOMAgent execute_intent not implemented.")
                    route = dest + "login"
                    await self.engine.navigate(route, new_tab=new_tab)
                    return "Opened website and navigated to login."
                except Exception as e:
                    logger.error(f"DOMAgent login failed: {e}")
                    return "Opened website, but failed to auto-login."

        await self.engine.navigate(dest, new_tab=new_tab)

        words = transcript.strip().split() if transcript else ["opened"]
        verb = words[0].lower()
        if verb in ['open', 'launch', 'start', 'show']:
            past = verb + 'ed' if verb not in ['show', 'launch'] else ('shown' if verb == 'show' else 'launched')
            return f"{past.capitalize()} {' '.join(words[1:]) if len(words) > 1 else 'CRM'}"
        return f"Opened {transcript or 'CRM'}"

    async def login(self, username: str = None, password: str = None, page: Page = None):
        """Fill the CRM login form on the CRM tab.

        KEY FIX: We always act on the CRM tab (_crm_page), never on whatever
        tab happens to be in the foreground.  If the user has Payroll open in
        the foreground and says "log in to CRM", this method will still find
        the CRM tab and fill its form.
        """
        logger.info("Logging into CRM...")

        # Use the provided page, find the CRM tab, or open a new one.
        if page is None or not self._host_matches(page.url):
            page = await self._crm_page()

        # If we landed on a non-CRM page (first run), navigate to /login
        if not self._host_matches(page.url):
            try:
                await page.goto(self.base_url + "login", wait_until="commit", timeout=15000)
            except PlaywrightTimeoutError:
                logger.warning("Network timeout navigating to CRM login. Reloading...")
                await page.reload(timeout=15000)
        else:
            # We're already on the CRM — navigate to /login if not already there.
            # Check for the landing page: try clicking the "Sign In" nav link first
            # (avoids a full page navigation if it's just a SPA route push).
            current = page.url.lower()
            if "/login" not in current and "/dashboard" not in current:
                # Likely the marketing landing page — try the Sign In nav link first
                try:
                    _signin_link = page.locator(
                        "a:has-text('Sign In'), a:has-text('Sign in'), "
                        "a:has-text('Login'), a:has-text('Log in'), "
                        "button:has-text('Sign In'), button:has-text('Sign in')"
                    ).first
                    if await _signin_link.count() > 0 and await _signin_link.is_visible():
                        await _signin_link.click(timeout=3000)
                        await page.wait_for_load_state("domcontentloaded", timeout=8000)
                        logger.info(f"[CRMMacros] Clicked Sign In link, now at {page.url}")
                    else:
                        await page.goto(self.base_url + "login", wait_until="commit", timeout=15000)
                except Exception as _nav_err:
                    logger.warning(f"Sign In link click failed: {_nav_err}. Navigating to /login directly.")
                    try:
                        await page.goto(self.base_url + "login", wait_until="commit", timeout=15000)
                    except PlaywrightTimeoutError:
                        await page.reload(timeout=15000)
            elif "/login" not in current:
                # On dashboard or other app page — go to login
                try:
                    await page.goto(self.base_url + "login", wait_until="commit", timeout=15000)
                except PlaywrightTimeoutError:
                    await page.reload(timeout=15000)

        # Bring the CRM tab to front so the user can see progress
        try:
            await page.bring_to_front()
        except Exception:
            pass
        # Invalidate the active-page cache so subsequent commands see CRM
        self.engine.invalidate_active_page_cache()

        if username:
            try:
                await page.wait_for_selector(
                    "input[name='email'], input[type='email']", timeout=5000
                )
                await page.fill("input[name='email'], input[type='email']", username)
            except PlaywrightTimeoutError:
                logger.warning("Email input not found via selector — falling back to DOMAgent.")
                from automation.browser.dom_agent import DOMAgent
                agent = DOMAgent(page)
                await agent.execute_intent(f"type {username} into the email field")

        if password:
            try:
                await page.wait_for_selector(
                    "input[name='password'], input[type='password']", timeout=5000
                )
                await page.fill("input[name='password'], input[type='password']", password)
                await page.keyboard.press("Enter")
            except PlaywrightTimeoutError:
                logger.warning("Password input not found via selector — falling back to DOMAgent.")
                from automation.browser.dom_agent import DOMAgent
                agent = DOMAgent(page)
                await agent.execute_intent(f"type {password} into the password field and submit")

        try:
            toast = await page.wait_for_selector(
                ".toast-error, .error-message, .alert-danger", timeout=3000
            )
            if toast:
                error_text = await toast.inner_text()
                return f"Login failed: {error_text.strip()}"
        except PlaywrightTimeoutError:
            pass

        return "Executed login flow."

    async def logout(self, page: Page = None):
        """Log out of the CRM using the CRM tab."""
        logger.info("Logging out of CRM...")
        if page is None or not self._host_matches(page.url):
            page = await self._crm_page()
        from automation.browser.logout_handler import LogoutHandler
        handler = LogoutHandler(page)
        return await handler.smart_logout()

    async def navigate_to_module(self, module_name: str, page: Page = None):
        """Navigate to a CRM sidebar module, always on the CRM tab."""
        module_name = module_name.lower().strip()
        logger.info(f"Navigating to CRM module: {module_name}")

        # Always target the CRM tab — never Payroll or any other open site
        if page is None or not self._host_matches(page.url):
            page = await self._crm_page()

        # If the CRM tab is not on the CRM at all, navigate home first
        if not self._host_matches(page.url):
            await page.goto(self.base_url, wait_until="commit", timeout=15000)

        await page.bring_to_front()
        self.engine.invalidate_active_page_cache()

        current_url = page.url.lower()
        is_landing = current_url.strip('/') == self.base_url.strip('/')
        if "login" in current_url or is_landing:
            if (
                await page.locator("text='Sign In'").count() > 0
                or await page.locator("text='Login'").count() > 0
            ):
                return "You are on the login page. Please say 'log in' first."

        try:
            loc = page.get_by_text(module_name.capitalize(), exact=True)
            if await loc.count() > 0:
                await loc.first.click(timeout=3000)
                return f"Navigated to {module_name}."

            hamburger = page.locator(".hamburger-menu, [aria-label='Menu'], button:has(.fa-bars)")
            if await hamburger.count() > 0:
                try:
                    await hamburger.first.click(timeout=3000)
                    await asyncio.sleep(1)
                    loc = page.get_by_text(module_name.capitalize(), exact=True)
                    if await loc.count() > 0:
                        await loc.first.click(timeout=3000)
                        return f"Navigated to {module_name} after expanding sidebar."
                except PlaywrightTimeoutError:
                    logger.warning("Hamburger menu not clickable.")

            logger.warning(f"Hardcoded navigation failed for {module_name}. Falling back to DOMAgent.")
            from automation.browser.dom_agent import DOMAgent
            agent = DOMAgent(page)
            res = await agent.execute_intent(f"click the {module_name} module link in the sidebar")
            if "couldn't find" in res or "Failed" in res:
                return f"Permission Denied or module '{module_name}' not found on this page."

            try:
                await page.wait_for_load_state("networkidle", timeout=2000)
            except Exception as e:
                logger.error(f"[{__name__}] {type(e).__name__}: {e}")

            if module_name.lower() not in page.url.lower():
                return f"Attempted to navigate, but may be blocked. Check login or permissions for {module_name}."

            return f"Navigated to {module_name} via DOMAgent."

        except Exception as e:
            return f"Failed to navigate to module {module_name}: {e}"

    async def create_entity(self, entity_name: str, page: Page = None):
        """Initiate entity creation (lead, quote, etc.) on the CRM tab."""
        entity_name = entity_name.lower().strip()
        logger.info(f"Initiating CRM {entity_name} creation...")
        module_name = entity_name + "s" if not entity_name.endswith('s') else entity_name
        await self.navigate_to_module(module_name, page=page)

        # After navigation, get the CRM tab again (navigate_to_module may have brought it forward)
        if page is None or not self._host_matches(page.url):
            page = await self._crm_page()

        try:
            import re
            pattern = re.compile(f"New {entity_name}|Create {entity_name}", re.IGNORECASE)
            btn = page.get_by_role("button", name=pattern).first
            if await btn.count() == 0:
                btn = page.get_by_text(pattern).first
            await btn.wait_for(state="visible", timeout=10000)

            try:
                await btn.click(timeout=5000)
                return f"Opened New {entity_name.capitalize()} form."
            except Exception as e:
                if "intercepted" in str(e).lower():
                    logger.warning("Click intercepted by overlay. Trying to close it...")
                    from automation.browser.dom_agent import DOMAgent
                    agent = DOMAgent(page)
                    await agent.execute_intent("close the popup or overlay")
                    await asyncio.sleep(0.5)
                    await btn.click(timeout=5000)
                    return f"Opened New {entity_name.capitalize()} form after clearing overlay."
                raise e

        except PlaywrightTimeoutError:
            return f"Navigated to {module_name.capitalize()}, but could not find the New {entity_name.capitalize()} button."
        except Exception as e:
            return f"Failed to initiate {entity_name} creation: {e}"

    async def search_record(self, entity_name: str, query: str, page: Page = None):
        """Navigate to a module and search for a record, always on the CRM tab."""
        logger.info(f"Searching for {query} in {entity_name}...")
        module_name = entity_name + "s" if not entity_name.endswith('s') else entity_name
        await self.navigate_to_module(module_name, page=page)

        if page is None or not self._host_matches(page.url):
            page = await self._crm_page()

        try:
            search_input = page.locator(
                "input[type='search'], input[placeholder*='Search'], input[placeholder*='search']"
            ).first
            await search_input.wait_for(state="visible", timeout=10000)
            await search_input.click()
            await search_input.fill("")
            await page.keyboard.type(query, delay=50)
            await page.keyboard.press("Enter")
            try:
                await page.wait_for_load_state("networkidle", timeout=3000)
            except Exception as e:
                logger.error(f"[{__name__}] {type(e).__name__}: {e}")
            return f"Searched for '{query}' in {module_name.capitalize()}."
        except PlaywrightTimeoutError:
            return f"Could not find a search bar on the {module_name.capitalize()} page."
        except Exception as e:
            return f"Failed to search {entity_name}: {e}"

    async def open_first_record(self, page: Page = None):
        """Click the first record in a data table on the CRM tab."""
        logger.info("Opening first record in data grid...")
        if page is None or not self._host_matches(page.url):
            page = await self._crm_page()

        try:
            first_row_link = page.locator(
                "tbody tr:first-child a, .MuiDataGrid-row:first-child a, [role='row']:nth-child(2) a"
            ).first
            if await first_row_link.count() > 0:
                await first_row_link.click(timeout=5000)
                return "Opened the first record."

            first_row = page.locator(
                "tbody tr:first-child, .MuiDataGrid-row:first-child, [role='row']:nth-child(2)"
            ).first
            if await first_row.count() > 0:
                await first_row.click(timeout=5000)
                return "Clicked the first row."

            return "Could not identify a table or grid with records on this page."
        except PlaywrightTimeoutError:
            return "Timeout while trying to interact with the first record."
        except Exception as e:
            return f"Failed to open first record: {e}"