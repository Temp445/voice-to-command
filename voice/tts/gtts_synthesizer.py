"""
ACE Voice Controller — gTTS Provider (Google Text-to-Speech)
Uses the free Google Translate TTS API via the `gTTS` Python library.
No API key required!
"""

import asyncio
import io
from loguru import logger
from gtts import gTTS

from voice.tts.base import TTSProvider


class GTTSSynthesizer(TTSProvider):
    """
    Google Text-to-Speech provider using the free gTTS library.
    Requires no API key and provides high-quality voices over the internet.
    """

    def __init__(self):
        pass

    def requires_api_key(self) -> bool:
        return False

    def is_configured(self) -> bool:
        return True

    async def synthesize(self, text: str) -> bytes:
        """Run gTTS synthesis in a thread pool (blocking network I/O)."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._synthesize_sync, text)

    def _synthesize_sync(self, text: str) -> bytes:
        try:
            # Create gTTS object. lang='en', tld='com' for standard US English
            tts = gTTS(text=text, lang='en', tld='com', slow=False)
            fp = io.BytesIO()
            tts.write_to_fp(fp)
            fp.seek(0)
            return fp.read()
        except Exception as e:
            logger.error(f"gTTS synthesis failed: {e}")
            raise

    async def get_available_voices(self) -> list[str]:
        """Return standard dialects supported by gTTS."""
        return [
            "en-us (English US)",
            "en-uk (English UK)",
            "en-au (English Australia)",
            "en-in (English India)"
        ]
