import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.llm.llm_service import LLMService, PROVIDER_REGISTRY

@pytest.fixture
def llm_service():
    return LLMService()

def test_set_provider_invalid(llm_service):
    with pytest.raises(ValueError, match="Unknown provider"):
        llm_service.set_provider("invalid-provider", "key", "model")

@patch('importlib.import_module')
def test_set_provider_valid(mock_import, llm_service):
    # Mock the imported module and class
    mock_module = MagicMock()
    mock_class = MagicMock()
    setattr(mock_module, "GroqAdapter", mock_class)
    mock_import.return_value = mock_module
    
    llm_service.set_provider("groq", "test-key", "llama-3.3-70b-versatile", 0.5, "fallback", True)
    
    assert llm_service.is_ready is True
    assert llm_service._provider_name == "groq"
    assert llm_service._model == "llama-3.3-70b-versatile"
    assert llm_service._temperature == 0.5
    assert llm_service._mode == "fallback"
    mock_class.assert_called_once_with(api_key="test-key", model="llama-3.3-70b-versatile")

def test_disable(llm_service):
    llm_service.disable("Testing disable")
    assert llm_service.is_ready is False
    assert llm_service._provider is None
    assert llm_service.last_error == "Testing disable"

@patch('app.services.context_state.get_context')
def test_build_messages_with_history(mock_get_context, llm_service):
    mock_context = MagicMock()
    mock_context.get_all.return_value = {"active_window": None}  # Empty context
    mock_get_context.return_value = mock_context
    
    llm_service.add_to_history("user", "Hello")
    llm_service.add_to_history("assistant", "Hi there")
    
    msgs = llm_service._build_messages("System instruction", "How are you?")
    
    assert len(msgs) == 4
    assert msgs[0]["role"] == "system"
    assert "System instruction" in msgs[0]["content"]
    assert msgs[1] == {"role": "user", "content": "Hello"}
    assert msgs[2] == {"role": "assistant", "content": "Hi there"}
    assert msgs[3] == {"role": "user", "content": "How are you?"}

@pytest.mark.asyncio
async def test_classify_intent_success(llm_service):
    # Setup mock provider
    mock_provider = AsyncMock()
    # Provide a valid JSON string (even with markdown)
    mock_provider.chat.return_value = '```json\n{"intent": "open_app", "confidence": 0.95, "params": {"app": "notepad"}}\n```'
    
    llm_service._provider = mock_provider
    llm_service._enabled = True
    
    available_intents = [{"name": "open_app", "description": "Open an app", "param_names": ["app"]}]
    
    # Needs to mock context_manager
    with patch('app.services.context_manager.context_manager') as mock_ctx:
        mock_ctx.get_system_prompt_injection.return_value = ""
        result = await llm_service.classify_intent("Open notepad", available_intents)
        
    assert result is not None
    assert result["intent"] == "open_app"
    assert result["confidence"] == 0.95
    assert result["params"]["app"] == "notepad"

@pytest.mark.asyncio
async def test_classify_intent_not_ready(llm_service):
    llm_service._enabled = False
    result = await llm_service.classify_intent("test", [])
    assert result is None
