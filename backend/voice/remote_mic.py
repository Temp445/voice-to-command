"""
ACE Voice Controller — Remote Microphone Queue
Handles audio chunks streamed from the web frontend over WebSockets.
"""

import queue
import threading
import time
from loguru import logger

_queues: list[queue.Queue] = []
_local_mic_running = False

def subscribe() -> queue.Queue:
    """Register a new queue for a background thread to consume remote audio."""
    q = queue.Queue(maxsize=100)
    _queues.append(q)
    return q

def unsubscribe(q: queue.Queue) -> None:
    """Remove a queue to prevent memory leaks."""
    if q in _queues:
        _queues.remove(q)

def put_chunk(chunk: bytes) -> None:
    """Broadcast an audio chunk to all subscribed queues."""
    for q in _queues:
        try:
            q.put_nowait(chunk)
        except queue.Full:
            try:
                q.get_nowait() # pop oldest
                q.put_nowait(chunk)
            except queue.Empty:
                pass

def clear_queues() -> None:
    """Empty all remote audio buffers."""
    for q in _queues:
        while not q.empty():
            try:
                q.get_nowait()
            except queue.Empty:
                break

def _local_mic_loop():
    import pyaudio
    import time
    
    while _local_mic_running:
        p = pyaudio.PyAudio()
        stream = None
        try:
            num_devices = p.get_device_count()
            if num_devices == 0:
                logger.warning("No local audio devices found. Retrying in 5 seconds...")
                time.sleep(5)
                continue
                
            try:
                default_device = p.get_default_input_device_info()
                device_index = default_device.get("index")
                device_name = default_device.get("name", "Unknown Device")
            except OSError:
                device_index = None
                device_name = "Fallback Device"
            
            try:
                stream = p.open(format=pyaudio.paInt16, channels=1, rate=16000, input=True, frames_per_buffer=1280, input_device_index=device_index)
            except Exception as first_err:
                logger.debug(f"Failed to open default mic: {first_err}. Searching for alternatives...")
                for i in range(num_devices):
                    try:
                        info = p.get_device_info_by_index(i)
                        if info.get('maxInputChannels', 0) > 0:
                            stream = p.open(format=pyaudio.paInt16, channels=1, rate=16000, input=True, frames_per_buffer=1280, input_device_index=i)
                            device_name = info.get("name", f"Device {i}")
                            break
                    except Exception as e:
                        logger.error(f"[{__name__}] {type(e).__name__}: {e}")
                        continue
                if not stream:
                    raise RuntimeError(f"No working microphone found. Initial error: {first_err}")

            logger.info(f"🎤 Local microphone broadcast started on: '{device_name}'")
            
            while _local_mic_running:
                raw = stream.read(1280, exception_on_overflow=False)
                put_chunk(raw)
                
        except Exception as e:
            logger.warning(f"Local mic broadcast issue: {e}. Retrying in 5 seconds...")
            time.sleep(5)
        finally:
            if stream:
                try:
                    stream.stop_stream()
                    stream.close()
                except Exception as e:
                    logger.error(f"[{__name__}] {type(e).__name__}: {e}")
                    pass
            try:
                p.terminate()
            except Exception as e:
                logger.error(f"[{__name__}] {type(e).__name__}: {e}")
                pass

def start_local_mic():
    global _local_mic_running
    if _local_mic_running:
        return
    _local_mic_running = True
    threading.Thread(target=_local_mic_loop, daemon=True).start()

def stop_local_mic():
    global _local_mic_running
    _local_mic_running = False
