from loguru import logger
from playwright.async_api import Page
from app.services.llm.llm_service import llm_service
from app.config import settings

class StateManagerMixin:
    def __init__(self):
        self._highlighted_elements = []

    async def clear_highlights(self):
        """
        Clears all highlight overlays from the page DOM.
        """
        try:
            await self.page.evaluate("""
                () => {
                    const marks = document.querySelectorAll('.ace-highlight-overlay');
                    marks.forEach(m => m.remove());
                }
            """)
        except Exception as e:
            logger.debug(f"Failed to clear highlights: {e}")
