import asyncio
import sys
import os

sys.path.append("E:\\Nivin_Sync\\ACE\\Voice\\Voice_Controller_v1")
print("Appended to sys.path")

try:
    from backend.automation.browser.browser_agent import AutonomousBrowserAgent
    from backend.app.services.llm.llm_service import llm_service
    print("Imported AutonomousBrowserAgent")
except Exception as e:
    print("Error importing:", e)

async def test():
    class DummyEngine:
        async def ensure_browser(self):
            return None
        _context = None

    try:
        print("Calling run_task")
        res = await AutonomousBrowserAgent.run_task("email nivin33@gmail.com and password Reset@123", DummyEngine())
        print("Result:", res)
    except Exception as e:
        print("CRASH:", e)

if __name__ == "__main__":
    print("Starting asyncio")
    asyncio.run(test())
