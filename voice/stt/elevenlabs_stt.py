"""
ACE Voice Controller — ElevenLabs Speech-to-Text Transcriber
Uses the ElevenLabs Scribe API for high-accuracy cloud-based transcription.
"""

import io
import wave
import os
from loguru import logger
from elevenlabs.client import ElevenLabs
from app.config import settings

class ElevenLabsSTTTranscriber:
    """
    Speech-to-text transcriber using ElevenLabs Scribe v2 API.
    """

    def __init__(self):
        # Resolve ElevenLabs API key: priority is in-memory settings (set dynamically), fallback is environment variable
        self.api_key = settings.elevenlabs_api_key or os.getenv("ELEVENLABS_API_KEY") or ""
        
        if not self.api_key:
            logger.warning("ElevenLabs API key is empty. Transcription calls will fail.")
            
        self.client = ElevenLabs(api_key=self.api_key)
        if self.api_key:
            logger.info("🎙️ ElevenLabs Speech-to-Text transcriber activated successfully.")

    def transcribe(self, audio_bytes: bytes) -> str:
        """
        Transcribe raw PCM audio bytes (16kHz, mono, int16) to text.
        Returns the transcribed string.
        """
        if not audio_bytes:
            return ""

        # Make sure we have a valid key, otherwise reload from settings
        if not self.api_key:
            self.api_key = settings.elevenlabs_api_key or os.getenv("ELEVENLABS_API_KEY") or ""
            self.client = ElevenLabs(api_key=self.api_key)

        try:
            # Convert raw PCM bytes to WAV format in memory (needed for ElevenLabs audio file input)
            wav_io = io.BytesIO()
            with wave.open(wav_io, 'wb') as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2) # 16-bit
                wav_file.setframerate(16000)
                wav_file.writeframes(audio_bytes)
            
            wav_io.seek(0)
            wav_io.name = "audio.wav" # name attribute is required by the HTTP file uploader

            # Send to ElevenLabs Speech to Text API (explicitly pass language_code="eng" to minimize latency)
            result = self.client.speech_to_text.convert(
                file=wav_io,
                model_id="scribe_v2",
                language_code="eng"
            )
            
            text = result.text.strip()
            logger.debug(f"ElevenLabs STT Transcribed: '{text}'")
            return text

        except Exception as e:
            err_str = str(e).lower()
            is_auth_error = any(kw in err_str for kw in ("401", "unauthorized", "api key", "credential", "invalid"))
            if not is_auth_error:
                logger.error(f"ElevenLabs STT error: {e}")
            raise
