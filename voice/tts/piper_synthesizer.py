"""
ACE Voice Controller — Piper TTS Provider (Offline)
Uses piper-tts to synthesize speech locally using .onnx voice models.
"""

import asyncio
import io
import wave
from pathlib import Path

from loguru import logger

from voice.tts.base import TTSProvider
from app.config import settings, _ROOT

try:
    from piper import PiperVoice, SynthesisConfig
except ImportError:
    PiperVoice = None
    SynthesisConfig = None


class PiperSynthesizer(TTSProvider):
    """
    Fully offline TTS using Piper. Requires a downloaded .onnx voice model.
    Model is auto-downloaded on first use via scripts/download_models.py.
    """

    _cached_piper_voice = None
    _cached_loaded_voice = ""

    def __init__(self):
        models_dir_path = Path(settings.piper_models_dir)
        if not models_dir_path.is_absolute():
            # Use _DATA_ROOT to properly support PyInstaller _internal structure
            from app.config import _DATA_ROOT
            self.models_dir = _DATA_ROOT / models_dir_path
        else:
            self.models_dir = models_dir_path
        self.voice = settings.piper_voice
        self.models_dir.mkdir(parents=True, exist_ok=True)
        
        self._piper_voice = PiperSynthesizer._cached_piper_voice

    def requires_api_key(self) -> bool:
        return False

    def is_configured(self) -> bool:
        model_path = self.models_dir / f"{self.voice}.onnx"
        return model_path.exists()

    def _load_voice_if_needed(self):
        """Load the ONNX model into memory (takes a few seconds, but only happens once)."""
        if PiperVoice is None:
            raise RuntimeError("piper-tts python package is not installed. Run `pip install piper-tts`")

        model_path = self.models_dir / f"{self.voice}.onnx"
        if not model_path.exists():
            logger.error(f"Piper model not found: {model_path}. Run scripts/download_models.py")
            raise FileNotFoundError(f"Piper voice model not found: {model_path}")

        if PiperSynthesizer._cached_piper_voice is None or PiperSynthesizer._cached_loaded_voice != self.voice:
            logger.info(f"Loading Piper voice model into memory: {self.voice} (this may take ~10 seconds...)")
            PiperSynthesizer._cached_piper_voice = PiperVoice.load(str(model_path))
            PiperSynthesizer._cached_loaded_voice = self.voice
            logger.info(f"Successfully loaded Piper voice: {self.voice}")
            
        self._piper_voice = PiperSynthesizer._cached_piper_voice

    async def synthesize(self, text: str) -> bytes:
        """Run Piper synthesis in a thread pool (CPU-bound)."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._synthesize_sync, text)

    def _synthesize_sync(self, text: str) -> bytes:
        # Load model into memory if not already loaded (or if voice changed)
        self._load_voice_if_needed()

        # Read speech rate and compute length scale (speed multiplier)
        speed = getattr(settings, "speech_rate", 1.0)
        length_scale = 1.0 / max(0.1, speed)

        # Synthesize directly to an in-memory WAV buffer
        wav_io = io.BytesIO()
        config = SynthesisConfig(length_scale=length_scale) if SynthesisConfig else None
        with wave.open(wav_io, "wb") as wav_file:
            self._piper_voice.synthesize_wav(text, wav_file, syn_config=config)
            
        return wav_io.getvalue()

    async def get_available_voices(self) -> list[str]:
        """Return available .onnx models in the models directory."""
        return [p.stem for p in self.models_dir.glob("*.onnx")]
