"""
ACE Voice Controller — TTS Provider Factory
Hot-swappable: reads active provider from settings on every call.
"""

from loguru import logger
from voice.tts.base import TTSProvider


async def get_tts_provider() -> TTSProvider:
    """
    Return the active TTS provider based on current settings.
    Hot-reloads on every call so settings changes take effect immediately.
    """
    from app.config import settings  # re-read each time for hot-swap

    provider = settings.tts_provider.lower()

    if provider == "gtts":
        from voice.tts.gtts_synthesizer import GTTSSynthesizer
        instance = GTTSSynthesizer()
        if not instance.is_configured():
            logger.warning("gTTS selected but API key not set — using Piper TTS")
            from voice.tts.piper_synthesizer import PiperSynthesizer
            return PiperSynthesizer()
        return instance

    # Default: Piper TTS
    from voice.tts.piper_synthesizer import PiperSynthesizer
    return PiperSynthesizer()
