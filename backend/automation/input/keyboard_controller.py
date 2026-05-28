"""
ACE Voice Controller — Keyboard Controller (pynput)
Keyboard automation: hotkeys, shortcuts, typing, media keys.
"""

import time
from pynput.keyboard import Key, Controller, HotKey
from loguru import logger


class KeyboardController:
    """Type text, press shortcuts, and send system keys."""

    def __init__(self):
        self._kb = Controller()

    def type_text(self, text: str) -> None:
        self._kb.type(text)
        logger.debug(f"Typed: {text[:30]}")

    def press(self, *keys) -> None:
        """Press a combination of keys. E.g. press(Key.ctrl, 'c')"""
        for k in keys[:-1]:
            self._kb.press(k)
        self._kb.press(keys[-1])
        self._kb.release(keys[-1])
        for k in reversed(keys[:-1]):
            self._kb.release(k)

    def copy(self) -> None:
        self.press(Key.ctrl, 'c')

    def paste(self) -> None:
        self.press(Key.ctrl, 'v')

    def cut(self) -> None:
        self.press(Key.ctrl, 'x')

    def undo(self) -> None:
        self.press(Key.ctrl, 'z')

    def redo(self) -> None:
        self.press(Key.ctrl, Key.shift, 'z')

    def select_all(self) -> None:
        self.press(Key.ctrl, 'a')

    def save(self) -> None:
        self.press(Key.ctrl, 's')

    def volume_up(self) -> None:
        self._kb.press(Key.media_volume_up)
        self._kb.release(Key.media_volume_up)

    def volume_down(self) -> None:
        self._kb.press(Key.media_volume_down)
        self._kb.release(Key.media_volume_down)

    def mute(self) -> None:
        self._kb.press(Key.media_volume_mute)
        self._kb.release(Key.media_volume_mute)

    def media_play_pause(self) -> None:
        self._kb.press(Key.media_play_pause)
        self._kb.release(Key.media_play_pause)

    def press_enter(self) -> None:
        self._kb.press(Key.enter)
        self._kb.release(Key.enter)

    def press_escape(self) -> None:
        self._kb.press(Key.esc)
        self._kb.release(Key.esc)

    def switch_window(self) -> None:
        self.press(Key.alt, Key.tab)

    def show_desktop(self) -> None:
        self.press(Key.cmd, 'd')
