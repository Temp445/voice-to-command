"""
Smart Logout Handler
====================
Detects and executes logout on any website using a 5-layer progressive strategy,
built entirely on the existing Playwright stack — zero new dependencies.

Layers:
  1. Direct DOM keyword scan  — instant, no LLM
  2. Profile/account menu detection + rescan — handles hidden menus
  3. DOMAgent LLM fallback   — handles unusual layouts
  4. Network request interception — confirms logout via API call detection
  5. Logout verification      — checks if login page/button appears after logout
"""

import asyncio
from loguru import logger
from playwright.async_api import Page

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LOGOUT_KEYWORDS = [
    "log out", "logout", "sign out", "signout",
    "sign off", "log off", "exit account",
    # Multilingual common variants
    "déconnexion", "salir", "cerrar sesión", "abmelden",
]

# CSS selectors for profile / account menu triggers, ordered by reliability.
# These are checked across the entire page but weighted toward top-right position.
PROFILE_SELECTORS = [
    "[aria-label*='account' i]",
    "[aria-label*='profile' i]",
    "[aria-label*='user' i]",
    "[aria-label*='avatar' i]",
    "[aria-label*='settings' i]",
    "[aria-label*='my account' i]",
    "[data-testid*='user-menu' i]",
    "[data-testid*='avatar' i]",
    "[data-testid*='profile' i]",
    "[class*='avatar' i]",
    "[class*='user-menu' i]",
    "[class*='profile-pic' i]",
    "[class*='profile-icon' i]",
    "img[alt*='avatar' i]",
    "img[alt*='profile' i]",
    "img[alt*='user' i]",
    "button:has(img)",           # button wrapping a user avatar image
    "[role='button']:has(img)",
]

# Keywords to confirm a post-logout dialog
CONFIRM_KEYWORDS = [
    "confirm", "yes", "continue", "log out", "logout",
    "sign out", "signout", "ok", "proceed",
]

# Signals that the page is now a login / auth page
LOGIN_SIGNAL_KEYWORDS = [
    "sign in", "log in", "login", "sign up", "create account",
    "get started", "welcome back", "enter your password",
    "forgot password", "remember me",
]

# URL fragments that indicate a login / auth page
LOGIN_URL_PATTERNS = [
    "/login", "/signin", "/auth", "/sign-in",
    "/log-in", "/logout", "/accounts/login",
    "accounts.google.com", "login.microsoftonline",
]


class LogoutHandler:
    """
    Progressive 5-layer logout detector for any website.

    Usage:
        handler = LogoutHandler(page)
        result  = await handler.smart_logout()
    """

    def __init__(self, page: Page):
        self.page = page
        self._logout_detected_via_network = False

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def smart_logout(self) -> str:
        """
        Attempts logout using 5 progressive layers.
        Returns a human-readable confirmation string.
        """
        # Attach a lightweight network listener for the whole duration.
        self._attach_network_listener()

        # --- Layer 1: Direct keyword scan on the visible page ---
        logger.info("[Logout] Layer 1: Direct DOM keyword scan")
        result = await self._scan_and_click_logout()
        if result:
            return await self._post_click_flow(result)

        # --- Layer 2: Open profile/account menu and rescan ---
        logger.info("[Logout] Layer 2: Profile menu detection + rescan")
        menu_opened = await self._open_profile_menu()
        if menu_opened:
            await asyncio.sleep(0.6)   # Wait for menu animation
            result = await self._scan_and_click_logout()
            if result:
                return await self._post_click_flow(result)

        # --- Layer 3: DOMAgent LLM fallback ---
        logger.info("[Logout] Layer 3: DOMAgent LLM fallback")
        try:
            from automation.browser.dom_agent import DOMAgent
            agent = DOMAgent(self.page)
            dom_result = await agent.execute_intent("click the logout or sign out button")
            # If DOMAgent confirmed it clicked something (not a failure message)
            if dom_result and "couldn't find" not in dom_result.lower() and "failed" not in dom_result.lower():
                return await self._post_click_flow(dom_result)
        except Exception as e:
            logger.warning(f"[Logout] DOMAgent fallback error: {e}")

        # --- Network interception check (passive, already attached) ---
        # If any layer caused a logout network call, we trust that.
        if self._logout_detected_via_network:
            return await self._verify_logout("Logout request detected via network.")

        logger.warning("[Logout] All layers exhausted. Could not find logout button.")
        return (
            "Couldn't find the logout button on this page. "
            "Try saying 'open profile menu' first, or navigate to the account settings."
        )

    # ------------------------------------------------------------------
    # Layer 1 — Direct DOM keyword scan
    # ------------------------------------------------------------------

    async def _scan_and_click_logout(self) -> str | None:
        """
        Scans visible DOM for logout-related text and clicks the first match.
        Returns a short description string on success, None on failure.
        """
        for keyword in LOGOUT_KEYWORDS:
            # Try role-based locators first (most reliable)
            for role in ("link", "button", "menuitem"):
                try:
                    import re
                    locator = self.page.get_by_role(
                        role,
                        name=re.compile(re.escape(keyword), re.IGNORECASE)
                    )
                    count = await locator.count()
                    if count > 0:
                        # Prefer visible elements
                        for i in range(count):
                            el = locator.nth(i)
                            if await el.is_visible():
                                await el.click(timeout=3000)
                                logger.info(f"[Logout] Layer 1 clicked: role={role}, text='{keyword}'")
                                return f"Clicked '{keyword}' ({role})"
                except Exception as e:
                    logger.error(f"[{__name__}] {type(e).__name__}: {e}")
                    pass

            # Fallback: plain text locator
            try:
                import re
                locator = self.page.get_by_text(
                    re.compile(re.escape(keyword), re.IGNORECASE)
                ).first
                if await locator.is_visible():
                    await locator.click(timeout=3000)
                    logger.info(f"[Logout] Layer 1 clicked (text): '{keyword}'")
                    return f"Clicked '{keyword}'"
            except Exception as e:
                logger.error(f"[{__name__}] {type(e).__name__}: {e}")
                pass

        return None

    # ------------------------------------------------------------------
    # Layer 2 — Open profile / account menu
    # ------------------------------------------------------------------

    async def _open_profile_menu(self) -> bool:
        """
        Finds and clicks the most likely profile/account menu icon.
        Prefers elements in the top-right quadrant of the viewport.
        Returns True if a menu icon was found and clicked.
        """
        # Get viewport size for top-right bias calculation
        viewport = self.page.viewport_size or {"width": 1280, "height": 720}
        vw = viewport.get("width", 1280)
        vh = viewport.get("height", 720)

        # Threshold: top 15% height, rightmost 40% width
        top_right_x_min = vw * 0.60
        top_right_y_max = vh * 0.15

        best_candidate = None  # (score, element, selector)

        for selector in PROFILE_SELECTORS:
            try:
                locators = self.page.locator(selector)
                count = await locators.count()
                for i in range(min(count, 5)):  # Check up to 5 matches per selector
                    el = locators.nth(i)
                    if not await el.is_visible():
                        continue

                    box = await el.bounding_box()
                    if not box:
                        continue

                    # Calculate score: top-right position wins
                    x_score = 1 if box["x"] >= top_right_x_min else 0
                    y_score = 1 if box["y"] <= top_right_y_max else 0
                    position_score = x_score + y_score

                    if best_candidate is None or position_score > best_candidate[0]:
                        best_candidate = (position_score, el, selector, box)
            except Exception as e:
                logger.error(f"[{__name__}] {type(e).__name__}: {e}")
                pass

        if best_candidate:
            score, el, selector, box = best_candidate
            try:
                await el.click(timeout=3000)
                logger.info(
                    f"[Logout] Layer 2 clicked profile menu: selector='{selector}' "
                    f"pos=({box['x']:.0f},{box['y']:.0f}) score={score}"
                )
                return True
            except Exception as e:
                logger.warning(f"[Logout] Layer 2 profile click failed: {e}")

        return False

    # ------------------------------------------------------------------
    # Post-click: Confirmation dialog + Verification
    # ------------------------------------------------------------------

    async def _post_click_flow(self, click_result: str) -> str:
        """
        After a logout button click:
          1. Handle confirmation dialogs (if any)
          2. Verify logout success
        """
        # Wait briefly for any dialog/redirect
        await asyncio.sleep(0.8)

        # Handle confirmation dialogs
        confirmed = await self._handle_confirmation_dialog()
        if confirmed:
            await asyncio.sleep(0.5)

        # Verify logout
        return await self._verify_logout(click_result)

    async def _handle_confirmation_dialog(self) -> bool:
        """
        Looks for and auto-confirms a logout confirmation modal/dialog.
        Returns True if a confirmation button was clicked.
        """
        import re
        for keyword in CONFIRM_KEYWORDS:
            for role in ("button", "link"):
                try:
                    locator = self.page.get_by_role(
                        role,
                        name=re.compile(re.escape(keyword), re.IGNORECASE)
                    )
                    count = await locator.count()
                    for i in range(count):
                        el = locator.nth(i)
                        if await el.is_visible():
                            await el.click(timeout=2000)
                            logger.info(f"[Logout] Confirmed dialog: clicked '{keyword}'")
                            return True
                except Exception as e:
                    logger.error(f"[{__name__}] {type(e).__name__}: {e}")
                    pass
        return False

    async def _verify_logout(self, click_result: str) -> str:
        """
        Checks if the user is now on a login/auth page.
        Returns a human-readable confirmation.
        """
        try:
            await self.page.wait_for_load_state("domcontentloaded", timeout=5000)
        except Exception as e:
            logger.error(f"[{__name__}] {type(e).__name__}: {e}")
            pass

        current_url = self.page.url.lower()
        url_is_login = any(pattern in current_url for pattern in LOGIN_URL_PATTERNS)

        # Check page text for login signals
        page_text_is_login = False
        try:
            body_text = (await self.page.inner_text("body", timeout=3000)).lower()
            page_text_is_login = any(kw in body_text for kw in LOGIN_SIGNAL_KEYWORDS)
        except Exception as e:
            logger.error(f"[{__name__}] {type(e).__name__}: {e}")
            pass

        if url_is_login or page_text_is_login or self._logout_detected_via_network:
            logger.info(
                f"[Logout] Verified logged out. URL login={url_is_login}, "
                f"text login={page_text_is_login}, network={self._logout_detected_via_network}"
            )
            return "Signed you out successfully."
        else:
            # Logout may have succeeded but didn't redirect (e.g., SPA that shows login inline)
            logger.info("[Logout] Could not definitively verify logout via URL/text, but click was attempted.")
            return "Attempted to sign you out. Please verify you are logged out."

    # ------------------------------------------------------------------
    # Layer 4 — Network interception (passive listener)
    # ------------------------------------------------------------------

    def _attach_network_listener(self):
        """
        Attaches a passive Playwright request listener to detect logout API calls.
        Sets `self._logout_detected_via_network = True` if a logout endpoint is hit.
        """
        LOGOUT_URL_HINTS = [
            "logout", "signout", "sign-out", "log-out",
            "auth/logout", "session/destroy", "accounts/logout",
            "api/logout", "api/signout",
        ]

        def _on_request(request):
            url = request.url.lower()
            if any(hint in url for hint in LOGOUT_URL_HINTS):
                logger.info(f"[Logout] Network logout request detected: {request.url}")
                self._logout_detected_via_network = True

        try:
            self.page.on("request", _on_request)
        except Exception as e:
            logger.warning(f"[Logout] Could not attach network listener: {e}")
