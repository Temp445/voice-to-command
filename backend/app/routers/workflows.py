"""Workflows router — CRUD for automation workflows."""

import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import Workflow
from app.schemas import WorkflowCreate, WorkflowResponse

router = APIRouter()
_DEFAULT_USER_ID = "00000000-0000-0000-0000-000000000001"


@router.get("", response_model=list[WorkflowResponse])
async def list_workflows(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Workflow).where(Workflow.user_id == _DEFAULT_USER_ID))
    return result.scalars().all()


@router.post("", response_model=WorkflowResponse, status_code=201)
async def create_workflow(body: WorkflowCreate, db: AsyncSession = Depends(get_db)):
    wf = Workflow(
        id=str(uuid.uuid4()),
        user_id=_DEFAULT_USER_ID,
        name=body.name,
        description=body.description,
        trigger_phrase=body.trigger_phrase,
        steps=[s.model_dump() for s in body.steps],
    )
    db.add(wf)
    await db.flush()
    return wf


@router.get("/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(workflow_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Workflow).where(Workflow.id == workflow_id))
    wf = result.scalar_one_or_none()
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return wf


@router.delete("/{workflow_id}", status_code=204)
async def delete_workflow(workflow_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Workflow).where(Workflow.id == workflow_id))
    wf = result.scalar_one_or_none()
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    await db.delete(wf)


@router.post("/{workflow_id}/run")
async def run_workflow(workflow_id: str, db: AsyncSession = Depends(get_db)):
    """Execute a workflow's steps sequentially."""
    from app.services.command_service import command_service
    import asyncio

    result = await db.execute(select(Workflow).where(Workflow.id == workflow_id))
    wf = result.scalar_one_or_none()
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")

    results = []
    for step in wf.steps:
        action = step.get("action", "")
        if step.get("delay_ms", 0):
            await asyncio.sleep(step["delay_ms"] / 1000)
        r = await command_service.parse_and_execute(action)
        results.append({"action": action, "result": r})

    wf.run_count += 1
    return {"workflow_id": workflow_id, "steps_run": len(results), "results": results}
