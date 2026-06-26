import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.command_service import CommandService

@pytest.mark.asyncio
async def test_double_credentials_intercept():
    # 1. Setup mock BrowserController and page
    mock_page = AsyncMock()
    mock_user_loc = AsyncMock()
    mock_pass_loc = AsyncMock()
    
    # Configure locators to mock element existence and the '.first' property
    mock_user_loc.first = mock_user_loc
    mock_pass_loc.first = mock_pass_loc
    mock_user_loc.count = AsyncMock(return_value=1)
    mock_pass_loc.count = AsyncMock(return_value=1)
    mock_user_loc.fill = AsyncMock()
    mock_pass_loc.fill = AsyncMock()
    mock_pass_loc.press = AsyncMock()
    
    # page.locator return values
    def locator_side_effect(selector):
        if "email" in selector or "user" in selector:
            return mock_user_loc
        if "pass" in selector:
            return mock_pass_loc
        return AsyncMock()
        
    mock_page.locator = locator_side_effect
    
    # Mock BrowserEngine get_active_page
    mock_engine = MagicMock()
    mock_engine.get_active_page = AsyncMock(return_value=mock_page)
    mock_engine._context = MagicMock()
    
    # Patch BrowserController and _run_in_playwright in command_service
    with patch("automation.browser.browser_controller.BrowserController") as MockController, \
         patch("automation.browser.browser_engine._run_in_playwright") as mock_run_in_playwright, \
         patch("app.services.command_service._is_chrome_running_fast", return_value=True), \
         patch("automation.browser.browser_engine.BrowserEngine._animate_action", new_callable=AsyncMock):
        
        # Configure MockController
        controller_instance = MagicMock()
        controller_instance.engine = mock_engine
        MockController.return_value = controller_instance
        
        # Simulate running the async block
        async def mock_run_coro(coro):
            return await coro
        mock_run_in_playwright.side_effect = mock_run_coro
        
        # Execute double credentials command
        service = CommandService()
        result = await service.parse_and_execute("email nivin3456@gmail.com password reSet@123")
        
        # Verify success output
        assert result["intent"] == "implicit_browser_type"
        assert result["parameters"]["email"] == "nivin3456@gmail.com"
        assert result["parameters"]["password"] == "reSet@123"
        assert result["status"] == "success"
        assert "Filled email" in result["result"]
        
        # Verify mock fields were filled
        mock_user_loc.fill.assert_called_once_with("nivin3456@gmail.com")
        mock_pass_loc.fill.assert_called_once_with("reSet@123")
        mock_pass_loc.press.assert_called_once_with("Enter")


@pytest.mark.asyncio
async def test_double_credentials_spoken_symbols():
    # 1. Setup mock BrowserController and page
    mock_page = AsyncMock()
    mock_user_loc = AsyncMock()
    mock_pass_loc = AsyncMock()
    
    # Configure locators to mock element existence and the '.first' property
    mock_user_loc.first = mock_user_loc
    mock_pass_loc.first = mock_pass_loc
    mock_user_loc.count = AsyncMock(return_value=1)
    mock_pass_loc.count = AsyncMock(return_value=1)
    mock_user_loc.fill = AsyncMock()
    mock_pass_loc.fill = AsyncMock()
    mock_pass_loc.press = AsyncMock()
    
    # page.locator return values
    def locator_side_effect(selector):
        if "email" in selector or "user" in selector:
            return mock_user_loc
        if "pass" in selector:
            return mock_pass_loc
        return AsyncMock()
        
    mock_page.locator = locator_side_effect
    
    # Mock BrowserEngine get_active_page
    mock_engine = MagicMock()
    mock_engine.get_active_page = AsyncMock(return_value=mock_page)
    mock_engine._context = MagicMock()
    
    # Patch BrowserController and _run_in_playwright in command_service
    with patch("automation.browser.browser_controller.BrowserController") as MockController, \
         patch("automation.browser.browser_engine._run_in_playwright") as mock_run_in_playwright, \
         patch("app.services.command_service._is_chrome_running_fast", return_value=True), \
         patch("automation.browser.browser_engine.BrowserEngine._animate_action", new_callable=AsyncMock):
        
        # Configure MockController
        controller_instance = MagicMock()
        controller_instance.engine = mock_engine
        MockController.return_value = controller_instance
        
        # Simulate running the async block
        async def mock_run_coro(coro):
            return await coro
        mock_run_in_playwright.side_effect = mock_run_coro
        
        # Execute double credentials command with spoken terms
        service = CommandService()
        result = await service.parse_and_execute(
            "email nivin thirty four fifty six at the rate gmail dot com password reSet shift two one two three"
        )
        
        # Verify success output
        assert result["intent"] == "implicit_browser_type"
        assert result["parameters"]["email"] == "nivin3456@gmail.com"
        assert result["parameters"]["password"] == "reSet@123"
        assert result["status"] == "success"
        
        # Verify mock fields were filled
        mock_user_loc.fill.assert_called_once_with("nivin3456@gmail.com")
        mock_pass_loc.fill.assert_called_once_with("reSet@123")
