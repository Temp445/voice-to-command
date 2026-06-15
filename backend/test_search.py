import traceback
from app.services.command_service import command_service
import asyncio

try:
    result = asyncio.run(command_service.parse_and_execute('search payroll'))
    print(result)
except Exception:
    traceback.print_exc()
