"""Commands router — Execute and retrieve command history via Supabase client."""

import asyncio
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


async def _save_history_bg(entry_id, user_id, body, result, now):
    """Non-blocking background task: persist history + LLM rewrite + WS broadcast."""
    # LLM rewrite (fires after response is already sent to caller)
    from app.services.llm.llm_service import llm_service
    result_text = result.get("result")
    if llm_service.is_ready and result.get("status") == "success" and result_text:
        try:
            result_text = await llm_service.rewrite_for_speech(result_text, body.text)
        except Exception as e:
            logger.warning(f"LLM rewrite failed in background: {e}")

    # Supabase insert (non-blocking — response already sent)
    row = {
        "id": entry_id,
        "user_id": user_id,
        "raw_text": body.text,
        "intent": result.get("intent"),
        "parameters": result.get("parameters"),
        "status": result.get("status", "failed"),
        "result": result_text,
        "source": body.source,
        "executed_at": now.isoformat(),
        "duration_ms": result.get("duration_ms"),
    }
    try:
        await sb_run(lambda: supabase_admin.table("command_history").insert(row).execute())
    except Exception as e:
        logger.warning(f"History insert failed: {e}")

    # WS broadcast fires immediately in execute_command above — skipped here.

    # TTS speak (non-blocking — fires after response returned)
    import asyncio
    from app.main import app as _app  # noqa: circular import is fine here
    pipeline = getattr(_app.state, "pipeline", None)
    if pipeline and body.source == "text" and result.get("status") == "success" and result_text:
        from voice.pipeline import PipelineState
        try:
            await pipeline._speak(result_text)
            pipeline._set_state(PipelineState.IDLE)
        except Exception as e:
            logger.warning(f"TTS speak failed in background: {e}")
            pipeline._set_state(PipelineState.IDLE)


@router.post("/execute", response_model=CommandResultResponse)
async def execute_command(
    request: Request,
    body: ExecuteCommandRequest,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(get_current_user_id),
):
    """Parse and execute a text or voice command. Returns instantly after execution."""
    logger.info(f"Executing command [{body.source}]: '{body.text}'")

    pipeline = getattr(request.app.state, "pipeline", None)
    if pipeline:
        from voice.pipeline import PipelineState
        pipeline._set_state(PipelineState.PROCESSING)

    if body.source == "text":
        await ws_manager.broadcast("transcript", {"text": body.text, "is_final": True})

    # ── Core execution — this is the only thing blocking the response ──────────
    result = await command_service.parse_and_execute(body.text)

    now = datetime.now(timezone.utc)
    entry_id = body.id or str(uuid.uuid4())

    # ── Broadcast to overlay IMMEDIATELY after execution, before browser opens ─
    # Previously the overlay received command_executed only after navigate() +
    # focus + CDP maximize all completed — causing a 10–25s overlay delay.
    # Now we fire it here so the overlay pops up instantly on command success,
    # regardless of how long the browser navigation takes afterward.
    asyncio.create_task(ws_manager.broadcast("command_executed", {
        "id": entry_id,
        "raw_text": body.text,
        "intent": result.get("intent"),
        "status": result.get("status", "failed"),
        "result": result.get("result"),
        "source": body.source,
        "routed_by_llm": result.get("routed_by_llm", False),
    }))

    # ── Everything else fires in background — response returns immediately ─────
    background_tasks.add_task(
        _save_history_bg, entry_id, user_id, body, result, now
    )

    if pipeline and body.source != "text":
        from voice.pipeline import PipelineState
        pipeline._set_state(PipelineState.IDLE)

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