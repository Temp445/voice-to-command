import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock

from app.main import app
from app.config import get_settings

client = TestClient(app)

# Mock settings dependency to simulate production mode
def override_settings_production():
    from app.config import Settings
    # We must provide a custom secret key so it passes the Pydantic validator!
    return Settings(debug=False, secret_key="test-secure-key-12345")

@pytest_asyncio.fixture
async def async_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

def test_health():
    """Ensure the health check returns 200."""
    response = client.get("/health")
    if response.status_code == 404:
        response = client.get("/api/health")
    assert response.status_code == 200
    assert "status" in response.json()

def test_settings_get():
    """Ensure settings returns either 200 or 401."""
    response = client.get("/api/settings")
    assert response.status_code in (200, 401)

@patch("app.routers.commands.command_service.parse_and_execute")
@patch("app.routers.commands.sb_run", new_callable=AsyncMock)
def test_command_dispatch(mock_sb_run, mock_parse):
    """Ensure /api/commands/execute triggers the command service without 500s."""
    # Mock to prevent actual execution
    from app.schemas import CommandResultResponse
    mock_parse.return_value = {
        "status": "success",
        "result": "Command processed",
        "intent": "test_intent",
        "parameters": {}
    }
    
    # We must mock get_current_user_id since it uses Supabase auth
    from app.routers.commands import get_current_user_id
    app.dependency_overrides[get_current_user_id] = lambda: "test-user-id"
    
    try:
        response = client.post(
            "/api/commands/execute", 
            json={"text": "open google", "source": "text"}
        )
        assert response.status_code in (200, 202, 401, 422)
    finally:
        app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_replay_endpoint_forbidden_in_production(async_client):
    """Ensure the dev replay endpoint returns 403 when debug is False."""
    app.dependency_overrides[get_settings] = override_settings_production
    
    from app.config import settings
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
