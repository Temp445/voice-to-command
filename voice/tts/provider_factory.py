"""
ACE Voice Controller — TTS Provider Factory
Hot-swappable: reads active provider from settings on every call.
"""

from loguru import logger
from voice.tts.base import TTSProvider


_cached_providers: dict[str, TTSProvider] = {}

async def get_tts_provider() -> TTSProvider:
    """
    Return the active TTS provider based on current settings.
    Caches provider instances to avoid reloading models from disk every time.
    """
    from app.config import settings

    provider_type = settings.tts_provider.lower()

    if provider_type not in _cached_providers:
        if provider_type == "gtts":
            from voice.tts.gtts_synthesizer import GTTSSynthesizer
            _cached_providers[provider_type] = GTTSSynthesizer()
        else:
            # Default: Piper TTS
            from voice.tts.piper_synthesizer import PiperSynthesizer
            # Use 'piper' as key even if it's not strictly 'piper' in settings
            provider_type = "piper"
            _cached_providers[provider_type] = PiperSynthesizer()

    provider = _cached_providers[provider_type]
    
    # Hot-reload specific settings onto the cached instance
    if provider_type == "piper":
        provider.voice = settings.piper_voice

    return provider
