import asyncio
import sys
import os

# Add e:\Nivin_Sync\ACE\Voice\voice-to-command\backend to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.config import settings
from app.services.intent_registry import register_all_intents
from app.services.command_service import command_service

settings.crm_url = 'https://crm.acesoftcloud.in/'
settings.crm_sites = '[{"url":"https://crm.acesoftcloud.in/","keywords":"open my crm, open crm, open ace crm"}]'

register_all_intents()

async def main():
    print("Testing command parsing and routing for: 'password reSet@123'...", flush=True)
    res = await command_service.parse_and_execute("password reSet@123")
    print("Result:", res, flush=True)

if __name__ == "__main__":
    asyncio.run(main())
