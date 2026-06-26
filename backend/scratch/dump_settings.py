import asyncio
from app.config import settings

async def main():
    print("crm_url:", settings.crm_url)
    print("crm_keywords:", settings.crm_keywords)
    print("crm_sites:", settings.crm_sites)

if __name__ == "__main__":
    asyncio.run(main())
