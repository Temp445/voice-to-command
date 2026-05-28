"""
ACE Voice Controller — OpenWakeWord Detector
Always-listening background thread that fires an event on "hey ace" detection.
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
DETECTION_THRESHOLD = 0.5  # Confidence threshold


class WakeWordDetector:
    """
    Listens continuously for the configured wake word using OpenWakeWord.
    Calls `on_detected` callback when wake word is heard.
    """

    def __init__(self, wake_word: str = "hey ace", on_detected: Callable | None = None):
        self.wake_word = wake_word.lower().strip()
        self.on_detected = on_detected
        self._running = False
        self._thread: threading.Thread | None = None
        self._model: "OWWModel | None" = None

    def _load_model(self) -> "OWWModel":
        if not OWW_AVAILABLE:
            raise RuntimeError("openwakeword is not installed")

        # OWW supports pre-trained wake words: hey_jarvis, alexa, hey_mycroft, etc.
        # Map "hey ace" to closest available or use custom model if provided
        model_map = {
            "hey ace": "hey_jarvis",       # Closest match; replace with custom trained model
            "hey jarvis": "hey_jarvis",
            "alexa": "alexa",
        }
        model_name = model_map.get(self.wake_word, "hey_jarvis")

        logger.info(f"Loading OpenWakeWord model for: '{self.wake_word}' (using '{model_name}')")
        openwakeword.utils.download_models()   # Download if not cached
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
        try:
            self._model = self._load_model()
        except Exception as e:
            logger.error(f"Failed to load wake word model: {e}")
            return

        audio = pyaudio.PyAudio()
        stream = audio.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=SAMPLE_RATE,
            input=True,
            frames_per_buffer=CHUNK_SIZE,
        )

        logger.info(f"✅ Listening for wake word: '{self.wake_word}'")

        try:
            while self._running:
                raw = stream.read(CHUNK_SIZE, exception_on_overflow=False)
                audio_np = np.frombuffer(raw, dtype=np.int16)
                predictions = self._model.predict(audio_np)

                for model_name, score in predictions.items():
                    if score >= DETECTION_THRESHOLD:
                        logger.info(f"🔔 Wake word detected! ('{self.wake_word}', score={score:.2f})")
                        self._model.reset()   # Reset prediction buffer
                        if self.on_detected:
                            self.on_detected()
                        break
        finally:
            stream.stop_stream()
            stream.close()
            audio.terminate()
