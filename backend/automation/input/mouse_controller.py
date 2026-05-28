"""
ACE Voice Controller — Mouse Controller (PyAutoGUI)
Mouse automation: clicking, scrolling, and cursor movement.
"""

import pyautogui
from loguru import logger

# Set pyautogui safety settings
pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0.1

class MouseController:
    """Control the mouse cursor using PyAutoGUI."""

    def click(self) -> None:
        """Left click at the current mouse position."""
        pyautogui.click()
        logger.debug("Mouse left-clicked.")

    def double_click(self) -> None:
        """Double left click at the current mouse position."""
        pyautogui.doubleClick()
        logger.debug("Mouse double-clicked.")

    def right_click(self) -> None:
        """Right click at the current mouse position."""
        pyautogui.rightClick()
        logger.debug("Mouse right-clicked.")

    def scroll_up(self, amount: int = 500) -> None:
        """Scroll the screen up."""
        # Note: on Windows, positive scroll values scroll up.
        pyautogui.scroll(amount)
        logger.debug(f"Scrolled up by {amount}.")

    def scroll_down(self, amount: int = 500) -> None:
        """Scroll the screen down."""
        # Note: on Windows, negative scroll values scroll down.
        pyautogui.scroll(-amount)
        logger.debug(f"Scrolled down by {amount}.")
