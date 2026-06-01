"""
ACE Voice Controller — Voice Pipeline Orchestrator
State machine: IDLE → LISTENING → PROCESSING → SPEAKING → IDLE
"""

import asyncio
import io
import threading
import time
from enum import Enum
from typing import Callable
import pygame
import numpy as np

from loguru import logger
from voice.wake_word.detector import WakeWordDetector
from voice.stt.audio_capture import AudioCapture
from voice.stt.transcriber import Transcriber
from voice.tts.provider_factory import get_tts_provider
from app.config import settings


class PipelineState(str, Enum):
    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"
    ERROR = "error"


class VoicePipeline:
    """
    Full voice processing pipeline:
    Wake Word → Audio Capture → STT → Command Execute → TTS Response

    Emits state changes via `on_state_change` callback for real-time UI updates.
    """

    def __init__(
        self,
        on_state_change: Callable[[PipelineState], None] | None = None,
        on_transcript: Callable[[str, bool], None] | None = None,
        on_command_result: Callable[[dict], None] | None = None,
    ):
        self.on_state_change = on_state_change
        self.on_transcript = on_transcript
        self.on_command_result = on_command_result

        self._state = PipelineState.IDLE
        self._audio_capture = AudioCapture()
        self._transcriber = Transcriber()
        self._wake_word = WakeWordDetector(
            wake_word=settings.wake_word,
            on_detected=self._on_wake_word,
        )
        self._running = False
        self._loop: asyncio.AbstractEventLoop | None = None

        # Init pygame mixer for audio playback
        pygame.mixer.init(frequency=22050, size=-16, channels=1, buffer=512)

    # ─── Lifecycle ───────────────────────────────────────────────────────────

    def start(self) -> None:
        """Start the pipeline in a background thread."""
        self._running = True
        self._loop = asyncio.new_event_loop()
        
        # Start the event loop in a dedicated background thread so async tasks execute
        self._loop_thread = threading.Thread(
            target=self._loop.run_forever,
            daemon=True,
            name="VoicePipelineLoop"
        )
        self._loop_thread.start()
        
        # Only start wake word detector initially (mutually exclusive mic access)
        self._wake_word.start()
        logger.info("🎙️ Voice pipeline started")

    def stop(self) -> None:
        self._running = False
        self._audio_capture.stop()
        self._wake_word.stop()
        if self._loop:
            self._loop.call_soon_threadsafe(self._loop.stop)
        if hasattr(self, "_loop_thread") and self._loop_thread:
            self._loop_thread.join(timeout=3)
        logger.info("🎙️ Voice pipeline stopped")

    # ─── State ───────────────────────────────────────────────────────────────

    def _set_state(self, state: PipelineState) -> None:
        self._state = state
        logger.debug(f"Pipeline state → {state.value}")
        if self.on_state_change:
            self.on_state_change(state)

    @property
    def state(self) -> PipelineState:
        return self._state

    # ─── Wake Word Callback ──────────────────────────────────────────────────

    def _on_wake_word(self) -> None:
        """Called from wake word detector thread."""
        if self._state != PipelineState.IDLE:
            return  # Already processing

        if self._loop:
            asyncio.run_coroutine_threadsafe(self._listen_and_process(), self._loop)
        else:
            asyncio.run(self._listen_and_process())

    def trigger_listening(self) -> None:
        """Manually trigger listening (from UI button or hotkey)."""
        self._on_wake_word()

    def deactivate(self) -> None:
        """Force the pipeline back to IDLE state."""
        self._audio_capture.stop()
        self._set_state(PipelineState.IDLE)
        self._wake_word.start()

    # ─── Processing Pipeline ─────────────────────────────────────────────────

    async def _listen_and_process(self) -> None:
        """Full pipeline run: listen → transcribe → command → speak."""
        try:
            # 1. Stop wake word to free the mic
            self._wake_word.stop()

            # Greet the user
            await self._speak("How can I help you?")

            # 2. Listen
            self._set_state(PipelineState.LISTENING)
            self._audio_capture.start()
            self._audio_capture.clear()
            audio_bytes = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self._audio_capture.get_speech_segment(timeout=8.0),
            )

            # 3. Stop audio capture to free the mic
            self._audio_capture.stop()

            if not audio_bytes:
                logger.debug("No speech detected — returning to idle")
                self._set_state(PipelineState.IDLE)
                self._wake_word.start()
                return

            # 4. Transcribe
            self._set_state(PipelineState.PROCESSING)
            text = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self._transcriber.transcribe(audio_bytes),
            )

            if not text.strip():
                self._set_state(PipelineState.IDLE)
                self._wake_word.start()
                return

            logger.info(f"📝 Transcript: '{text}'")
            if self.on_transcript:
                self.on_transcript(text, True)

            # 5. Execute command
            from app.services.command_service import command_service
            result = await command_service.parse_and_execute(text)
            if self.on_command_result:
                self.on_command_result(result)

            # 6. Speak response
            response_text = result.get("result", "Done")
            await self._speak(response_text)

        except Exception as e:
            logger.error(f"Pipeline error: {e}")
            self._audio_capture.stop()
            self._set_state(PipelineState.ERROR)
            await asyncio.sleep(1)
            self._set_state(PipelineState.IDLE)
            self._wake_word.start()
        else:
            self._set_state(PipelineState.IDLE)
            self._wake_word.start()

    async def _speak(self, text: str) -> None:
        """Synthesize and play TTS response."""
        self._set_state(PipelineState.SPEAKING)
        try:
            provider = await get_tts_provider()
            audio_bytes = await provider.synthesize(text)

            # Play using pygame
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self._play_audio(audio_bytes),
            )
        except Exception as e:
            logger.warning(f"TTS playback failed: {e}")

    def _play_audio(self, audio_bytes: bytes) -> None:
        sound = pygame.mixer.Sound(io.BytesIO(audio_bytes))
        sound.play()
        while pygame.mixer.get_busy():
            time.sleep(0.05)
