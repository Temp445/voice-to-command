"""Commands router — Execute and retrieve command history."""

import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, delete
from loguru import logger

from app.database import get_db
from app.models import CommandHistory
from app.schemas import ExecuteCommandRequest, CommandResultResponse
from app.services.command_service import command_service
from app.websocket.manager import ws_manager

router = APIRouter()


from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks

@router.post("/execute", response_model=CommandResultResponse)
async def execute_command(request: Request, body: ExecuteCommandRequest, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
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

    entry = CommandHistory(
        id=body.id or str(uuid.uuid4()),
        user_id="00000000-0000-0000-0000-000000000001",  # TODO: real user from JWT
        raw_text=body.text,
        intent=result.get("intent"),
        parameters=result.get("parameters"),
        status=result.get("status", "failed"),
        result=result.get("result"),
        source=body.source,
        executed_at=datetime.now(timezone.utc),
        duration_ms=result.get("duration_ms"),
    )
    db.add(entry)
    await db.flush()

    # Broadcast real-time event to UI
    await ws_manager.broadcast("command_executed", {
        "id": entry.id,
        "raw_text": body.text,
        "intent": entry.intent,
        "status": entry.status,
        "result": entry.result,
        "source": body.source,
        "routed_by_llm": result.get("routed_by_llm", False)
    })



    # Speak the response using the TTS system (if triggered via text/console)
    if pipeline:
        from voice.pipeline import PipelineState
        if body.source == "text" and result.get("status") == "success" and result.get("result"):
            try:
                # Run the speaking in background so we return the HTTP response immediately
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

    return entry


@router.get("/history", response_model=list[CommandResultResponse])
async def get_history(limit: int = 50, db: AsyncSession = Depends(get_db)):
    """Return recent command history."""
    result = await db.execute(
        select(CommandHistory)
        .order_by(desc(CommandHistory.executed_at))
        .limit(limit)
    )
    return result.scalars().all()


@router.delete("/history/{history_id}")
async def delete_history_item(history_id: str, db: AsyncSession = Depends(get_db)):
    """Delete a single command history entry."""
    result = await db.execute(delete(CommandHistory).where(CommandHistory.id == history_id))
    await db.commit()
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="History entry not found")
    return {"status": "success", "message": "Deleted successfully"}


@router.delete("/history")
async def clear_history(db: AsyncSession = Depends(get_db)):
    """Clear all command history."""
    await db.execute(delete(CommandHistory))
    await db.commit()
    return {"status": "success", "message": "All history cleared"}


@router.get("/intents")
async def list_intents():
    """Return all registered command intents."""
    return command_service.list_intents()
