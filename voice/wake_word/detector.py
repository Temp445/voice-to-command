"""
ACE Voice Controller — OpenWakeWord Detector
Always-listening background thread that fires an event on "alexa" detection.
"""

import threading
import queue
import numpy as np
import pyaudio
from loguru import logger
from typing import Callable

try:
    import openwakeword
    from openwakeword.model import Model as OWWModel
    OWW_AVAILABLE = True
except ImportError:
    OWW_AVAILABLE = False
    logger.warning("openwakeword not installed — wake word detection disabled")


SAMPLE_RATE = 16000
CHUNK_SIZE = 1280          # 80ms at 16kHz (OWW requirement)
FORMAT = pyaudio.paInt16
CHANNELS = 1
DETECTION_THRESHOLD = 0.50  # Confidence threshold (Lowered to 0.50 to make it more responsive to different voices)

# Max bytes we allow to queue up before dropping stale audio.
# 3 × 1280 samples × 2 bytes = ~240ms of backlog before we start skipping.
_MAX_BUFFER_BYTES = CHUNK_SIZE * 2 * 3


class WakeWordDetector:
    """
    Listens continuously for the configured wake word using OpenWakeWord.
    Calls `on_detected` callback when wake word is heard.
    """

    def __init__(self, wake_word: str = "alexa", on_detected: Callable | None = None):
        raw_wake_word = wake_word.lower().strip()
        
        # OpenWakeWord only supports specific pre-trained models.
        # Map user input to the correct acoustic model, or fallback to alexa.
        model_map = {
            "alexa": "alexa",
            "hey jarvis": "hey_jarvis",
            "hey_jarvis": "hey_jarvis",
            "hey mycroft": "hey_mycroft",
            "hey_mycroft": "hey_mycroft",
            "hey rhasspy": "hey_rhasspy",
            "hey_rhasspy": "hey_rhasspy",
        }
        
        self.acoustic_model = model_map.get(raw_wake_word, "alexa")
        # Overwrite the actual wake_word used by the pipeline for stripping
        # to match what the acoustic model is actually listening for.
        self.wake_word = self.acoustic_model.replace("_", " ")
        
        if raw_wake_word not in model_map:
            logger.warning(
                f"⚠️ Wake word '{raw_wake_word}' has no offline model. "
                f"Falling back to '{self.wake_word}'. You MUST SAY: '{self.wake_word}'!"
            )
            
        self.on_detected = on_detected
        self._running = False
        self._thread: threading.Thread | None = None
        self._model: "OWWModel | None" = None
        self._audio = pyaudio.PyAudio()
        self._audio_buffer = np.array([], dtype=np.int16)
        self._chunk_counter = 0

    def _load_model(self) -> "OWWModel":
        if not OWW_AVAILABLE:
            raise RuntimeError("openwakeword is not installed")

        logger.info(f"Loading OpenWakeWord model: '{self.acoustic_model}'")

        try:
            from openwakeword.utils import download_models
            download_models(model_names=[f"{self.acoustic_model}_v0.1"])
        except Exception as e:
            logger.warning(f"Could not download model {self.acoustic_model}: {e}")

        return OWWModel(wakeword_models=[self.acoustic_model], inference_framework="onnx")

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._detection_loop, daemon=True)
        self._thread.start()
        logger.info(f"👂 Wake word detector started for: '{self.wake_word}'")

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=3)
        logger.info("👂 Wake word detector stopped")

    def _detection_loop(self) -> None:
        while self._model is None and self._running:
            try:
                self._model = self._load_model()
            except Exception as e:
                logger.error(f"Failed to load wake word model: {e}. Retrying in 5s...")
                import time
                time.sleep(5)
                continue

        if not self._running:
            return

        from voice.remote_mic import subscribe, unsubscribe
        remote_q = subscribe()

        logger.info(f"✅ Listening for wake word: '{self.wake_word}' (Global Mic Stream)")

        try:
            while self._running:
                # ─── FIX 1: Get ONE chunk at a time, never drain the whole queue.
                # Draining accumulates hundreds of ms of audio before OWW sees any
                # of it, which causes detections to fire long after the word was spoken.
                try:
                    raw = remote_q.get(timeout=0.08)   # 80ms = one OWW frame
                except queue.Empty:
                    continue

                if not raw:
                    continue

                # ─── FIX 2: Only drop stale audio if severely behind (> 4 seconds).
                # Predict is fast (~5ms), so we should just process the queue to catch up.
                # Dropping audio breaks the contiguous stream OpenWakeWord needs to detect words.
                backlog = remote_q.qsize()
                if backlog > 50:
                    logger.warning(f"Audio queue severely behind ({backlog} chunks). Dropping stale audio to catch up.")
                    while not remote_q.empty():
                        try:
                            remote_q.get_nowait()
                        except queue.Empty:
                            break
                    self._audio_buffer = np.array([], dtype=np.int16)

                # ─── FIX 3: Ensure even byte count before converting.
                if len(raw) % 2 != 0:
                    raw = raw[: -(len(raw) % 2)]

                audio_np = np.frombuffer(raw, dtype=np.int16)
                self._audio_buffer = np.concatenate((self._audio_buffer, audio_np))

                # ─── Process every complete 1280-sample chunk immediately.
                # No batching — each chunk is fed to OWW as soon as it arrives.
                while len(self._audio_buffer) >= CHUNK_SIZE:
                    chunk = self._audio_buffer[:CHUNK_SIZE]
                    self._audio_buffer = self._audio_buffer[CHUNK_SIZE:]

                    self._chunk_counter += 1
                    if self._chunk_counter % 50 == 0:
                        rms = np.sqrt(np.mean(chunk.astype(np.float32) ** 2))
                        logger.info(f"🎙️ Audio Stream Active: RMS amplitude = {rms:.1f} (counter={self._chunk_counter})")

                    predictions = self._model.predict(chunk)

                    detected = False
                    for model_name, score in predictions.items():
                        if score > 0.05:
                            logger.info(f"Wake word '{model_name}' score: {score:.3f}")
                        if score >= DETECTION_THRESHOLD:
                            logger.info(
                                f"🔔 Wake word detected! ('{self.wake_word}', score={score:.2f})"
                            )
                            self._model.reset()
                            self._audio_buffer = np.array([], dtype=np.int16)
                            if self.on_detected:
                                self.on_detected()
                            detected = True
                            break

                    if detected:
                        break   # stop processing remaining buffer chunks this cycle

        except Exception as e:
            logger.error(f"Detector loop error: {e}")
        finally:
            unsubscribe(remote_q)