"""
ACE Voice Controller — Background Service
Runs the voice pipeline as a persistent background process.
Integrates system tray via pystray.
"""

import threading
import asyncio
import signal
import sys
from pathlib import Path

import pystray
from PIL import Image, ImageDraw
from loguru import logger

from voice.pipeline import VoicePipeline, PipelineState
from app.config import settings


class BackgroundService:
    """
    Long-running background process that:
    1. Starts the voice pipeline (wake word + STT + TTS)
    2. Shows a system tray icon
    3. Handles shutdown gracefully
    """

    def __init__(self):
        self._pipeline = VoicePipeline(
            on_state_change=self._on_state_change,
            on_transcript=self._on_transcript,
        )
        self._tray: pystray.Icon | None = None
        self._running = False

    def start(self) -> None:
        self._running = True
        self._pipeline.start()
        self._setup_tray()
        logger.info("✅ ACE Background Service started")

        # Block on tray
        if self._tray:
            self._tray.run()

    def stop(self) -> None:
        self._running = False
        self._pipeline.stop()
        if self._tray:
            self._tray.stop()
        logger.info("🛑 ACE Background Service stopped")

    def _on_state_change(self, state: PipelineState) -> None:
        icon_map = {
            PipelineState.IDLE: "⚫",
            PipelineState.LISTENING: "🟢",
            PipelineState.PROCESSING: "🟡",
            PipelineState.SPEAKING: "🔵",
        }
        logger.debug(f"State: {icon_map.get(state, '?')} {state.value}")

    def _on_transcript(self, text: str, is_final: bool) -> None:
        logger.info(f"📝 {'[FINAL]' if is_final else '[PARTIAL]'} {text}")

    def _create_tray_icon(self) -> Image.Image:
        """Create a simple coloured tray icon."""
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.ellipse([8, 8, 56, 56], fill=(99, 102, 241))   # Indigo dot
        return img

    def _setup_tray(self) -> None:
        menu = pystray.Menu(
            pystray.MenuItem("ACE Voice Controller", None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Activate Listening", lambda: self._pipeline.trigger_listening()),
            pystray.MenuItem("Stop Assistant", self._stop_from_tray),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Exit", self._exit),
        )
        self._tray = pystray.Icon(
            "ACE",
            self._create_tray_icon(),
            "ACE Voice Controller",
            menu,
        )

    def _stop_from_tray(self, icon, item) -> None:
        self._pipeline.stop()

    def _exit(self, icon, item) -> None:
        self.stop()
        sys.exit(0)


def main():
    service = BackgroundService()

    def handle_signal(sig, frame):
        service.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    service.start()


if __name__ == "__main__":
    main()
