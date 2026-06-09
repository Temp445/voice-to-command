import sys
import os
import asyncio
import wave
import io
import time

# Add backend and workspace root to path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
workspace_dir = os.path.abspath(os.path.join(backend_dir, '..'))
sys.path.insert(0, backend_dir)

from voice.tts.piper_synthesizer import PiperSynthesizer
from app.config import settings

async def generate_fake_audio():
    print("Generating fake audio file for browser test...")
    tts = PiperSynthesizer()
    tts.voice = settings.piper_voice
    
    text = "Open the CRM dashboard."
    print(f"Synthesizing command: '{text}'")
    wav_bytes = await tts.synthesize(text)
    
    # Playwright requires the fake audio to be exactly 44.1kHz or 48kHz for reliable playback on some systems,
    # but let's try writing the 16kHz generated WAV directly.
    wav_path = os.path.join(backend_dir, "scratch", "fake_mic.wav")
    with open(wav_path, "wb") as f:
        f.write(wav_bytes)
        
    print(f"Saved to {wav_path}")

if __name__ == "__main__":
    asyncio.run(generate_fake_audio())
