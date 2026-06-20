import pyaudio
import numpy as np

p = pyaudio.PyAudio()
default_info = p.get_default_input_device_info()
idx = default_info['index']
native_rate = int(default_info['defaultSampleRate'])

print(f"Default Device: {default_info['name']}")
print(f"Native Sample Rate: {native_rate} Hz")

try:
    stream = p.open(format=pyaudio.paInt16, channels=1, rate=native_rate, input=True, input_device_index=idx, frames_per_buffer=int(native_rate * 0.1))
    
    print("Reading 3 chunks...")
    for _ in range(3):
        raw = stream.read(int(native_rate * 0.1), exception_on_overflow=False)
        vol = np.abs(np.frombuffer(raw, dtype=np.int16)).mean()
        print(f"Chunk volume: {vol:.1f}")
        
    stream.stop_stream()
    stream.close()
except Exception as e:
    print(f"Error: {e}")

p.terminate()
