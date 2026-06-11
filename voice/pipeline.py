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
from voice.stt.provider_factory import get_stt_provider
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
        self._wake_word = WakeWordDetector(
            wake_word=settings.wake_word,
            on_detected=self._on_wake_word,
        )
        self._running = False
        self._loop: asyncio.AbstractEventLoop | None = None
        self._last_spoken_text: str = ""
        self._manually_stopped: bool = False

        # Init pygame mixer for audio playback
        pygame.mixer.init(frequency=22050, size=-16, channels=1, buffer=512)

    # ─── Lifecycle ───────────────────────────────────────────────────────────

    def start(self) -> None:
        """Start the background pipeline loops."""
        if self._running:
            return
        
        # Start the global local microphone broadcast
        from voice.remote_mic import start_local_mic
        start_local_mic()
        
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

        # Async preload TTS engine so the first command is instant
        asyncio.run_coroutine_threadsafe(self._preload_tts(), self._loop)
        # Async preload STT engine so the first transcription doesn't have a 30s cold-start delay
        asyncio.run_coroutine_threadsafe(self._preload_stt(), self._loop)

    async def _preload_tts(self) -> None:
        try:
            logger.info("⚙️ Preloading TTS engine in background...")
            provider = await get_tts_provider()
            # Force model load
            audio_bytes = await provider.synthesize("System initialized and ready.")
            # Optional: play the welcome sound
            # await asyncio.get_event_loop().run_in_executor(None, lambda: self._play_audio(audio_bytes))
            logger.info("✅ TTS engine preloaded successfully.")
        except Exception as e:
            logger.warning(f"Failed to preload TTS engine: {e}")

    async def _preload_stt(self) -> None:
        try:
            logger.info("⚙️ Preloading STT engine in background...")
            stt = get_stt_provider()
            import numpy as np
            # Force model load with 1s of silent audio
            silent_audio = np.zeros(16000, dtype=np.int16).tobytes()
            await asyncio.get_event_loop().run_in_executor(None, stt.transcribe, silent_audio)
            logger.info("✅ STT engine preloaded successfully.")
        except Exception as e:
            logger.warning(f"Failed to preload STT engine: {e}")

    def stop(self) -> None:
        self._running = False
        self._audio_capture.stop()
        self._wake_word.stop()
        if self._loop and self._loop.is_running():
            async def _cancel_and_stop():
                tasks = [t for t in asyncio.all_tasks(self._loop) if t is not asyncio.current_task()]
                for task in tasks:
                    task.cancel()
                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)
                self._loop.stop()
            asyncio.run_coroutine_threadsafe(_cancel_and_stop(), self._loop)
        if hasattr(self, "_loop_thread") and self._loop_thread:
            self._loop_thread.join(timeout=3)
        try:
            pygame.mixer.quit()
        except Exception:
            pass
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

    def stop_listening(self) -> None:
        """Manually stop listening if currently in LISTENING state."""
        if self._state == PipelineState.LISTENING:
            self._manually_stopped = True
            self._audio_capture.stop_recording_early()

    def deactivate(self) -> None:
        """Force the pipeline back to IDLE state."""
        self._audio_capture.stop()
        self._set_state(PipelineState.IDLE)
        self._wake_word.start()

    # ─── Processing Pipeline ─────────────────────────────────────────────────

    def _is_only_wake_word(self, text: str) -> bool:
        """Return True if the transcript is just the wake word with no real command."""
        cleaned = text.lower().strip().rstrip(".,!?")
        wake = self._wake_word.wake_word  # e.g. "alexa"
        variants = {wake, f"hey {wake}", f"ok {wake}", f"okay {wake}", "hey", "ok", "okay"}
        return cleaned in variants

    def _strip_wake_word(self, text: str) -> str:
        """Remove the wake word from the start of the text so the NLU can parse it cleanly."""
        cleaned = text.strip()
        lower_cleaned = cleaned.lower()
        wake = self._wake_word.wake_word.lower()
        
        prefixes_to_strip = [f"hey {wake}", f"ok {wake}", f"okay {wake}", wake]
        
        for prefix in prefixes_to_strip:
            if lower_cleaned.startswith(prefix):
                # Slice off the prefix length from the ORIGINAL string to preserve casing
                stripped = cleaned[len(prefix):].strip()
                # Remove leading punctuation like commas or colons (e.g., "Alexa, open crm")
                return stripped.lstrip(".,!:;").strip()
                
        return cleaned

    async def _capture_and_stream(self, timeout: float = 8.0, max_initial_silence_chunks: int = 20) -> tuple[bytes, str]:
        """Start mic, stream speech segments to STT, and return final (audio_bytes, text)."""
        self._manually_stopped = False
        self._set_state(PipelineState.LISTENING)
        self._audio_capture.start()
        self._audio_capture.clear()

        stt_provider = get_stt_provider()
        loop = asyncio.get_event_loop()

        final_text = ""
        final_audio_bytes = b""

        def _transcribe_stream():
            nonlocal final_text, final_audio_bytes
            for audio_bytes, is_final in self._audio_capture.stream_speech_segment(timeout=timeout, max_initial_silence_chunks=max_initial_silence_chunks):
                final_audio_bytes = audio_bytes
                if is_final and len(audio_bytes) >= 3200:  # MIN_AUDIO_BYTES
                    # Provide instant UI feedback that we are no longer listening
                    self._set_state(PipelineState.PROCESSING)
                    if self.on_transcript:
                        self.on_transcript("Transcribing audio...", False)
                    text = stt_provider.transcribe(audio_bytes)
                    final_text = text

        await loop.run_in_executor(None, _transcribe_stream)
        self._audio_capture.stop()
        return final_audio_bytes, final_text

    async def _listen_and_process(self) -> None:
        """Full pipeline run: stream capture & transcribe → command → speak.
        
        Enterprise Workflow:
        1. Capture initial command.
        2. If only wake word, wait 10s silently.
        3. If still silent, prompt "How can I assist you?".
        4. Enter Active Mode loop until active_mode_timeout expires.
        """
        from app.config import settings
        import time

        MIN_AUDIO_BYTES = 3200  # ~0.1s of audio @ 16kHz 16-bit
        active_timeout = getattr(settings, 'active_mode_timeout', 120)

        try:
            self._wake_word.stop()
            deadline = time.time() + active_timeout

            # 1. First stream pass — capture wake word + command
            audio_bytes, text = await self._capture_and_stream(timeout=8.0, max_initial_silence_chunks=20)

            if self._manually_stopped:
                self._manually_stopped = False
                return

            if not audio_bytes or len(audio_bytes) < MIN_AUDIO_BYTES or not text.strip() or self._is_only_wake_word(text):
                # 2. Wait 10 seconds for user to naturally give command
                logger.info("Only wake word detected. Waiting 10s for command...")
                audio_bytes, text = await self._capture_and_stream(timeout=10.0, max_initial_silence_chunks=100) # 100 chunks = 10s
                
                if self._manually_stopped:
                    self._manually_stopped = False
                    return

                if not audio_bytes or len(audio_bytes) < MIN_AUDIO_BYTES or not text.strip() or self._is_only_wake_word(text):
                    # 3. Still no command. Prompt them.
                    logger.debug("No command after 10s wait. Asking how to help.")
                    await self._speak("How can I assist you?")
                    text = "" # Clear text so we don't execute the wake word in the loop

            # 4. Active Conversational Loop
            while time.time() < deadline:
                if self._manually_stopped:
                    logger.debug("Manually stopped — returning to idle")
                    self._manually_stopped = False
                    break
                
                if text.strip() and not self._is_only_wake_word(text):
                    # We have a valid command! Execute it.
                    self._set_state(PipelineState.PROCESSING)
                    logger.info(f"📝 Transcript: '{text}'")
                    if self.on_transcript:
                        self.on_transcript(text, True)

                    from app.services.command_service import command_service
                    clean_text = self._strip_wake_word(text)
                    logger.info(f"🚀 Passing to command_service: '{clean_text}'")
                    result = await command_service.parse_and_execute(clean_text)
                    if self.on_command_result:
                        self.on_command_result(result)

                    response_text = result.get("result", "Done")
                    await self._speak(response_text)
                    
                    if getattr(settings, 'require_wake_word_always', False):
                        logger.info("Require wake word always is enabled. Exiting Active Mode after single command.")
                        break

                    # Reset deadline after execution to give another full window
                    deadline = time.time() + active_timeout
                
                # Check if timeout reached
                time_left = deadline - time.time()
                if time_left <= 0:
                    break
                    
                # Listen again
                listen_timeout = min(15.0, time_left) 
                audio_bytes, text = await self._capture_and_stream(timeout=listen_timeout, max_initial_silence_chunks=150)

            # Loop finished
            logger.info("Active Mode finished or timed out. Returning to IDLE.")
            
        except Exception as e:
            logger.error(f"Pipeline error: {e}")
            self._audio_capture.stop()
            self._set_state(PipelineState.ERROR)
            await asyncio.sleep(1)
        finally:
            self._set_state(PipelineState.IDLE)
            self._wake_word.start()

    async def _speak(self, text: str) -> None:
        """Synthesize and play TTS response."""
        self._last_spoken_text = text
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

    def replay(self) -> None:
        """Replay the last spoken text and emit it as a websocket event."""
        if not self._last_spoken_text:
            if self.on_transcript:
                self.on_transcript("__replay_empty__", True)
            return
        if self._state != PipelineState.IDLE:
            return
        # Emit the replay text as a special transcript so overlay can display it
        if self.on_transcript:
            self.on_transcript(f"__replay__{self._last_spoken_text}", True)
            
        async def _do_replay():
            await self._speak(self._last_spoken_text)
            self._set_state(PipelineState.IDLE)
            
        if self._loop:
            asyncio.run_coroutine_threadsafe(_do_replay(), self._loop)
            
    def speak_suggestion(self) -> None:
        """Fetch a random context-aware suggestion and speak it."""
        if self._state != PipelineState.IDLE:
            return

        async def _do_suggest():
            from app.services.command_service import command_service
            import random
            suggs = command_service.get_suggestions(limit=5)
            if suggs and suggs.get("suggestions"):
                s = random.choice(suggs["suggestions"])
                # Emit text so overlay can display it immediately
                if self.on_transcript:
                    self.on_transcript(f"__suggestion__{s}", True)
                # Also speak it
                await self._speak(f"You can try: {s}")
            else:
                if self.on_transcript:
                    self.on_transcript("__suggestion__Try saying: Hey ACE, open Chrome", True)
            self._set_state(PipelineState.IDLE)

        if self._loop:
            asyncio.run_coroutine_threadsafe(_do_suggest(), self._loop)
