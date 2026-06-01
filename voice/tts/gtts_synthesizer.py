"""
ACE Voice Controller — gTTS Provider (Google Cloud Text-to-Speech)
Uses Google Cloud TTS REST API. Requires an API key.
Falls back to Piper TTS if API key is missing or request fails.
"""

import io
from loguru import logger
from voice.tts.base import TTSProvider

class GTTSSynthesizer(TTSProvider):
    """
    gTTS Provider. Uses the free gTTS python module.
    No API key required!
    """

    def __init__(self, api_key: str | None = None):
        pass

    def requires_api_key(self) -> bool:
        return False

    def is_configured(self) -> bool:
        return True

    async def synthesize(self, text: str) -> bytes:
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._synthesize_sync, text)

    def _synthesize_sync(self, text: str) -> bytes:
        from gtts import gTTS
        try:
            tts = gTTS(text, lang='en')
            fp = io.BytesIO()
            tts.write_to_fp(fp)
            return fp.getvalue()
        except Exception as e:
            logger.error(f"gTTS synthesis failed: {e}")
            raise e

    async def get_available_voices(self) -> list[str]:
        return ["en"]

