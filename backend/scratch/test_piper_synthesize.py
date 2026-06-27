import sys
from pathlib import Path

# Add backend and workspace root directories to path
_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.append(str(_ROOT))
_BACKEND = _ROOT / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.append(str(_BACKEND))

from app.config import settings
from voice.tts.piper_synthesizer import PiperSynthesizer

def test():
    try:
        synth = PiperSynthesizer()
        print("Model configured:", synth.is_configured())
        print("Model path:", synth.models_dir / f"{synth.voice}.onnx")
        print("Running synthesize...")
        import asyncio
        audio_bytes = asyncio.run(synth.synthesize("System initialized and ready."))
        print(f"Success! Generated {len(audio_bytes)} bytes.")
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test()
