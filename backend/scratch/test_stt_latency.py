import sys
import os
import time
import asyncio
import numpy as np
import wave
import io

# Add backend and workspace root to path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
workspace_dir = os.path.abspath(os.path.join(backend_dir, '..'))
sys.path.insert(0, backend_dir)
sys.path.insert(0, workspace_dir)

from voice.stt.provider_factory import get_stt_provider
from voice.tts.piper_synthesizer import PiperSynthesizer
from app.config import settings

async def main():
    print("Initializing providers...", flush=True)
    stt = get_stt_provider()
    tts = PiperSynthesizer()
    tts.voice = settings.piper_voice
    
    print("Pre-warming STT model...", flush=True)
    silent_audio = np.zeros(16000, dtype=np.int16).tobytes()
    stt.transcribe(silent_audio)
    
    commands = [
        "Open the CRM dashboard.",
        "Play the latest video on youtube.",
        "Scroll down the page.",
        "Turn up the volume.",
        "Hey ACE, can you click the submit button for me?"
    ]
    
    for i, text in enumerate(commands, 1):
        print(f"\n--- Voice Command Test {i} ---", flush=True)
        print(f"Target Command: {text}", flush=True)
        
        # Synthesize command
        wav_bytes = await tts.synthesize(text)
        
        # Extract PCM
        with wave.open(io.BytesIO(wav_bytes), 'rb') as w:
            raw_pcm_bytes = w.readframes(w.getnframes())
            duration_audio = w.getnframes() / w.getframerate()
        
        print(f"Transcribing {duration_audio:.2f}s of audio...", flush=True)
        start_t = time.time()
        result = stt.transcribe(raw_pcm_bytes)
        duration = time.time() - start_t
        
        print(f"Transcription Result: '{result}'", flush=True)
        print(f"Latency: {duration:.3f} seconds", flush=True)
        
        # Simple accuracy check
        target_lower = text.lower().replace(".", "").replace(",", "").replace("?", "").strip()
        result_lower = result.lower().replace(".", "").replace(",", "").replace("?", "").strip()
        accuracy = "100%" if target_lower == result_lower else "Failed/Partial"
        print(f"Accuracy: {accuracy}", flush=True)

if __name__ == "__main__":
    asyncio.run(main())
