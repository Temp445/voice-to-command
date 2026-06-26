import asyncio
import sys
from app.config import settings
from automation.browser.browser_engine import BrowserEngine
from automation.browser.crm_workflows import CRMMacros

settings.crm_url = 'https://crm.acesoftcloud.in/'
settings.crm_sites = '[{"url":"https://crm.acesoftcloud.in/","keywords":"open my crm, open crm, open ace crm"}]'

async def main():
    print("Initializing BrowserEngine...", flush=True)
    engine = BrowserEngine()
    print("Ensuring browser...", flush=True)
    await engine.ensure_browser()
    
    mac = CRMMacros(engine)
    print("Calling login workflow...", flush=True)
    
    # We will run this with a timeout to prevent hanging the CLI
    try:
        res = await asyncio.wait_for(mac.login(), timeout=10.0)
        print("Login workflow finished with result:", res, flush=True)
    except asyncio.TimeoutError:
        print("Login workflow TIMED OUT!", flush=True)

if __name__ == "__main__":
    asyncio.run(main())
