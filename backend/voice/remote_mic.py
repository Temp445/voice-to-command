"""
ACE Voice Controller — Remote Microphone Queue
Handles audio chunks streamed from the web frontend over WebSockets.
"""

import queue

_queues: list[queue.Queue] = []

def subscribe() -> queue.Queue:
    """Register a new queue for a background thread to consume remote audio."""
    q = queue.Queue(maxsize=100)
    _queues.append(q)
    return q

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
