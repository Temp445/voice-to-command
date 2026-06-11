from supabase import create_client, Client
from loguru import logger
from app.config import settings

def get_supabase_client() -> Client | None:
    if not settings.supabase_url or not settings.supabase_publishable_key:
        logger.warning("Supabase URL or Publishable Key not configured. Supabase Auth will fail.")
        return None
    return create_client(settings.supabase_url, settings.supabase_publishable_key)

supabase = get_supabase_client()
