import pyaudio
import time

def test_pyaudio():
    p = pyaudio.PyAudio()
    if p.get_device_count() == 0:
        print("No audio devices.")
        return
        
    stream = p.open(format=pyaudio.paInt16, channels=1, rate=16000, input=True, frames_per_buffer=1280)
    print("Stream opened.")
    
    for i in range(10):
        avail = stream.get_read_available()
        print(f"Available frames: {avail}")
        time.sleep(0.1)
        
    stream.stop_stream()
    stream.close()
    p.terminate()

if __name__ == "__main__":
    test_pyaudio()
