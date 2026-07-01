import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.command_service import CommandService
from app.services.spelling_service import spelling_corrector

def test_spelling_corrector_preserves_modified_case():
    # Make sure spelling_corrector is initialized
    spelling_corrector._initialized = True
    spelling_corrector.sym_spell = MagicMock()
    
    # SymSpell should normally lowercase/correct "Reset" to "reset" if not protected
    # Let's verify that a wrap-protected modified word is NOT corrected
    spelling_corrector.sym_spell.lookup.return_value = [MagicMock(term="reset")]
    
    input_text = "Password reset at 1, 2, 3, R caps."
    corrected = spelling_corrector.correct(input_text)
    
    # "Reset" should be capitalized and preserved
    assert "Reset" in corrected
    assert "reset" not in corrected.split() # The word 'reset' should be capitalized 'Reset'
    assert "R caps" not in corrected # Modifier tokens should be deleted

@pytest.mark.asyncio
async def test_password_modifier_integration():
    # Setup mock BrowserController and page to test the end-to-end command parsing
    mock_page = AsyncMock()
    mock_pass_loc = AsyncMock()
    
    mock_pass_loc.first = mock_pass_loc
    mock_pass_loc.count = AsyncMock(return_value=1)
    mock_pass_loc.fill = AsyncMock()
    mock_pass_loc.press = AsyncMock()
    
    def locator_side_effect(selector):
        if "pass" in selector:
            return mock_pass_loc
        return AsyncMock()
        
    mock_page.locator = locator_side_effect
    
    mock_engine = MagicMock()
    mock_engine.get_active_page = AsyncMock(return_value=mock_page)
    mock_engine._context = MagicMock()
    
    with patch("automation.browser.browser_controller.BrowserController") as MockController, \
         patch("automation.browser.browser_engine._run_in_playwright") as mock_run_in_playwright, \
         patch("app.services.command_service._is_chrome_running_fast", return_value=True), \
         patch("automation.browser.browser_engine.BrowserEngine._animate_action", new_callable=AsyncMock):
        
        controller_instance = MagicMock()
        controller_instance.engine = mock_engine
        MockController.return_value = controller_instance
        
        async def mock_run_coro(coro):
            return await coro
        mock_run_in_playwright.side_effect = mock_run_coro
        
        # Execute the user's specific test command
        service = CommandService()
        result = await service.parse_and_execute("Password reset at 1, 2, 3, R caps.")
        
        # Verify success output and correct normalization to "Reset@123"
        assert result["intent"] == "implicit_browser_type"
        assert result["parameters"]["field"] == "password"
        assert result["parameters"]["value"] == "Reset@123"
        assert result["status"] == "success"
        
        # Verify the password field was filled with "Reset@123"
        mock_pass_loc.fill.assert_called_once_with("Reset@123")
