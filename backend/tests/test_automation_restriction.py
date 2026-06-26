import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from app.config import settings
from automation.browser.browser_engine import BrowserEngine

@pytest.fixture
def clean_settings():
    # Store original values
    orig_restrict = settings.restrict_browser_automation
    orig_crm_sites = settings.crm_sites
    yield settings
    # Restore original values
    settings.restrict_browser_automation = orig_restrict
    settings.crm_sites = orig_crm_sites

def test_is_shortcut_url_internal_and_local(clean_settings):
    engine = BrowserEngine()
    
    # Internal page matches
    assert engine._is_shortcut_url("about:blank") is True
    assert engine._is_shortcut_url("chrome://settings") is True
    assert engine._is_shortcut_url("chrome-extension://abcde/options.html") is True
    assert engine._is_shortcut_url("new-tab-page") is True
    assert engine._is_shortcut_url("chrome://new-tab-page") is True
    assert engine._is_shortcut_url("newtab") is True
    
    # Local host matches
    assert engine._is_shortcut_url("http://localhost:3000") is True
    assert engine._is_shortcut_url("http://127.0.0.1:8000/api") is True

def test_is_shortcut_url_custom_sites(clean_settings):
    engine = BrowserEngine()
    
    # Setup mock shortcuts in settings
    clean_settings.crm_sites = json.dumps([
        {"url": "https://crm.acesoftcloud.in/", "keywords": "crm"},
        {"url": "google.com", "keywords": "search"}
    ])
    
    # Check exact and subdomain matches
    assert engine._is_shortcut_url("https://crm.acesoftcloud.in/dashboard") is True
    assert engine._is_shortcut_url("http://crm.acesoftcloud.in") is True
    assert engine._is_shortcut_url("google.com") is True
    assert engine._is_shortcut_url("https://www.google.com/search?q=test") is True
    assert engine._is_shortcut_url("sub.google.com") is True
    
    # Check non-matches
    assert engine._is_shortcut_url("https://yahoo.com") is False
    assert engine._is_shortcut_url("https://bing.com/search") is False

@pytest.mark.asyncio
async def test_navigate_restricted_check(clean_settings):
    engine = BrowserEngine()
    clean_settings.restrict_browser_automation = True
    clean_settings.crm_sites = json.dumps([
        {"url": "example.com", "keywords": "example"}
    ])
    
    # Navigate to allowed site should NOT raise error (it will call page.goto, so we mock page/context)
    mock_page = AsyncMock()
    mock_context = AsyncMock()
    mock_context.pages = [mock_page]
    engine._context = mock_context
    engine._active_page_override = mock_page
    
    # Mocking page.goto to avoid real browser invocation
    mock_page.goto = AsyncMock(return_value=None)
    mock_page.bring_to_front = AsyncMock()
    mock_page.is_closed = MagicMock(return_value=False)
    
    # Navigation to allowed site
    try:
        await engine.navigate("example.com")
    except PermissionError:
        pytest.fail("Should not raise PermissionError for allowed shortcut website")
        
    # Navigation to restricted site MUST raise PermissionError
    with pytest.raises(PermissionError) as exc_info:
        await engine.navigate("google.com")
    
    assert "Automation restricted" in str(exc_info.value)
    assert "google.com" in str(exc_info.value)

@pytest.mark.asyncio
async def test_get_active_page_restricted_check(clean_settings):
    engine = BrowserEngine()
    clean_settings.restrict_browser_automation = True
    clean_settings.crm_sites = json.dumps([
        {"url": "example.com", "keywords": "example"}
    ])
    
    mock_page = AsyncMock()
    mock_page.is_closed = MagicMock(return_value=False)
    
    # Allowed site active page
    mock_page.url = "https://example.com/dashboard"
    engine._active_page_override = mock_page
    engine.invalidate_active_page_cache()
    
    page = await engine.get_active_page(allow_restricted=False)
    assert page == mock_page
    
    # Restricted site active page MUST raise PermissionError
    mock_page.url = "https://restricted.com/login"
    engine.invalidate_active_page_cache()
    
    with pytest.raises(PermissionError) as exc_info:
        await engine.get_active_page(allow_restricted=False)
        
    assert "Automation restricted" in str(exc_info.value)
    assert "restricted.com" in str(exc_info.value)
