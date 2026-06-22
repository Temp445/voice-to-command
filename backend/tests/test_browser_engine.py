import pytest
from unittest.mock import AsyncMock, patch, MagicMock

@pytest.fixture
def mock_playwright():
    with patch("automation.browser.browser_engine.async_playwright") as mock_ap:
        # Mock the playwright context manager
        mock_pw_instance = AsyncMock()
        mock_browser = AsyncMock()
        mock_context = AsyncMock()
        mock_page = AsyncMock()
        
        # Setup the chain: async_playwright() -> start() -> browser -> new_context -> new_page
        mock_ap.return_value.__aenter__.return_value = mock_pw_instance
        
        # Mock Chromium launch
        mock_pw_instance.chromium.launch.return_value = mock_browser
        
        # Mock context creation
        mock_browser.new_context.return_value = mock_context
        
        # Mock page creation
        mock_context.new_page.return_value = mock_page
        
        yield {
            "ap": mock_ap,
            "pw": mock_pw_instance,
            "browser": mock_browser,
            "context": mock_context,
            "page": mock_page
        }

@pytest.mark.asyncio
async def test_init_browser(mock_playwright):
    """Test that the browser initializes with the correct stealth arguments."""
    from automation.browser.browser_engine import BrowserEngine
    engine = BrowserEngine()
    
    await engine.init_browser()
    
    # Assert playwright was started
    mock_playwright["pw"].chromium.launch.assert_called_once()
    kwargs = mock_playwright["pw"].chromium.launch.call_args[1]
    
    # Check that stealth args were passed
    assert "args" in kwargs
    assert "--disable-blink-features=AutomationControlled" in kwargs["args"]
    assert engine.page is not None
    assert engine.context is not None

@pytest.mark.asyncio
async def test_navigate(mock_playwright):
    """Test navigation commands."""
    from automation.browser.browser_engine import BrowserEngine
    engine = BrowserEngine()
    await engine.init_browser()
    
    # Test valid URL
    await engine.navigate("https://example.com")
    mock_playwright["page"].goto.assert_called_with("https://example.com", timeout=60000)

@pytest.mark.asyncio
async def test_close(mock_playwright):
    """Test cleanup of browser resources."""
    from automation.browser.browser_engine import BrowserEngine
    engine = BrowserEngine()
    await engine.init_browser()
    
    await engine.close()
    
    mock_playwright["context"].close.assert_called_once()
    mock_playwright["browser"].close.assert_called_once()
