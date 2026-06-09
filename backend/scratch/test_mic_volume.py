import pyaudio
import numpy as np

def test_mic_volume():
    p = pyaudio.PyAudio()
    if p.get_device_count() == 0:
        print("No audio devices.")
        return
        
    try:
        stream = p.open(format=pyaudio.paInt16, channels=1, rate=16000, input=True, frames_per_buffer=1280)
        print("Listening to default microphone... (Speak now!)")
        
        for _ in range(30): # Listen for ~3 seconds
            try:
                raw = stream.read(1280, exception_on_overflow=False)
                audio_np = np.frombuffer(raw, dtype=np.int16)
                vol = np.abs(audio_np).mean()
                print(f"Volume: {vol:.2f}")
            except Exception as e:
                print(f"Error reading: {e}")
                
        stream.stop_stream()
        stream.close()
    except Exception as e:
        print(f"Could not open stream: {e}")
    finally:
        p.terminate()

if __name__ == "__main__":
    test_mic_volume()
