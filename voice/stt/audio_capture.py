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

    def __init__(self):
        from app.config import settings
        # Level 2: balanced — catches real speech without over-filtering marginal frames.
        # Level 3 is too aggressive and causes legitimate speech frames to be dropped,
        # leading to garbled or truncated audio sent to Whisper.
        noise_cancelling = getattr(settings, 'stt_noise_cancellation', True)
        vad_aggressiveness = 2
        
        self._vad = webrtcvad.Vad(vad_aggressiveness)
        self._audio = pyaudio.PyAudio()
        self._queue: queue.Queue[bytes] = queue.Queue()
        self._running = False
        self._thread: threading.Thread | None = None
        self._noise_cancelling = noise_cancelling
        
        # NOTE: pyrnnoise is disabled. Its dependency chain (pyrnnoise → audiolab → av.option)
        # is permanently broken: av.option was removed in PyAV 14+, and audiolab also relies
        # on Codec.canonical_name which doesn't exist in older PyAV versions.
        # Noise cancellation is skipped; WebRTC VAD still filters non-speech frames adequately.
        self._denoiser = None
        self._force_stop_recording = False

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
        from voice.remote_mic import subscribe, unsubscribe
        remote_q = subscribe()
        import queue
        import time
        from collections import deque

        # Buffer the last ~90ms of audio BEFORE speech is detected.
        # This prevents the VAD from cutting off the very first consonant/vowel of a word.
        # Pre-roll: 3 chunks × 30ms = 90ms — enough to catch plosive onset (/k/, /p/, /t/)
        # without prepending 300ms of ambient noise to every command.
        # The original maxlen=10 (300ms) caused Whisper to receive 300ms of room hum
        # BEFORE the word, making /k/ in "crm" sound like fricative /s/ → "serum".
        pre_roll_buffer = deque(maxlen=3)
        was_speech = False

        try:
            while self._running:
                # Drain the queue to get all available chunks
                raw_bytes = bytearray()
                try:
                    # Block for at least one chunk to avoid busy looping
                    first_chunk = remote_q.get(timeout=0.1)
                    if first_chunk:
                        raw_bytes.extend(first_chunk)
                    
                    # Drain all remaining chunks in the queue
                    while not remote_q.empty():
                        nxt = remote_q.get_nowait()
                        if nxt:
                            raw_bytes.extend(nxt)
                except queue.Empty:
                    if not raw_bytes:
                        continue
                        
                raw = bytes(raw_bytes)
                if not raw:
                    continue

                if len(raw) % 2 != 0:
                    raw = raw[:-(len(raw) % 2)]
                
                # Apply pyrnnoise if enabled
                if self._noise_cancelling and self._denoiser:
                    try:
                        # Convert to numpy array for pyrnnoise
                        chunk_np = np.frombuffer(raw, dtype=np.int16)
                        
                        denoised_frames = []
                        # denoise_chunk yields (speech_prob, denoised_frame)
                        for _, frame in self._denoiser.denoise_chunk(chunk_np):
                            denoised_frames.append(np.ravel(frame))
                            
                        if denoised_frames:
                            raw = np.concatenate(denoised_frames).astype(np.int16).tobytes()
                    except Exception as e:
                        # Fallback to original raw audio if it fails
                        logger.error(f"RNNoise processing error: {e}")
                
                try:
                    # webrtcvad strictly requires 10, 20, or 30ms frames (960 bytes for 30ms at 16kHz)
                    frame_len = 960
                    is_speech = False
                    for i in range(0, len(raw), frame_len):
                        frame = raw[i:i+frame_len]
                        if len(frame) == frame_len:
                            if self._vad.is_speech(frame, SAMPLE_RATE):
                                is_speech = True
                                break
                except Exception:
                    is_speech = False
                    
                if is_speech:
                    # If this is the start of a new speech segment, dump the pre-roll buffer first
                    if not was_speech:
                        while pre_roll_buffer:
                            self._queue.put(pre_roll_buffer.popleft())
                    self._queue.put(raw)
                    was_speech = True
                else:
                    # Save silent chunk to pre-roll
                    pre_roll_buffer.append(raw)
                    was_speech = False
                    
        except Exception as e:
            logger.error(f"Audio capture loop error: {e}")
        finally:
            unsubscribe(remote_q)

    def stop_recording_early(self) -> None:
        self._force_stop_recording = True

    def get_speech_segment(self, silence_chunks: int = 6, timeout: float = 10.0) -> bytes:
        """
        Collect speech until `silence_chunks` consecutive silent frames (each ~100ms).
        Default 6 chunks = ~0.6s of trailing silence — fast response for short commands
        (e.g. "sign in", "open CRM") while still covering brief mid-sentence pauses.
        Returns concatenated audio bytes.
        """
        import time
        frames: list[bytes] = []
        silent = 0
        deadline = time.time() + timeout
        self._force_stop_recording = False

        while time.time() < deadline and not self._force_stop_recording:
            try:
                chunk = self._queue.get(timeout=0.1)
                frames.append(chunk)
                silent = 0
            except queue.Empty:
                silent += 1
                if frames and silent >= silence_chunks:
                    break
                elif not frames and silent >= 20:  # Auto-stop after 2s of complete silence at start
                    break

        return b"".join(frames)

    def stream_speech_segment(self, silence_chunks: int = 6, timeout: float = 10.0, yield_interval_chunks: int = 15, max_initial_silence_chunks: int = 20):
        """
        Generator that yields (audio_bytes, is_final) periodically as speech is collected.
        yield_interval_chunks of 15 ~ 450ms between partial yields.
        silence_chunks of 6 = ~0.6s trailing silence — fast end-of-speech for short commands.
        """
        import time
        frames: list[bytes] = []
        silent = 0
        deadline = time.time() + timeout
        self._force_stop_recording = False
        chunks_since_last_yield = 0

        while time.time() < deadline and not self._force_stop_recording:
            try:
                chunk = self._queue.get(timeout=0.1)
                frames.append(chunk)
                silent = 0
                chunks_since_last_yield += 1
                
                # Yield partial audio periodically
                if chunks_since_last_yield >= yield_interval_chunks:
                    yield (b"".join(frames), False)
                    chunks_since_last_yield = 0
                    
            except queue.Empty:
                silent += 1
                if frames and silent >= silence_chunks:
                    break
                elif not frames and silent >= max_initial_silence_chunks:
                    break

        yield (b"".join(frames), True)

    def clear(self) -> None:
        while not self._queue.empty():
            self._queue.get_nowait()
