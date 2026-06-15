import sys
import traceback
import asyncio
from app.services.intent_registry import handle_search_file
try:
    print(asyncio.run(handle_search_file('payroll')))
except Exception as e:
    traceback.print_exc()
    sys.exit(1)
