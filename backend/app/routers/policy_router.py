"""Policy router — Admin-only controls to read and modify user policies."""

from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger
from pydantic import BaseModel
from typing import Any, Dict

from app.core.supabase_client import supabase_admin, sb_run
from app.routers.settings_router import get_current_user_id

router = APIRouter()

# --- Schemas ---

class PolicyUpdate(BaseModel):
    permissions: Dict[str, Any]
    screen_settings_visible_to_users: bool | None = None

class UserPolicyInfo(BaseModel):
    user_id: str
    email: str
    display_name: str | None
    role: str
    permissions: Dict[str, Any]
    screen_settings_visible_to_users: bool


# --- Admin Dependency ---

async def get_current_admin_user_id(user_id: str = Depends(get_current_user_id)) -> str:
    """Dependency verifying the requester has the 'admin' role."""
    res = await sb_run(lambda: supabase_admin.table("users").select("role").eq("id", user_id).execute())
    if not res.data or res.data[0].get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: Admin privilege required."
        )
    return user_id


# --- Routes ---

@router.get("", response_model=list[UserPolicyInfo])
async def list_policies(admin_id: str = Depends(get_current_admin_user_id)):
    """Retrieve all users and their settings permissions policies."""
    try:
        users_res = await sb_run(lambda: supabase_admin.table("users").select("id, email, display_name, role").execute())
        policies_res = await sb_run(lambda: supabase_admin.table("user_policies").select("user_id, permissions").execute())
        settings_res = await sb_run(lambda: supabase_admin.table("settings").select("user_id, screen_settings_visible_to_users").execute())
        
        policies_map = {p["user_id"]: p["permissions"] for p in policies_res.data}
        settings_map = {s["user_id"]: s.get("screen_settings_visible_to_users", True) for s in settings_res.data}
        
        result = []
        for u in users_res.data:
            uid = u["id"]
            result.append(UserPolicyInfo(
                user_id=uid,
                email=u["email"],
                display_name=u.get("display_name"),
                role=u.get("role") or "user",
                permissions=policies_map.get(uid, {}),
                screen_settings_visible_to_users=settings_map.get(uid, True)
            ))
        return result
    except Exception as e:
        logger.error(f"Failed to list policies: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{user_id}", response_model=Dict[str, Any])
async def update_user_policy(
    user_id: str,
    body: PolicyUpdate,
    admin_id: str = Depends(get_current_admin_user_id)
):
    """Create or update setting policy rules for a specific user."""
    try:
        # Check if user exists
        user_check = await sb_run(lambda: supabase_admin.table("users").select("id").eq("id", user_id).execute())
        if not user_check.data:
            raise HTTPException(status_code=404, detail="User not found")

        # Upsert the policy row
        res = await sb_run(lambda: supabase_admin.table("user_policies").upsert({
            "user_id": user_id,
            "permissions": body.permissions
        }, on_conflict="user_id").execute())
        
        if not res.data:
            raise HTTPException(status_code=500, detail="Failed to update policy row.")
            
        # Update settings table if visibility field is provided (using upsert to handle missing settings rows)
        if body.screen_settings_visible_to_users is not None:
            await sb_run(lambda: supabase_admin.table("settings").upsert({
                "user_id": user_id,
                "screen_settings_visible_to_users": body.screen_settings_visible_to_users
            }, on_conflict="user_id").execute())
            
        logger.info(f"Admin {admin_id} updated policies for user {user_id}")
        return {
            "status": "success",
            "permissions": body.permissions,
            "screen_settings_visible_to_users": body.screen_settings_visible_to_users
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update policy: {e}")
        raise HTTPException(status_code=500, detail=str(e))
