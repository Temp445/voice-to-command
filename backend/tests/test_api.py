import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.config import get_settings

# Mock settings dependency to simulate production mode
def override_settings_production():
    from app.config import Settings
    # We must provide a custom secret key so it passes the Pydantic validator!
    return Settings(debug=False, secret_key="test-secure-key-12345")

@pytest_asyncio.fixture
async def async_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

@pytest.mark.asyncio
async def test_replay_endpoint_forbidden_in_production(async_client):
    """Ensure the dev replay endpoint returns 403 when debug is False."""
    app.dependency_overrides[get_settings] = override_settings_production
    
    from app.main import settings
    original_debug = settings.debug
    settings.debug = False
    
    try:
        response = await async_client.get("/api/test/replay")
        assert response.status_code == 403
        assert "Dev endpoints are disabled" in response.json()["detail"]
    finally:
        # Restore the original debug flag
        settings.debug = original_debug
        app.dependency_overrides.clear()
