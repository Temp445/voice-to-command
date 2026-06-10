"""
ACE Voice Controller — Faster-Whisper STT Transcriber
Transcribes audio bytes to text using Faster-Whisper (CTranslate2 engine).
"""

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
        pass

    def _load_model(self) -> WhisperModel:
        if Transcriber._model is not None:
            return Transcriber._model

        model_size = settings.whisper_model
        # Always use CPU — this system does not have the CUDA 12 runtime
        # (cublas64_12.dll). Using device="cpu" avoids a failed CUDA probe
        # on every startup and gives clean, warning-free logs.
        logger.info(f"Loading Whisper model: {model_size} (device=cpu, compute=int8)")
        Transcriber._model = WhisperModel(model_size, device="cpu", compute_type="int8")
        logger.info(f"✅ Whisper model '{model_size}' loaded (CPU)")
        return Transcriber._model

    def transcribe(self, audio_bytes: bytes) -> str:
        """
        Transcribe raw PCM audio bytes (16kHz, mono, int16) to text.
        Returns the transcribed string.
        """
        model = self._load_model()

        # Convert raw bytes -> float32 numpy array
        audio_np = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0

        # Context-aware prompt to establish tone, verb usage, and vocabulary.
        # This prevents common phonetic errors (e.g. "Notepad" -> "not bad") and improves
        # intent recognition for desktop and CRM commands.
        initial_prompt = "Voice commands: Open Notepad, Chrome, Spotify, YouTube, CRM, play, pause, next, select, close, mute, volume."

        _transcribe_kwargs = dict(
            beam_size=1,                  # Greedy decoding: massively reduces CPU processing time
            language="en",
            condition_on_previous_text=False,
            temperature=0.0,              # Deterministic -- eliminates hallucinations on short phrases
            no_speech_threshold=0.6,      # Reject segment if Whisper thinks it's silence/noise
            log_prob_threshold=-1.0,      # Reject low-confidence segments
            vad_filter=False,             # Disabled: We use WebRTC VAD before STT for instant streaming
            initial_prompt=initial_prompt,
            word_timestamps=False,        # Not needed; skip for speed
        )

        segments_gen, info = model.transcribe(audio_np, **_transcribe_kwargs)
        segment_list = list(segments_gen)

        # Filter out hallucinated segments (Whisper sometimes generates text from silence)
        NO_SPEECH_PROB_THRESHOLD = 0.6
        kept = []
        for seg in segment_list:
            if seg.no_speech_prob < NO_SPEECH_PROB_THRESHOLD:
                kept.append(seg.text.strip())
            else:
                logger.debug(
                    f"Dropped hallucinated segment (no_speech_prob={seg.no_speech_prob:.2f}): '{seg.text.strip()}'"
                )

        text = " ".join(kept).strip()
        logger.debug(f"Transcribed ({info.language}, {info.duration:.1f}s): '{text}'")
        return text

    @classmethod
    def reload_model(cls) -> None:
        """Force model reload (e.g., after model size change in settings)."""
        cls._model = None
        logger.info("Whisper model unloaded -- will reload on next transcription")
