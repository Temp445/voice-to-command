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
    p = pyaudio.PyAudio()
    if p.get_device_count() == 0:
        logger.warning("No local audio devices found.")
        return
        
    try:
        stream = p.open(format=pyaudio.paInt16, channels=1, rate=16000, input=True, frames_per_buffer=1280)
        logger.info("🎤 Local microphone broadcast started.")
        while _local_mic_running:
            raw = stream.read(1280, exception_on_overflow=False)
            put_chunk(raw)
    except Exception as e:
        logger.error(f"Local mic broadcast error: {e}")
    finally:
        if 'stream' in locals() and stream:
            stream.stop_stream()
            stream.close()
        p.terminate()

def start_local_mic():
    global _local_mic_running
    if _local_mic_running:
        return
    _local_mic_running = True
    threading.Thread(target=_local_mic_loop, daemon=True).start()

def stop_local_mic():
    global _local_mic_running
    _local_mic_running = False
