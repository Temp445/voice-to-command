"""
ACE Voice Controller — Deepgram Speech-to-Text Transcriber
Uses the Deepgram listen.v1.media API for fast, high-accuracy cloud-based transcription.
"""

import io
import wave
import os
from loguru import logger
from deepgram import DeepgramClient
from app.config import settings

class DeepgramSTTTranscriber:
    """
    Speech-to-text transcriber using Deepgram listen.v1.media API.
    """

    def __init__(self):
        # Resolve Deepgram API key: priority is in-memory settings (set dynamically), fallback is environment variable
        self.api_key = settings.deepgram_api_key or os.getenv("DEEPGRAM_API_KEY") or ""
        
        if not self.api_key:
            logger.warning("Deepgram API key is empty. Transcription calls will fail.")
            
        self.client = DeepgramClient(api_key=self.api_key)
        if self.api_key:
            logger.info("🎙️ Deepgram Speech-to-Text transcriber activated successfully.")

    def transcribe(self, audio_bytes: bytes) -> str:
        """
        Transcribe raw PCM audio bytes (16kHz, mono, int16) to text.
        Returns the transcribed string.
        """
        if not audio_bytes:
            return ""

        # Make sure we have a valid key, otherwise reload from settings
        if not self.api_key:
            self.api_key = settings.deepgram_api_key or os.getenv("DEEPGRAM_API_KEY") or ""
            self.client = DeepgramClient(api_key=self.api_key)

        try:
            # Convert raw PCM bytes to WAV format in memory (needed for Deepgram audio file input)
            wav_io = io.BytesIO()
            with wave.open(wav_io, 'wb') as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2) # 16-bit
                wav_file.setframerate(16000)
                wav_file.writeframes(audio_bytes)
            
            wav_io.seek(0)
            wav_data = wav_io.read()
            
            # Send to Deepgram Speech to Text API (v7 syntax)
            response = self.client.listen.v1.media.transcribe_file(
                request=wav_data,
                model="nova-3",
                smart_format=True,
                language="en"
            )
            
            # Extract transcript text
            transcript = response.results.channels[0].alternatives[0].transcript
            text = transcript.strip()
            logger.debug(f"Deepgram STT Transcribed: '{text}'")
            return text

        except Exception as e:
            err_str = str(e).lower()
            is_auth_error = any(kw in err_str for kw in ("401", "unauthorized", "api key", "credential", "invalid"))
            if not is_auth_error:
                logger.error(f"Deepgram STT error: {e}")
            raise
