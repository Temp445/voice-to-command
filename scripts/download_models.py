"""Download Piper TTS voice models."""

import sys
import urllib.request
from pathlib import Path

MODELS_DIR = Path(__file__).parent.parent / "voice" / "tts" / "models"

VOICES = {
    "en_US-lessac-medium": {
        "onnx": "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx",
        "json": "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json",
    },
    "en_US-ryan-medium": {
        "onnx": "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/ryan/medium/en_US-ryan-medium.onnx",
        "json": "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/ryan/medium/en_US-ryan-medium.onnx.json",
    },
    "en_US-hfc_female-medium": {
        "onnx": "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/hfc_female/medium/en_US-hfc_female-medium.onnx",
        "json": "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/hfc_female/medium/en_US-hfc_female-medium.onnx.json",
    }
}


def download(name: str, url: str, dest: Path) -> None:
    if dest.exists():
        print(f"  ✅ Already downloaded: {dest.name}")
        return
    print(f"  ⬇️  Downloading {dest.name}...")
    try:
        urllib.request.urlretrieve(url, dest, reporthook=progress)
        print(f"\n  ✅ Saved: {dest}")
    except Exception as e:
        print(f"\n  ❌ Failed to download {name}: {e}")


def progress(count, block_size, total_size):
    if total_size > 0:
        pct = min(count * block_size * 100 // total_size, 100)
        sys.stdout.write(f"\r     {pct}%")
        sys.stdout.flush()


def main():
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    print(f"\n📦 Downloading Piper TTS models to: {MODELS_DIR}\n")
    for voice_name, files in VOICES.items():
        print(f"  Voice: {voice_name}")
        download(f"{voice_name}.onnx", files["onnx"], MODELS_DIR / f"{voice_name}.onnx")
        download(f"{voice_name}.json", files["json"], MODELS_DIR / f"{voice_name}.onnx.json")
    print("\n✅ Voice models ready")


if __name__ == "__main__":
    main()
