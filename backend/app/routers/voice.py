"""Voice router — TTS synthesis, voice pipeline status."""
from loguru import logger


from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
import io

from app.schemas import TTSRequest, VoiceStatusResponse
from app.websocket.manager import ws_manager

router = APIRouter()

# Shared pipeline state (updated by background service)
_pipeline_state = {
    "wake_word_active": False,
    "listening": False,
    "pipeline_state": "idle",
}


@router.get("/status", response_model=VoiceStatusResponse)
async def get_voice_status():
    from app.config import settings
    return VoiceStatusResponse(
        wake_word_active=_pipeline_state["wake_word_active"],
        listening=_pipeline_state["listening"],
        tts_provider=settings.tts_provider,
        whisper_model=settings.whisper_model,
        pipeline_state=_pipeline_state["pipeline_state"],
    )


@router.post("/synthesize")
async def synthesize_speech(body: TTSRequest):
    """Synthesize text to speech and return audio bytes."""
    from voice.tts.provider_factory import get_tts_provider
    provider = await get_tts_provider()
    try:
        audio_bytes = await provider.synthesize(body.text)
        
        is_gtts = provider.__class__.__name__ == "GTTSSynthesizer"
        media_type = "audio/mpeg" if is_gtts else "audio/wav"
        ext = "mp3" if is_gtts else "wav"
        
        return StreamingResponse(
            io.BytesIO(audio_bytes),
            media_type=media_type,
            headers={"Content-Disposition": f"inline; filename=speech.{ext}"},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTS error: {e}")

@router.post("/test-tts")
async def test_tts(body: TTSRequest):
    """Test specific TTS configurations before saving them."""
    if body.provider == "piper":
        from voice.tts.piper_synthesizer import PiperSynthesizer
        provider = PiperSynthesizer()
        if body.piper_voice:
            provider.voice = body.piper_voice
    elif body.provider == "gtts":
        from voice.tts.gtts_synthesizer import GTTSSynthesizer
        provider = GTTSSynthesizer()
    else:
        from voice.tts.provider_factory import get_tts_provider
        provider = await get_tts_provider()
        
    try:
        audio_bytes = await provider.synthesize(body.text)
        
        is_gtts = provider.__class__.__name__ == "GTTSSynthesizer"
        media_type = "audio/mpeg" if is_gtts else "audio/wav"
        ext = "mp3" if is_gtts else "wav"
        
        return StreamingResponse(
            io.BytesIO(audio_bytes),
            media_type=media_type,
            headers={"Content-Disposition": f"inline; filename=test_speech.{ext}"},
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTS error: {e}")

@router.post("/activate")
async def activate_listening(request: Request):
    """Manually trigger listening mode (skip wake word)."""
    _pipeline_state["listening"] = True
    _pipeline_state["pipeline_state"] = "listening"
    await ws_manager.broadcast("pipeline_state", {"state": "listening"})
    if hasattr(request.app.state, "pipeline"):
        request.app.state.pipeline.trigger_listening()
    return {"status": "listening"}


@router.post("/deactivate")
async def deactivate_listening(request: Request):
    _pipeline_state["listening"] = False
    _pipeline_state["pipeline_state"] = "idle"
    await ws_manager.broadcast("pipeline_state", {"state": "idle"})
    if hasattr(request.app.state, "pipeline"):
        request.app.state.pipeline.deactivate()
    return {"status": "idle"}


@router.websocket("/ws-test-stt")
async def websocket_test_stt(websocket: WebSocket):
    await websocket.accept()
    from voice.stt.provider_factory import get_stt_provider
    import asyncio
    import json
    import webrtcvad
    import time
    
    stt = get_stt_provider()
    vad = webrtcvad.Vad(3)
    
    raw_in_buffer = b""
    speech_buffer = b""
    silence_chunks = 0
    MAX_SILENCE_CHUNKS = 15  # ~450ms of silence ends the utterance
    MAX_BUFFER_SIZE = 160000 # 10 seconds max duration to prevent CPU hang
    
    async def transcribe_loop():
        nonlocal speech_buffer, silence_chunks
        last_transcribe_time = time.time()
        
        while True:
            await asyncio.sleep(0.4)
            buf_copy = speech_buffer
            
            # Only transcribe on final chunk to prevent massive CPU backlog and 58s delays
            is_max_length = len(buf_copy) >= MAX_BUFFER_SIZE
            is_final = silence_chunks >= MAX_SILENCE_CHUNKS or is_max_length
            if len(buf_copy) >= 3200 and is_final:
                try:
                    loop = asyncio.get_running_loop()
                    start_t = time.time()
                    text = await loop.run_in_executor(None, stt.transcribe, buf_copy)
                    duration_ms = int((time.time() - start_t) * 1000)
                    
                    if text.strip():
                        await websocket.send_json({"text": text, "is_final": is_final, "duration_ms": duration_ms})
                        
                    if is_final:
                        speech_buffer = b""
                        silence_chunks = 0
                        
                    last_transcribe_time = time.time()
                except Exception as e:
                    logger.error(f"[{__name__}] {type(e).__name__}: {e}")
                    pass

    transcribe_task = asyncio.create_task(transcribe_loop())
    
    try:
        while True:
            message = await websocket.receive()
            if "bytes" in message:
                raw_in_buffer += message["bytes"]
                
                # Process 960-byte chunks (30ms at 16kHz, 16-bit) for VAD
                while len(raw_in_buffer) >= 960:
                    chunk = raw_in_buffer[:960]
                    raw_in_buffer = raw_in_buffer[960:]
                    
                    is_speech = False
                    try:
                        is_speech = vad.is_speech(chunk, 16000)
                    except Exception as e:
                        logger.error(f"[{__name__}] {type(e).__name__}: {e}")
                        pass
                        
                    if is_speech:
                        speech_buffer += chunk
                        silence_chunks = 0
                    else:
                        silence_chunks += 1
                        if len(speech_buffer) > 0:
                            speech_buffer += chunk
                            
            elif "text" in message:
                try:
                    data = json.loads(message["text"])
                    if data.get("type") == "stop":
                        break
                except Exception as e:
                    logger.error(f"[{__name__}] {type(e).__name__}: {e}")
                    pass
    except WebSocketDisconnect:
        pass
    finally:
        transcribe_task.cancel()
        if len(speech_buffer) >= 3200:
            try:
                loop = asyncio.get_running_loop()
                start_t = time.time()
                text = await loop.run_in_executor(None, stt.transcribe, speech_buffer)
                duration_ms = int((time.time() - start_t) * 1000)
                await websocket.send_json({"text": text, "is_final": True, "duration_ms": duration_ms})
            except Exception as e:
                logger.error(f"[{__name__}] {type(e).__name__}: {e}")
                pass
        try:
            await websocket.close()
        except Exception as e:
            logger.error(f"[{__name__}] {type(e).__name__}: {e}")
            pass
