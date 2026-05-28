"""
ACE Voice Controller — Piper TTS Provider (Offline)
Uses piper-tts to synthesize speech locally using .onnx voice models.
"""

import asyncio
import io
import subprocess
import tempfile
import wave
from pathlib import Path

from loguru import logger

from voice.tts.base import TTSProvider
from app.config import settings


class PiperSynthesizer(TTSProvider):
    """
    Fully offline TTS using Piper. Requires a downloaded .onnx voice model.
    Model is auto-downloaded on first use via scripts/download_models.py.
    """

    def __init__(self):
        self.models_dir = Path(settings.piper_models_dir)
        self.voice = settings.piper_voice
        self.models_dir.mkdir(parents=True, exist_ok=True)

    def requires_api_key(self) -> bool:
        return False

    def is_configured(self) -> bool:
        model_path = self.models_dir / f"{self.voice}.onnx"
        return model_path.exists()

    async def synthesize(self, text: str) -> bytes:
        """Run Piper synthesis in a thread pool (CPU-bound)."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._synthesize_sync, text)

    def _synthesize_sync(self, text: str) -> bytes:
        model_path = self.models_dir / f"{self.voice}.onnx"
        model_json = self.models_dir / f"{self.voice}.onnx.json"

        if not model_path.exists():
            logger.error(f"Piper model not found: {model_path}. Run scripts/download_models.py")
            raise FileNotFoundError(f"Piper voice model not found: {model_path}")

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            result = subprocess.run(
                [
                    "piper",
                    "--model", str(model_path),
                    "--output_file", tmp_path,
                ],
                input=text,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                raise RuntimeError(f"Piper failed: {result.stderr}")

            with open(tmp_path, "rb") as f:
                return f.read()

        finally:
            Path(tmp_path).unlink(missing_ok=True)

    async def get_available_voices(self) -> list[str]:
        """Return available .onnx models in the models directory."""
        return [p.stem for p in self.models_dir.glob("*.onnx")]
