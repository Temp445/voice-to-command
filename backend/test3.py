import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from voice.tts.piper_synthesizer import PiperSynthesizer
print(hasattr(PiperSynthesizer()._piper_voice, "synthesize_stream_raw"))
