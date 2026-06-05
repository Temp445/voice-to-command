import asyncio
from loguru import logger
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

class CRMMacros:
    """Macros for common workflows on the Acesoftcloud CRM."""
    
    def __init__(self, engine):
        """
        Expects a BrowserEngine instance from the BrowserController.
        """
        self.engine = engine
        self.base_url = "https://crm.acesoftcloud.in/"

    async def open_crm(self):
        """Navigates to the CRM homepage."""
        logger.info("Opening CRM...")
        return await self.engine.navigate(self.base_url)

    async def login(self, username: str = None, password: str = None):
        """Automates the CRM login flow with robust error handling and fallbacks."""
        logger.info("Logging into CRM...")
        
        page = await self.engine.ensure_browser()
        
        try:
            await page.goto(self.base_url + "login", wait_until="commit", timeout=15000)
        except PlaywrightTimeoutError:
            logger.warning("Network timeout on login page. Retrying with reload...")
            await page.reload(timeout=15000)
            
        if username:
            try:
                # Wait for email input
                await page.wait_for_selector("input[name='email'], input[type='email']", timeout=5000)
                await page.fill("input[name='email'], input[type='email']", username)
            except PlaywrightTimeoutError:
                logger.warning("Email input not found via hardcoded selector. Falling back to DOMAgent.")
                from automation.browser.dom_agent import DOMAgent
                agent = DOMAgent(page)
                await agent.execute_intent(f"type {username} into the email field")
                
        if password:
            try:
                await page.wait_for_selector("input[name='password'], input[type='password']", timeout=5000)
                await page.fill("input[name='password'], input[type='password']", password)
                await page.keyboard.press("Enter")
            except PlaywrightTimeoutError:
                logger.warning("Password input not found via hardcoded selector. Falling back to DOMAgent.")
                from automation.browser.dom_agent import DOMAgent
                agent = DOMAgent(page)
                await agent.execute_intent(f"type {password} into the password field and submit")
                
        # Check for error toast
        try:
            toast = await page.wait_for_selector(".toast-error, .error-message, .alert-danger", timeout=3000)
            if toast:
                error_text = await toast.inner_text()
                return f"Login failed: {error_text.strip()}"
        except PlaywrightTimeoutError:
            pass # No error toast appeared, login likely successful
            
        return "Executed login flow."

    async def navigate_to_module(self, module_name: str):
        """Navigates to a specific module with fallback handling for collapsed sidebars."""
        module_name = module_name.lower().strip()
        logger.info(f"Navigating to CRM module: {module_name}")
        
        page = await self.engine.ensure_browser()
        
        # Check if user is blocked by the login page or landing page
        current_url = page.url.lower()
        is_landing = current_url.strip('/') == self.base_url.strip('/')
        if "login" in current_url or is_landing:
            # Confirm it's the unauthenticated page by looking for typical landing page buttons
            if await page.locator("text='Sign In'").count() > 0 or await page.locator("text='Login'").count() > 0:
                return "You are currently on the landing page. Please say 'log in' or 'sign in' first."
            
        try:
            # Try finding the exact text link first
            loc = page.get_by_text(module_name.capitalize(), exact=True)
            if await loc.count() > 0:
                await loc.first.click(timeout=3000)
                return f"Navigated to {module_name}."
            
            # If standard text fails, try hamburger menu toggle (assume it might be collapsed)
            hamburger = page.locator(".hamburger-menu, [aria-label='Menu'], button:has(.fa-bars)")
            if await hamburger.count() > 0:
                try:
                    logger.info("Sidebar might be collapsed. Toggling hamburger menu.")
                    await hamburger.first.click(timeout=3000)
                    await asyncio.sleep(1) # wait for animation
                    
                    loc = page.get_by_text(module_name.capitalize(), exact=True)
                    if await loc.count() > 0:
                        await loc.first.click(timeout=3000)
                        return f"Navigated to {module_name} after expanding sidebar."
                except PlaywrightTimeoutError:
                    logger.warning("Hamburger menu was found but not clickable (likely hidden).")
                    
            # Ultimate fallback to DOM Agent for semantic matching
            logger.warning(f"Hardcoded navigation failed for {module_name}. Falling back to DOMAgent.")
            from automation.browser.dom_agent import DOMAgent
            agent = DOMAgent(page)
            res = await agent.execute_intent(f"click the {module_name} module link in the sidebar")
            if "couldn't find" in res or "Failed" in res:
                return f"Permission Denied or module '{module_name}' not found on this page."
                
            # Verify if navigation actually succeeded by checking the URL or waiting a moment
            try:
                await page.wait_for_load_state("networkidle", timeout=2000)
            except Exception:
                pass
                
            if module_name.lower() not in page.url.lower():
                return f"Attempted to navigate, but you appear to be blocked. You may need to log in or you do not have permission for {module_name}."
                
            return f"Navigated to {module_name} via DOMAgent."
            
        except Exception as e:
            return f"Failed to navigate to module {module_name}: {e}"

    async def create_entity(self, entity_name: str):
        """Initiates entity creation process (e.g., lead, quote) with overlay handling."""
        entity_name = entity_name.lower().strip()
        logger.info(f"Initiating CRM {entity_name} creation...")
        module_name = entity_name + "s" if not entity_name.endswith('s') else entity_name
        await self.navigate_to_module(module_name)
        
        page = await self.engine.ensure_browser()
        
        try:
            import re
            
            # Wait for either 'New X' or 'Create X' to be visible, ignoring case
            pattern = re.compile(f"New {entity_name}|Create {entity_name}", re.IGNORECASE)
            btn = page.get_by_role("button", name=pattern).first
            
            # If the button doesn't have a button role, fallback to generic text match
            if await btn.count() == 0:
                btn = page.get_by_text(pattern).first
                
            await btn.wait_for(state="visible", timeout=10000)
            
            try:
                await btn.click(timeout=5000)
                return f"Opened New {entity_name.capitalize()} form."
                
            except Exception as e:
                if "intercepted" in str(e).lower():
                    logger.warning("Click intercepted by overlay. Attempting to close overlay using DOMAgent.")
                    from automation.browser.dom_agent import DOMAgent
                    agent = DOMAgent(page)
                    await agent.execute_intent("close the popup or overlay")
                    # Retry
                    await asyncio.sleep(0.5)
                    await btn.click(timeout=5000)
                    return f"Opened New {entity_name.capitalize()} form after clearing overlay."
                raise e
                
        except PlaywrightTimeoutError:
            return f"Navigated to {module_name.capitalize()}, but could not find the New {entity_name.capitalize()} button."
        except Exception as e:
            return f"Failed to initiate {entity_name} creation: {e}"

    async def search_record(self, entity_name: str, query: str):
        """Navigates to the appropriate module and searches for a query."""
        logger.info(f"Searching for {query} in {entity_name}...")
        module_name = entity_name + "s" if not entity_name.endswith('s') else entity_name
        await self.navigate_to_module(module_name)
        
        page = await self.engine.ensure_browser()
        
        try:
            # Common CRM search bar selectors
            search_input = page.locator("input[type='search'], input[placeholder*='Search'], input[placeholder*='search']").first
            await search_input.wait_for(state="visible", timeout=10000)
            await search_input.click()
            await search_input.fill("")
            await page.keyboard.type(query, delay=50)
            await page.keyboard.press("Enter")
            
            # Wait for grid to update
            try:
                await page.wait_for_load_state("networkidle", timeout=3000)
            except Exception:
                pass
            return f"Searched for '{query}' in {module_name.capitalize()}."
        except PlaywrightTimeoutError:
            return f"Could not find a search bar on the {module_name.capitalize()} page."
        except Exception as e:
            return f"Failed to search {entity_name}: {e}"

    async def open_first_record(self):
        """Clicks the first available record in a standard data table."""
        logger.info("Attempting to open the first record in the data grid...")
        page = await self.engine.ensure_browser()
        
        try:
            # Common table row links: looking for an anchor tag in the first row of a tbody
            first_row_link = page.locator("tbody tr:first-child a, .MuiDataGrid-row:first-child a, [role='row']:nth-child(2) a").first
            
            if await first_row_link.count() > 0:
                await first_row_link.click(timeout=5000)
                return "Opened the first record."
                
            # Fallback to just clicking the first row itself if there are no anchor tags
            first_row = page.locator("tbody tr:first-child, .MuiDataGrid-row:first-child, [role='row']:nth-child(2)").first
            if await first_row.count() > 0:
                await first_row.click(timeout=5000)
                return "Clicked the first row."
                
            return "Could not identify a table or grid with records on this page."
            
        except PlaywrightTimeoutError:
            return "Timeout while trying to interact with the first record."
        except Exception as e:
            return f"Failed to open first record: {e}"

