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
DETECTION_THRESHOLD = 0.3  # Confidence threshold


class WakeWordDetector:
    """
    Listens continuously for the configured wake word using OpenWakeWord.
    Calls `on_detected` callback when wake word is heard.
    """

    def __init__(self, wake_word: str = "alexa", on_detected: Callable | None = None):
        self.wake_word = wake_word.lower().strip()
        self.on_detected = on_detected
        self._running = False
        self._thread: threading.Thread | None = None
        self._model: "OWWModel | None" = None
        self._audio = pyaudio.PyAudio()

    def _load_model(self) -> "OWWModel":
        if not OWW_AVAILABLE:
            raise RuntimeError("openwakeword is not installed")

        # OWW supports pre-trained wake words: hey_jarvis, alexa, hey_mycroft, hey_rhasspy
        # The acoustic model must match what is actually spoken
        model_map = {
            "alexa":      "alexa",
        }
        model_name = model_map.get(self.wake_word, "alexa")

        if self.wake_word != model_name.replace("_", " "):
            logger.warning(
                f"⚠️  Wake word '{self.wake_word}' has no dedicated offline model. "
                f"Using '{model_name}' acoustic model. "
                f"You MUST SAY: '{model_name.replace('_', ' ')}' to trigger detection!"
            )
        else:
            logger.info(f"Loading OpenWakeWord model for: '{self.wake_word}' (using '{model_name}')")
        
        # We explicitly omit openwakeword.utils.download_models() because it attempts to
        # download ALL models (30+ files) which frequently causes HuggingFace connection timeouts.
        # The OWWModel constructor will automatically download just the requested model.
        return OWWModel(wakeword_models=[model_name], inference_framework="onnx")

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

        from voice.remote_mic import subscribe
        remote_q = subscribe()
        import queue

        logger.info(f"✅ Listening for wake word: '{self.wake_word}' (Global Mic Stream)")

        try:
            while self._running:
                try:
                    raw = remote_q.get(timeout=0.1)
                except queue.Empty:
                    continue

                if not raw:
                    continue

                if len(raw) % 2 != 0:
                    raw = raw[:-(len(raw) % 2)]

                audio_np = np.frombuffer(raw, dtype=np.int16)
                predictions = self._model.predict(audio_np)

                for model_name, score in predictions.items():
                    if score > 0.1:
                        logger.debug(f"Wake word '{model_name}' score: {score:.3f}")
                    if score >= DETECTION_THRESHOLD:
                        logger.info(f"🔔 Wake word detected! ('{self.wake_word}', score={score:.2f})")
                        self._model.reset()   # Reset prediction buffer
                        # NOTE: We DO NOT clear queues anymore! 
                        # Doing so destroys the command audio that immediately follows the wake word.
                        if self.on_detected:
                            self.on_detected()
                        break
        except Exception as e:
            logger.error(f"Detector loop error: {e}")
