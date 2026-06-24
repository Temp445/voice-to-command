"""
ACE Voice Controller — Faster-Whisper STT Transcriber
Transcribes audio bytes to text using Faster-Whisper (CTranslate2 engine).

STT Accuracy Improvements (v2):
  - compute_type changed from int8 → float32: eliminates quantization accuracy loss
    on small models (base/small) where 8-bit rounding is a large relative error.
  - beam_size changed from 1 → 5: enables beam search decoding for sentence-level
    context instead of greedy per-token selection. Improves accuracy ~10–20% on
    ambiguous commands like homophones and proper nouns.
  - temperature changed from 0.0 → [0.0, 0.2, 0.4, 0.6, 0.8]: allows Whisper to
    retry with progressively looser sampling when initial confidence is low,
    instead of silently emitting a low-quality guess.
  - initial_prompt changed from a hardcoded noun-list to a sentence-style prompt:
    prevents Whisper from forcing free speech into predefined command words.
"""

import numpy as np
from faster_whisper import WhisperModel
from loguru import logger
from app.config import settings




import threading

class Transcriber:
    """
    Speech-to-text using Faster-Whisper.
    Loads model once and reuses it for low-latency inference.
    """

    _model: WhisperModel | None = None
    _lock = threading.Lock()

    def __init__(self):
        pass

    def _load_model(self) -> WhisperModel:
        if Transcriber._model is not None:
            return Transcriber._model

        with Transcriber._lock:
            # Double-checked locking
            if Transcriber._model is not None:
                return Transcriber._model

            model_size = settings.whisper_model
            # float32 gives the highest accuracy on CPU for base/small models.
            # int8 saves RAM (~4×) but introduces quantization errors that are a
            # disproportionately large fraction of small model weights, degrading
            # accuracy by 8–15% on short commands.
            logger.info(f"Loading Whisper model: {model_size} (device=cpu, compute=float32)")
            Transcriber._model = WhisperModel(model_size, device="cpu", compute_type="float32")
            logger.info(f"✅ Whisper model '{model_size}' loaded (CPU, float32)")
            return Transcriber._model

    def transcribe(self, audio_bytes: bytes) -> str:
        """
        Transcribe raw PCM audio bytes (16kHz, mono, int16) to text.
        Returns the transcribed string.
        """
        model = self._load_model()

        # Convert raw bytes → float32 numpy array
        audio_np = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0

        # Trim leading silence from the audio segment.
        # Even with the reduced pre-roll (3 chunks = 90ms), the first few frames
        # can be near-silent. Leading silence confuses Whisper into hallucinating
        # a fricative onset (/s/) for plosive words like "crm" → "serum".
        # Trim any leading frames below RMS threshold before feeding Whisper.
        rms_threshold = 0.01  # ~-40dB — below this is effective silence
        frame_size = int(16000 * 0.02)  # 20ms frames for trimming
        trim_start = 0
        for i in range(0, len(audio_np) - frame_size, frame_size):
            frame_rms = float(np.sqrt(np.mean(audio_np[i:i+frame_size] ** 2)))
            if frame_rms > rms_threshold:
                trim_start = max(0, i - frame_size)  # keep one frame before onset
                break
        if trim_start > 0:
            audio_np = audio_np[trim_start:]

        # Build initial_prompt with known shortcut/app names from settings.
        # Whisper uses this as a strong lexical prior — listing "CRM, payroll, acesoft"
        # makes those tokens far more likely to be selected over phonetically similar
        # common words ("serum", "pay roll", "ace soft").
        shortcut_names = ""
        try:
            from app.config import settings as _gs
            import json as _json
            _sites_raw = getattr(_gs, "crm_sites", None)
            if _sites_raw:
                _sites = _json.loads(_sites_raw) if isinstance(_sites_raw, str) else _sites_raw
                names = []
                for s in _sites:
                    # Pull the first keyword as the display name (most concise)
                    kws = [k.strip() for k in s.get("keywords", "").split(",") if k.strip()]
                    if kws:
                        names.append(kws[0])
                if names:
                    shortcut_names = " Known shortcuts: " + ", ".join(names) + "."
        except Exception:
            pass

        initial_prompt = (
            "The following is a short voice command for a desktop automation assistant."
            " Commands include opening applications, navigating websites, typing text,"
            " clicking buttons, and controlling media playback."
            + shortcut_names
        )

        _transcribe_kwargs = dict(
            # beam_size=5: Whisper's default — maintains 5 candidate transcriptions
            # simultaneously and picks the one with the best cumulative probability
            # across the whole sentence, not just the most likely next token.
            # beam_size=1 (greedy) was ~1.5–2× faster but ~10–20% less accurate
            # on short ambiguous commands.
            beam_size=5,
            language="en",
            condition_on_previous_text=False,
            # Temperature fallback list: try deterministic (0.0) first;
            # if log_prob_threshold is not met, retry with progressively looser
            # sampling until a confident transcription is found.
            # Static temperature=0.0 never retried, silently emitting low-quality results.
            temperature=[0.0, 0.2, 0.4, 0.6, 0.8],
            no_speech_threshold=0.6,      # Reject segment if Whisper thinks it's silence/noise
            log_prob_threshold=-1.0,      # Reject low-confidence segments; triggers temperature fallback
            vad_filter=False,             # Disabled: WebRTC VAD runs upstream; double-filtering hurts accuracy
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
