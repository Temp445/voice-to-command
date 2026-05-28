"""
ACE Voice Controller — Browser Controller (Playwright)
Async browser automation: navigate, search, fill forms, multi-tab.
"""

import asyncio
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from loguru import logger
from app.config import settings
from app.core.exceptions import BrowserAutomationError
from playwright_stealth import Stealth


class BrowserController:
    """Singleton Playwright browser controller."""

    _playwright = None
    _browser: Browser | None = None
    _context: BrowserContext | None = None
    _page: Page | None = None

    async def _ensure_browser(self) -> Page:
        if not BrowserController._browser or not BrowserController._browser.is_connected():
            if not BrowserController._playwright:
                BrowserController._playwright = await async_playwright().start()
            
            browser_type = getattr(BrowserController._playwright, settings.browser_type, BrowserController._playwright.chromium)
            BrowserController._browser = await browser_type.launch(headless=False)
            BrowserController._context = await BrowserController._browser.new_context()
            BrowserController._page = await BrowserController._context.new_page()
            await Stealth().apply_stealth_async(BrowserController._page)
            logger.info(f"Browser launched: {settings.browser_type} (Stealth Mode Enabled)")

        if not BrowserController._page or BrowserController._page.is_closed():
            try:
                BrowserController._page = await BrowserController._context.new_page()
            except Exception:
                BrowserController._context = await BrowserController._browser.new_context()
                BrowserController._page = await BrowserController._context.new_page()
                await Stealth().apply_stealth_async(BrowserController._page)

        return BrowserController._page

    async def navigate(self, url: str) -> str:
        """Navigate to a URL."""
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"
        page = await self._ensure_browser()
        await page.goto(url, wait_until="domcontentloaded", timeout=20000)
        logger.info(f"Navigated to: {url}")
        return f"Opened {url}"

    async def search_google(self, query: str) -> str:
        page = await self._ensure_browser()
        search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
        await page.goto(search_url, wait_until="domcontentloaded")
        return f"Searched Google for: {query}"

    async def search_youtube(self, query: str) -> str:
        page = await self._ensure_browser()
        search_url = f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}"
        await page.goto(search_url, wait_until="domcontentloaded")
        return f"Searched YouTube for: {query}"

    async def fill_form(self, selector: str, value: str) -> None:
        page = await self._ensure_browser()
        await page.fill(selector, value)

    async def click(self, selector: str) -> None:
        page = await self._ensure_browser()
        await page.click(selector)

    async def new_tab(self, url: str | None = None) -> str:
        if not BrowserController._context:
            await self._ensure_browser()
        BrowserController._page = await BrowserController._context.new_page()
        await Stealth().apply_stealth_async(BrowserController._page)
        if url:
            await self.navigate(url)
        return "New tab opened"

    async def close(self) -> None:
        if BrowserController._browser:
            await BrowserController._browser.close()
            BrowserController._browser = None
            BrowserController._context = None
            BrowserController._page = None
        if BrowserController._playwright:
            await BrowserController._playwright.stop()
            BrowserController._playwright = None
