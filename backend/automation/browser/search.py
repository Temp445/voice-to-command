"""Browser search helpers."""

from automation.browser.browser_controller import BrowserController


class BrowserSearch:
    def __init__(self):
        self._bc = BrowserController()

    async def google(self, query: str) -> str:
        return await self._bc.search_google(query)

    async def youtube(self, query: str) -> str:
        return await self._bc.search_youtube(query)
