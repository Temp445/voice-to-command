import pytest
from app.services.command_service import CommandService, Intent

@pytest.fixture
def command_service():
    service = CommandService()
    # Register a few simple intents for testing
    
    async def mock_handler(app: str = "", **kwargs):
        return f"Opening {app}"
        
    async def mock_search(query: str = "", **kwargs):
        return f"Searching for {query}"
        
    service.register(Intent(
        name="open_app",
        description="Open an application",
        patterns=[r"(?:open|launch|start) ([\w\s]+)"],
        param_names=["app"],
        handler=mock_handler
    ))
    
    service.register(Intent(
        name="search_google",
        description="Search Google",
        patterns=[r"(?:search|google|lookup) ([\w\s]+)"],
        param_names=["query"],
        handler=mock_search
    ))
    
    return service

@pytest.mark.asyncio
async def test_intent_fast_path_exact_match(command_service):
    """Test that regex patterns correctly match and extract parameters."""
    result = await command_service.process_command("open notepad")
    # Result should be the string returned by the handler
    assert result == "Opening notepad"
    
    result2 = await command_service.process_command("search Python programming")
    assert result2 == "Searching for Python programming"

@pytest.mark.asyncio
async def test_intent_no_match(command_service):
    """Test behavior when no fast-path regex matches and LLM is disabled."""
    # Since we didn't mock LLMService here, but LLMService is default disabled
    # process_command should return an error or fallback string.
    result = await command_service.process_command("do something unknown")
    
    # In command_service.py, if no match and LLM is disabled, it returns:
    # "I didn't understand that command."
    assert "didn't understand" in result.lower()

def test_intent_registry_registration(command_service):
    """Test that intents are correctly registered in the service."""
    assert len(command_service.intents) == 2
    assert command_service.intents[0].name == "open_app"
    assert command_service.intents[1].name == "search_google"
    assert command_service.intents[0].param_names == ["app"]
