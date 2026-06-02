"""
ACE Voice Controller — Faster-Whisper STT Transcriber
Transcribes audio bytes to text using Faster-Whisper (CTranslate2 engine).
"""

import io
import numpy as np
from faster_whisper import WhisperModel
from loguru import logger
from app.config import settings


class Transcriber:
    """
    Speech-to-text using Faster-Whisper.
    Loads model once and reuses it for low-latency inference.
    """

    _model: WhisperModel | None = None

    def __init__(self):
        self._model_size = settings.whisper_model

    def _load_model(self) -> WhisperModel:
        if Transcriber._model is None:
            logger.info(f"Loading Whisper model: {self._model_size}")
            Transcriber._model = WhisperModel(
                self._model_size,
                device="cpu",
                compute_type="int8",    # quantised for speed
            )
            logger.info(f"✅ Whisper model '{self._model_size}' loaded")
        return Transcriber._model

    def transcribe(self, audio_bytes: bytes) -> str:
        """
        Transcribe raw PCM audio bytes (16kHz, mono, int16) to text.
        Returns the transcribed string.
        """
        model = self._load_model()

        # Convert raw bytes → float32 numpy array
        audio_np = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0

        # Dynamically build initial prompt from registered intents to dramatically improve accuracy
        try:
            from app.services.command_service import command_service
            intents = [i["name"].replace("_", " ") for i in command_service.list_intents()]
            dynamic_prompt = "desktop assistant commands: " + ", ".join(intents) + "."
        except Exception:
            dynamic_prompt = "desktop assistant commands: open application, close application, system settings, minimize window."

        segments, info = model.transcribe(
            audio_np,
            beam_size=5,
            language="en",
            condition_on_previous_text=False,
            vad_filter=True,              # Built-in VAD silences noise
            vad_parameters={"min_silence_duration_ms": 500},
            initial_prompt=dynamic_prompt,
        )

        text = " ".join(s.text.strip() for s in segments).strip()
        logger.debug(f"Transcribed ({info.language}, {info.duration:.1f}s): '{text}'")
        return text

    @classmethod
    def reload_model(cls) -> None:
        """Force model reload (e.g., after model size change in settings)."""
        cls._model = None
        logger.info("Whisper model unloaded — will reload on next transcription")
