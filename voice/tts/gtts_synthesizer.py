"""
ACE Voice Controller — gTTS Provider (Google Cloud Text-to-Speech)
Uses Google Cloud TTS REST API. Requires an API key.
Falls back to Piper TTS if API key is missing or request fails.
"""

import asyncio
import io
import json
import base64
import httpx
from loguru import logger

from voice.tts.base import TTSProvider
from app.config import settings


GOOGLE_TTS_URL = "https://texttospeech.googleapis.com/v1/text:synthesize"

# Default voice config (high quality WaveNet)
_DEFAULT_VOICE = {
    "languageCode": "en-US",
    "name": "en-US-Wavenet-D",
    "ssmlGender": "MALE",
}

_DEFAULT_AUDIO_CONFIG = {
    "audioEncoding": "LINEAR16",  # WAV
    "speakingRate": 1.0,
    "pitch": 0.0,
    "volumeGainDb": 0.0,
}


class GTTSSynthesizer(TTSProvider):
    """
    Google Cloud Text-to-Speech provider.
    Requires GTTS_API_KEY in settings (stored encrypted in DB).
    """

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key or settings.gtts_api_key

    def requires_api_key(self) -> bool:
        return True

    def is_configured(self) -> bool:
        return bool(self._api_key and self._api_key.strip())

    async def synthesize(self, text: str) -> bytes:
        if not self.is_configured():
            logger.warning("gTTS API key not set — falling back to Piper TTS")
            from voice.tts.piper_synthesizer import PiperSynthesizer
            return await PiperSynthesizer().synthesize(text)

        payload = {
            "input": {"text": text},
            "voice": _DEFAULT_VOICE,
            "audioConfig": _DEFAULT_AUDIO_CONFIG,
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    GOOGLE_TTS_URL,
                    params={"key": self._api_key},
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
                audio_b64 = data.get("audioContent", "")
                return base64.b64decode(audio_b64)

        except httpx.HTTPStatusError as e:
            logger.error(f"Google TTS API error {e.response.status_code}: {e.response.text}")
            logger.warning("Falling back to Piper TTS due to gTTS error")
            from voice.tts.piper_synthesizer import PiperSynthesizer
            return await PiperSynthesizer().synthesize(text)

        except Exception as e:
            logger.error(f"gTTS synthesis failed: {e}")
            from voice.tts.piper_synthesizer import PiperSynthesizer
            return await PiperSynthesizer().synthesize(text)

    async def get_available_voices(self) -> list[str]:
        """Fetch available voices from Google TTS API."""
        if not self.is_configured():
            return []
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    "https://texttospeech.googleapis.com/v1/voices",
                    params={"key": self._api_key},
                )
                resp.raise_for_status()
                voices = resp.json().get("voices", [])
                return [v["name"] for v in voices if "en-US" in v.get("languageCodes", [])]
        except Exception as e:
            logger.warning(f"Could not fetch gTTS voices: {e}")
            return []
