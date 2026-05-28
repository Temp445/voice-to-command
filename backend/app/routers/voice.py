"""Voice router — TTS synthesis, voice pipeline status."""

from fastapi import APIRouter, HTTPException
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
        return StreamingResponse(
            io.BytesIO(audio_bytes),
            media_type="audio/wav",
            headers={"Content-Disposition": "inline; filename=speech.wav"},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTS error: {e}")


@router.post("/activate")
async def activate_listening():
    """Manually trigger listening mode (skip wake word)."""
    _pipeline_state["listening"] = True
    _pipeline_state["pipeline_state"] = "listening"
    await ws_manager.broadcast("pipeline_state", {"state": "listening"})
    return {"status": "listening"}


@router.post("/deactivate")
async def deactivate_listening():
    _pipeline_state["listening"] = False
    _pipeline_state["pipeline_state"] = "idle"
    await ws_manager.broadcast("pipeline_state", {"state": "idle"})
    return {"status": "idle"}
