import sys
from pathlib import Path

# Add backend and workspace root directories to path
_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.append(str(_ROOT))
_BACKEND = _ROOT / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.append(str(_BACKEND))

import asyncio
from app.core.supabase_client import supabase_admin, sb_run

async def test():
    try:
        # Fetch first user
        users = await sb_run(lambda: supabase_admin.table("users").select("id").limit(1).execute())
        if not users.data:
            print("No users found in database.")
            return
        
        user_id = users.data[0]["id"]
        print(f"Testing with user_id: {user_id}")
        
        # Current policy
        old_policy = await sb_run(lambda: supabase_admin.table("user_policies").select("permissions").eq("user_id", user_id).execute())
        print(f"Current permissions in DB: {old_policy.data}")
        
        # Perform upsert
        test_perms = {"test_key": {"visible": False, "mutable": False}}
        res = await sb_run(lambda: supabase_admin.table("user_policies").upsert({
            "user_id": user_id,
            "permissions": test_perms
        }, on_conflict="user_id").execute())
        
        print(f"Upsert response data: {res.data}")
        
        # Read back
        new_policy = await sb_run(lambda: supabase_admin.table("user_policies").select("permissions").eq("user_id", user_id).execute())
        print(f"New permissions in DB after upsert: {new_policy.data}")
        
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test())
