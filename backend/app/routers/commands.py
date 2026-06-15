"""Commands router — Execute and retrieve command history via Supabase client."""

import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from loguru import logger

from app.schemas import ExecuteCommandRequest, CommandResultResponse
from app.services.command_service import command_service
from app.core.supabase_client import supabase_admin, sb_run
from app.websocket.manager import ws_manager
from app.routers.settings_router import get_current_user_id

router = APIRouter()


@router.post("/execute", response_model=CommandResultResponse)
async def execute_command(
    request: Request,
    body: ExecuteCommandRequest,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(get_current_user_id),
):
    """Parse and execute a text or voice command."""
    logger.info(f"Executing command [{body.source}]: '{body.text}'")

    pipeline = getattr(request.app.state, "pipeline", None)
    if pipeline:
        from voice.pipeline import PipelineState
        pipeline._set_state(PipelineState.PROCESSING)

    if body.source == "text":
        logger.info(f"Broadcasting text transcript to overlay: {body.text}")
        await ws_manager.broadcast("transcript", {"text": body.text, "is_final": True})

    result = await command_service.parse_and_execute(body.text)
    
    # Intercept and rewrite using LLM for natural language (if enabled)
    from app.services.llm.llm_service import llm_service
    if llm_service.is_ready and result.get("status") == "success" and result.get("result"):
        raw_res = result.get("result")
        natural_res = await llm_service.rewrite_for_speech(raw_res, body.text)
        result["result"] = natural_res

    now = datetime.now(timezone.utc)
    entry_id = body.id or str(uuid.uuid4())
    row = {
        "id": entry_id,
        "user_id": user_id,
        "raw_text": body.text,
        "intent": result.get("intent"),
        "parameters": result.get("parameters"),
        "status": result.get("status", "failed"),
        "result": result.get("result"),
        "source": body.source,
        "executed_at": now.isoformat(),
        "duration_ms": result.get("duration_ms"),
    }

    await sb_run(lambda: supabase_admin.table("command_history").insert(row).execute())

    # Broadcast real-time event to UI
    await ws_manager.broadcast("command_executed", {
        "id": entry_id,
        "raw_text": body.text,
        "intent": result.get("intent"),
        "status": result.get("status", "failed"),
        "result": result.get("result"),
        "source": body.source,
        "routed_by_llm": result.get("routed_by_llm", False),
    })

    # Speak the response using TTS (if triggered via text/console)
    if pipeline:
        from voice.pipeline import PipelineState
        if body.source == "text" and result.get("status") == "success" and result.get("result"):
            try:
                import asyncio
                async def _speak_and_reset():
                    await pipeline._speak(result.get("result"))
                    pipeline._set_state(PipelineState.IDLE)
                asyncio.create_task(_speak_and_reset())
            except Exception as e:
                logger.warning(f"Failed to play TTS for text command: {e}")
                pipeline._set_state(PipelineState.IDLE)
        else:
            pipeline._set_state(PipelineState.IDLE)

    # Return the row as a CommandResultResponse
    return CommandResultResponse(
        id=entry_id,
        raw_text=body.text,
        intent=result.get("intent"),
        parameters=result.get("parameters"),
        status=result.get("status", "failed"),
        result=result.get("result"),
        duration_ms=result.get("duration_ms"),
        executed_at=now,
    )


@router.get("/history", response_model=list[CommandResultResponse])
async def get_history(limit: int = 50, user_id: str = Depends(get_current_user_id)):
    """Return recent command history."""
    res = await sb_run(
        lambda: supabase_admin
        .table("command_history")
        .select("*")
        .eq("user_id", user_id)
        .order("executed_at", desc=True)
        .limit(limit)
        .execute()
    )
    rows = res.data or []
    return [
        CommandResultResponse(
            id=r["id"],
            raw_text=r["raw_text"],
            intent=r.get("intent"),
            parameters=r.get("parameters"),
            status=r.get("status", "failed"),
            result=r.get("result"),
            duration_ms=r.get("duration_ms"),
            executed_at=datetime.fromisoformat(r["executed_at"]) if isinstance(r["executed_at"], str) else r["executed_at"],
        )
        for r in rows
    ]


@router.delete("/history/{history_id}")
async def delete_history_item(history_id: str, user_id: str = Depends(get_current_user_id)):
    """Delete a single command history entry."""
    res = await sb_run(
        lambda: supabase_admin
        .table("command_history")
        .delete()
        .eq("id", history_id)
        .eq("user_id", user_id)
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=404, detail="History entry not found")
    return {"status": "success", "message": "Deleted successfully"}


@router.delete("/history")
async def clear_history(user_id: str = Depends(get_current_user_id)):
    """Clear all command history for this user."""
    await sb_run(
        lambda: supabase_admin
        .table("command_history")
        .delete()
        .eq("user_id", user_id)
        .execute()
    )
    return {"status": "success", "message": "All history cleared"}


@router.get("/intents")
async def list_intents():
    """Return all registered command intents."""
    return command_service.list_intents()
