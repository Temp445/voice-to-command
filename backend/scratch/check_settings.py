import asyncio
from app.config import settings
from app.core.supabase_client import supabase_admin, sb_run

async def main():
    print("In-memory settings:")
    print("browser_animations_enabled:", settings.browser_animations_enabled)
    print("restrict_browser_automation:", settings.restrict_browser_automation)
    print("owner_user_id:", settings.owner_user_id)
    
    print("\nQuerying Supabase settings table:")
    try:
        res = await sb_run(lambda: supabase_admin.table("settings").select("*").execute())
        if res.data:
            for row in res.data:
                print(f"User ID: {row.get('user_id')}")
                print(f"  browser_animations_enabled: {row.get('browser_animations_enabled')}")
                print(f"  restrict_browser_automation: {row.get('restrict_browser_automation')}")
        else:
            print("No rows found in settings table.")
    except Exception as e:
        print("Database query failed:", e)

if __name__ == "__main__":
    asyncio.run(main())
