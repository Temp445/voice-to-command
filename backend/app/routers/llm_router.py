"""LLM Router — AI assistant status, provider info, test connection, and chat."""

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.schemas import LLMChatRequest, LLMChatResponse, LLMStatusResponse, LLMProviderInfo
from app.services.llm.llm_service import llm_service, PROVIDER_REGISTRY

router = APIRouter()


@router.get("/providers", response_model=list[LLMProviderInfo])
async def get_providers():
    """Return all supported providers and their available models."""
    return llm_service.get_all_providers()


@router.get("/status", response_model=LLMStatusResponse)
async def get_status():
    """Return current LLM provider status."""
    return LLMStatusResponse(**llm_service.status())


@router.post("/test")
async def test_connection():
    """Send a quick ping to verify the configured provider is reachable."""
    if not llm_service.is_ready:
        err_msg = llm_service.last_error or "LLM provider not configured. Go to Settings → AI Assistant."
        return {"ok": False, "error": err_msg}
    try:
        reply = await llm_service._provider.chat(
            [{"role": "user", "content": "Reply with exactly: OK"}],
            temperature=0.0,
            max_tokens=10,
        )
        return {"ok": True, "provider": llm_service._provider_name, "model": llm_service._model, "reply": reply.strip()}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.post("/chat", response_model=LLMChatResponse)
async def chat(body: LLMChatRequest):
    """Send a message to the LLM and get a full response."""
    if not llm_service.is_ready:
        return LLMChatResponse(
            reply="AI assistant is not configured. Please go to Settings → AI Assistant.",
            provider="none",
            model="none",
        )
    if body.stream:
        # Return a streaming response for real-time token output
        async def token_generator():
            async for token in llm_service.stream_chat(body.message):
                yield token
        return StreamingResponse(token_generator(), media_type="text/plain")

    reply = await llm_service.chat(body.message)
    return LLMChatResponse(reply=reply, provider=llm_service._provider_name, model=llm_service._model)


@router.delete("/history")
async def clear_history():
    """Clear the LLM conversation memory."""
    llm_service.clear_history()
    return {"ok": True, "message": "Conversation history cleared."}
