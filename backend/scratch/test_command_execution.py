import asyncio
from app.config import settings
from app.services.intent_registry import register_all_intents
from app.services.command_service import command_service

settings.crm_url = 'https://crm.acesoftcloud.in/'
settings.crm_sites = '[{"url":"https://crm.acesoftcloud.in/","keywords":"open my crm, open crm, open ace crm"}]'

register_all_intents()

async def main():
    print("Starting parse_and_execute...", flush=True)
    res = await command_service.parse_and_execute("sign in crm")
    print("Result:", res, flush=True)

if __name__ == "__main__":
    asyncio.run(main())
