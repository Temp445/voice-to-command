"""
ACE Voice Controller — Google Speech-to-Text Transcriber
Uses the free Google Web Speech API via the SpeechRecognition library.
"""

import io
import speech_recognition as sr
from loguru import logger
import wave

class GoogleSTTTranscriber:
    """
    Speech-to-text using Google's free Web Speech API.
    Provides highly accurate transcription for general language without requiring a local model.
    """

    def __init__(self):
        self.recognizer = sr.Recognizer()

    def transcribe(self, audio_bytes: bytes) -> str:
        """
        Transcribe raw PCM audio bytes (16kHz, mono, int16) to text.
        Returns the transcribed string.
        """
        if not audio_bytes:
            return ""

        try:
            # Convert raw PCM bytes to WAV format in memory
            wav_io = io.BytesIO()
            with wave.open(wav_io, 'wb') as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2) # 16-bit
                wav_file.setframerate(16000)
                wav_file.writeframes(audio_bytes)
            
            wav_io.seek(0)

            # Use SpeechRecognition to read the WAV data
            with sr.AudioFile(wav_io) as source:
                audio_data = self.recognizer.record(source)

            # Send to Google Web Speech API
            text = self.recognizer.recognize_google(audio_data, language="en-US")
            logger.debug(f"Google STT Transcribed: '{text}'")
            return text

        except sr.UnknownValueError:
            logger.debug("Google STT could not understand audio")
            return ""
        except sr.RequestError as e:
            logger.error(f"Could not request results from Google STT service; {e}")
            return ""
        except Exception as e:
            logger.error(f"Google STT error: {e}")
            return ""
