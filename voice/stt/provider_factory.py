"""
ACE Voice Controller — STT Provider Factory
Hot-swappable: reads active provider from settings on every call.
"""

from loguru import logger

def get_stt_provider():
    """
    Return the active STT provider based on current settings.
    Hot-reloads on every call so settings changes take effect immediately.
    """
    from app.config import settings

    provider = settings.stt_provider.lower() if hasattr(settings, 'stt_provider') else "whisper"

    if provider == "gstt" or provider == "google":
        try:
            from voice.stt.google_stt import GoogleSTTTranscriber
            return GoogleSTTTranscriber()
        except ImportError:
            logger.warning("SpeechRecognition not installed. Falling back to Whisper.")
            pass

    if provider == "elevenlabs" or provider == "eleven":
        try:
            from voice.stt.elevenlabs_stt import ElevenLabsSTTTranscriber
            return ElevenLabsSTTTranscriber()
        except Exception as e:
            logger.warning(f"Failed to load ElevenLabs STT: {e}. Falling back to Whisper.")
            pass

    if provider == "deepgram":
        try:
            from voice.stt.deepgram_stt import DeepgramSTTTranscriber
            return DeepgramSTTTranscriber()
        except Exception as e:
            logger.warning(f"Failed to load Deepgram STT: {e}. Falling back to Whisper.")
            pass

    # Default: Whisper TTS
    from voice.stt.transcriber import Transcriber as WhisperTranscriber
    return WhisperTranscriber()
