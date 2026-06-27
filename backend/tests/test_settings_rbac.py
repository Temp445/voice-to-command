import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch, MagicMock

from app.main import app
from app.routers.settings_router import get_current_user_id

client = TestClient(app)

class MockQuery:
    def __init__(self, table_name, data_map):
        self.table_name = table_name
        self.data_map = data_map

    def select(self, *args, **kwargs):
        return self

    def insert(self, *args, **kwargs):
        return self

    def update(self, *args, **kwargs):
        return self

    def upsert(self, *args, **kwargs):
        return self

    def eq(self, *args, **kwargs):
        return self

    def execute(self):
        res = MagicMock()
        res.data = self.data_map.get(self.table_name, [])
        return res


@pytest.fixture
def mock_auth():
    # Bypass auth and return test-user-id
    app.dependency_overrides[get_current_user_id] = lambda: "test-user-id"
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_settings_visibility_filtering(mock_auth):
    """Test that a non-admin user gets filtered settings based on visibility policy."""
    mock_data = {
        "settings": [{
            "user_id": "test-user-id",
            "wake_word": "alexa",
            "browser_animations_enabled": True,
            "enable_desktop_overlay": True,
            "screen_settings_visible_to_users": False, # Screen settings hidden for users!
        }],
        "users": [{
            "id": "test-user-id",
            "role": "user",
        }],
        "user_policies": [{
            "user_id": "test-user-id",
            "permissions": {
                "browser_animations_enabled": {"visible": False, "mutable": False}
            }
        }]
    }

    # Patch supabase_admin in both routers
    mock_supabase = MagicMock()
    mock_supabase.table.side_effect = lambda t: MockQuery(t, mock_data)

    with patch("app.routers.settings_router.supabase_admin", mock_supabase):
        response = client.get("/api/settings")
        assert response.status_code == 200
        data = response.json()
        
        # Verify permissions map is returned
        assert "permissions" in data
        assert "role" in data
        assert data["role"] == "user"
        
        # Since screen_settings_visible_to_users is False, the restricted keys must be hidden
        assert data["permissions"]["browser_animations_enabled"]["visible"] is False
        assert data["permissions"]["enable_desktop_overlay"]["visible"] is False


@pytest.mark.asyncio
async def test_update_settings_read_only_block(mock_auth):
    """Test that regular users are forbidden from patching read-only/restricted fields."""
    mock_data = {
        "settings": [{
            "user_id": "test-user-id",
            "wake_word": "alexa",
            "browser_animations_enabled": True,
            "screen_settings_visible_to_users": True,
        }],
        "users": [{
            "id": "test-user-id",
            "role": "user",
        }],
        "user_policies": [{
            "user_id": "test-user-id",
            "permissions": {
                "browser_animations_enabled": {"visible": True, "mutable": False}
            }
        }]
    }

    mock_supabase = MagicMock()
    mock_supabase.table.side_effect = lambda t: MockQuery(t, mock_data)

    with patch("app.routers.settings_router.supabase_admin", mock_supabase):
        # Attempt to patch a read-only setting field
        response = client.patch("/api/settings", json={"browser_animations_enabled": False})
        
        # Must be forbidden!
        assert response.status_code == 403
        assert "is read-only or restricted" in response.json()["detail"]


@pytest.mark.asyncio
async def test_admin_list_policies(mock_auth):
    """Test that list policies endpoint returns user list to admins."""
    # Override admin dependency to simulate admin calling it
    from app.routers.policy_router import get_current_admin_user_id
    app.dependency_overrides[get_current_admin_user_id] = lambda: "admin-user-id"
    
    mock_data = {
        "users": [
            {"id": "user-1", "email": "user1@example.com", "display_name": "User 1", "role": "user"},
            {"id": "admin-1", "email": "admin@example.com", "display_name": "Admin", "role": "admin"}
        ],
        "user_policies": [
            {"user_id": "user-1", "permissions": {"browser_animations_enabled": {"visible": True, "mutable": False}}}
        ],
        "settings": [
            {"user_id": "user-1", "screen_settings_visible_to_users": True},
            {"user_id": "admin-1", "screen_settings_visible_to_users": True}
        ]
    }

    mock_supabase = MagicMock()
    mock_supabase.table.side_effect = lambda t: MockQuery(t, mock_data)

    try:
        with patch("app.routers.policy_router.supabase_admin", mock_supabase):
            response = client.get("/api/admin/policies")
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 2
            assert data[0]["email"] == "user1@example.com"
            assert data[0]["screen_settings_visible_to_users"] is True
            assert "browser_animations_enabled" in data[0]["permissions"]
    finally:
        app.dependency_overrides.clear()
