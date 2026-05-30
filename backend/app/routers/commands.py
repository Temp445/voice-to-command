"""Commands router — Execute and retrieve command history."""

import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from loguru import logger

from app.database import get_db
from app.models import CommandHistory
from app.schemas import ExecuteCommandRequest, CommandResultResponse
from app.services.command_service import command_service
from app.websocket.manager import ws_manager

router = APIRouter()


@router.post("/execute", response_model=CommandResultResponse)
async def execute_command(body: ExecuteCommandRequest, db: AsyncSession = Depends(get_db)):
    """Parse and execute a text or voice command."""
    logger.info(f"Executing command [{body.source}]: '{body.text}'")

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
        "source": entry.source,
    })

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


@router.get("/intents")
async def list_intents():
    """Return all registered command intents."""
    return command_service.list_intents()
