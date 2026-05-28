"""
ACE Voice Controller — Microphone Audio Capture + VAD
Streams microphone input and detects voice activity using WebRTC VAD.
"""

import queue
import threading
import numpy as np
import pyaudio
import webrtcvad
from loguru import logger
from dataclasses import dataclass


SAMPLE_RATE = 16000       # Whisper requires 16kHz
CHANNELS = 1
CHUNK_DURATION_MS = 30    # VAD frame size: 10, 20, or 30ms
CHUNK_SIZE = int(SAMPLE_RATE * CHUNK_DURATION_MS / 1000)
FORMAT = pyaudio.paInt16


@dataclass
class AudioChunk:
    data: bytes
    is_speech: bool
    timestamp: float


class AudioCapture:
    """
    Continuous microphone capture with WebRTC VAD filtering.
    Pushes speech frames into a thread-safe queue.
    """

    def __init__(self, vad_aggressiveness: int = 2):
        """
        vad_aggressiveness: 0-3 (0=permissive, 3=aggressive noise filtering)
        """
        self._vad = webrtcvad.Vad(vad_aggressiveness)
        self._audio = pyaudio.PyAudio()
        self._queue: queue.Queue[bytes] = queue.Queue()
        self._running = False
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()
        logger.info("🎤 Audio capture started")

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
        logger.info("🎤 Audio capture stopped")

    def _capture_loop(self) -> None:
        stream = self._audio.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=SAMPLE_RATE,
            input=True,
            frames_per_buffer=CHUNK_SIZE,
        )
        try:
            while self._running:
                raw = stream.read(CHUNK_SIZE, exception_on_overflow=False)
                try:
                    is_speech = self._vad.is_speech(raw, SAMPLE_RATE)
                except Exception:
                    is_speech = False
                if is_speech:
                    self._queue.put(raw)
        finally:
            stream.stop_stream()
            stream.close()

    def get_speech_segment(self, silence_chunks: int = 30, timeout: float = 10.0) -> bytes:
        """
        Collect speech until `silence_chunks` consecutive silent frames.
        Returns concatenated audio bytes.
        """
        import time
        frames: list[bytes] = []
        silent = 0
        deadline = time.time() + timeout

        while time.time() < deadline:
            try:
                chunk = self._queue.get(timeout=0.1)
                frames.append(chunk)
                silent = 0
            except queue.Empty:
                silent += 1
                if frames and silent >= silence_chunks:
                    break

        return b"".join(frames)

    def clear(self) -> None:
        while not self._queue.empty():
            self._queue.get_nowait()
