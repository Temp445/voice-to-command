"""Workflows router — CRUD for automation workflows via Supabase client."""

import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException

from app.schemas import WorkflowCreate, WorkflowResponse, WorkflowUpdate
from app.core.supabase_client import supabase_admin, sb_run
from app.routers.settings_router import get_current_user_id

router = APIRouter()


def _row_to_response(r: dict) -> WorkflowResponse:
    def _parse_dt(val):
        if not val:
            return datetime.now(timezone.utc)
        if isinstance(val, str):
            return datetime.fromisoformat(val)
        return val

    return WorkflowResponse(
        id=r["id"],
        name=r["name"],
        description=r.get("description"),
        trigger_phrase=r.get("trigger_phrase"),
        steps=r.get("steps", []),
        is_active=r.get("is_active", True),
        run_count=r.get("run_count", 0),
        created_at=_parse_dt(r.get("created_at")),
        updated_at=_parse_dt(r.get("updated_at")),
    )


@router.get("", response_model=list[WorkflowResponse])
async def list_workflows(user_id: str = Depends(get_current_user_id)):
    res = await sb_run(
        lambda: supabase_admin.table("workflows").select("*").eq("user_id", user_id).execute()
    )
    return [_row_to_response(r) for r in (res.data or [])]


@router.post("", response_model=WorkflowResponse, status_code=201)
async def create_workflow(body: WorkflowCreate, user_id: str = Depends(get_current_user_id)):
    now = datetime.now(timezone.utc).isoformat()
    row = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "name": body.name,
        "description": body.description,
        "trigger_phrase": body.trigger_phrase,
        "steps": [s.model_dump() for s in body.steps],
        "is_active": True,
        "run_count": 0,
        "created_at": now,
        "updated_at": now,
    }
    await sb_run(lambda: supabase_admin.table("workflows").insert(row).execute())
    # Refresh the in-memory cache so the new workflow is immediately active
    from app.services.command_service import command_service
    command_service.refresh_in_background()
    return _row_to_response(row)


@router.get("/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(workflow_id: str, user_id: str = Depends(get_current_user_id)):
    res = await sb_run(
        lambda: supabase_admin.table("workflows").select("*").eq("id", workflow_id).execute()
    )
    if not res.data:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return _row_to_response(res.data[0])


@router.patch("/{workflow_id}", response_model=WorkflowResponse)
async def update_workflow(
    workflow_id: str,
    body: WorkflowUpdate,
    user_id: str = Depends(get_current_user_id)
):
    from app.schemas import WorkflowUpdate
    
    update_data = body.model_dump(exclude_unset=True)
    if "steps" in update_data and update_data["steps"] is not None:
        update_data["steps"] = [s.model_dump() if hasattr(s, "model_dump") else s for s in body.steps]
        
    if not update_data:
        # Nothing to update
        return await get_workflow(workflow_id, user_id)
        
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    res = await sb_run(
        lambda: supabase_admin.table("workflows")
        .update(update_data)
        .eq("id", workflow_id)
        .eq("user_id", user_id)
        .execute()
    )
    
    if not res.data:
        raise HTTPException(status_code=404, detail="Workflow not found")
        
    # Refresh the in-memory cache
    from app.services.command_service import command_service
    command_service.refresh_in_background()
    
    return _row_to_response(res.data[0])


@router.delete("/{workflow_id}", status_code=204)
async def delete_workflow(workflow_id: str, user_id: str = Depends(get_current_user_id)):
    res = await sb_run(
        lambda: supabase_admin.table("workflows").delete().eq("id", workflow_id).eq("user_id", user_id).execute()
    )
    if not res.data:
        raise HTTPException(status_code=404, detail="Workflow not found")
    # Refresh the in-memory cache so the deleted workflow no longer triggers
    from app.services.command_service import command_service
    command_service.refresh_in_background()


@router.post("/{workflow_id}/run")
async def run_workflow(workflow_id: str, user_id: str = Depends(get_current_user_id)):
    """Execute a workflow's steps sequentially."""
    from app.services.command_service import command_service
    import asyncio

    res = await sb_run(
        lambda: supabase_admin.table("workflows").select("*").eq("id", workflow_id).execute()
    )
    if not res.data:
        raise HTTPException(status_code=404, detail="Workflow not found")

    wf = res.data[0]
    results = []
    for step in wf.get("steps", []):
        action = step.get("action", "")
        if step.get("delay_ms", 0):
            await asyncio.sleep(step["delay_ms"] / 1000)
        r = await command_service.parse_and_execute(action)
        results.append({"action": action, "result": r})

    # Increment run_count
    new_count = wf.get("run_count", 0) + 1
    await sb_run(
        lambda: supabase_admin.table("workflows")
        .update({"run_count": new_count, "updated_at": datetime.now(timezone.utc).isoformat()})
        .eq("id", workflow_id)
        .execute()
    )

    return {"workflow_id": workflow_id, "steps_run": len(results), "results": results}
