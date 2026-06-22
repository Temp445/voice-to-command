import pytest
from unittest.mock import AsyncMock, patch, MagicMock

# Base mock definitions for different providers to avoid actual API calls
@pytest.fixture
def mock_openai():
    with patch("app.services.llm.adapters.openai_adapter.AsyncOpenAI") as mock:
        client_instance = AsyncMock()
        client_instance.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="OpenAI response"))]
        )
        mock.return_value = client_instance
        yield mock

@pytest.fixture
def mock_claude():
    with patch("app.services.llm.adapters.claude_adapter.AsyncAnthropic") as mock:
        client_instance = AsyncMock()
        client_instance.messages.create.return_value = MagicMock(
            content=[MagicMock(text="Claude response")]
        )
        mock.return_value = client_instance
        yield mock

@pytest.fixture
def mock_gemini():
    with patch("app.services.llm.adapters.gemini_adapter.genai") as mock_genai:
        mock_model = AsyncMock()
        mock_model.generate_content_async.return_value = MagicMock(text="Gemini response")
        mock_genai.GenerativeModel.return_value = mock_model
        yield mock_genai

@pytest.fixture
def mock_groq():
    with patch("app.services.llm.adapters.groq_adapter.AsyncGroq") as mock:
        client_instance = AsyncMock()
        client_instance.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="Groq response"))]
        )
        mock.return_value = client_instance
        yield mock

@pytest.fixture
def mock_deepseek():
    with patch("app.services.llm.adapters.deepseek_adapter.AsyncOpenAI") as mock:
        client_instance = AsyncMock()
        client_instance.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="DeepSeek response"))]
        )
        mock.return_value = client_instance
        yield mock

@pytest.fixture
def mock_ollama():
    with patch("app.services.llm.adapters.ollama_adapter.AsyncClient") as mock:
        client_instance = AsyncMock()
        client_instance.chat.return_value = {"message": {"content": "Ollama response"}}
        mock.return_value = client_instance
        yield mock


@pytest.mark.asyncio
async def test_openai_adapter(mock_openai):
    from app.services.llm.adapters.openai_adapter import OpenAIAdapter
    adapter = OpenAIAdapter(api_key="test-key", model="gpt-4")
    res = await adapter.generate_response([{"role": "user", "content": "hello"}])
    assert "OpenAI response" in res

@pytest.mark.asyncio
async def test_claude_adapter(mock_claude):
    from app.services.llm.adapters.claude_adapter import ClaudeAdapter
    adapter = ClaudeAdapter(api_key="test-key", model="claude-3")
    res = await adapter.generate_response([{"role": "user", "content": "hello"}])
    assert "Claude response" in res

@pytest.mark.asyncio
async def test_gemini_adapter(mock_gemini):
    from app.services.llm.adapters.gemini_adapter import GeminiAdapter
    adapter = GeminiAdapter(api_key="test-key", model="gemini-1.5")
    res = await adapter.generate_response([{"role": "user", "content": "hello"}])
    assert "Gemini response" in res

@pytest.mark.asyncio
async def test_groq_adapter(mock_groq):
    from app.services.llm.adapters.groq_adapter import GroqAdapter
    adapter = GroqAdapter(api_key="test-key", model="mixtral")
    res = await adapter.generate_response([{"role": "user", "content": "hello"}])
    assert "Groq response" in res

@pytest.mark.asyncio
async def test_deepseek_adapter(mock_deepseek):
    from app.services.llm.adapters.deepseek_adapter import DeepSeekAdapter
    adapter = DeepSeekAdapter(api_key="test-key", model="deepseek-chat")
    res = await adapter.generate_response([{"role": "user", "content": "hello"}])
    assert "DeepSeek response" in res

@pytest.mark.asyncio
async def test_ollama_adapter(mock_ollama):
    from app.services.llm.adapters.ollama_adapter import OllamaAdapter
    adapter = OllamaAdapter(api_key="http://localhost:11434", model="llama3")
    res = await adapter.generate_response([{"role": "user", "content": "hello"}])
    assert "Ollama response" in res

# Test generate_json with a mock response formatted as JSON string
@pytest.mark.asyncio
async def test_openai_generate_json(mock_openai):
    mock_openai.return_value.chat.completions.create.return_value.choices[0].message.content = '{"key": "value"}'
    from app.services.llm.adapters.openai_adapter import OpenAIAdapter
    adapter = OpenAIAdapter(api_key="test", model="gpt-4")
    res = await adapter.generate_json([{"role": "user", "content": "hello"}])
    assert isinstance(res, dict)
    assert res.get("key") == "value"

@pytest.mark.asyncio
async def test_gemini_generate_json(mock_gemini):
    mock_model = AsyncMock()
    mock_model.generate_content_async.return_value = MagicMock(text='```json\n{"status": "success"}\n```')
    mock_gemini.GenerativeModel.return_value = mock_model
    from app.services.llm.adapters.gemini_adapter import GeminiAdapter
    adapter = GeminiAdapter(api_key="test", model="gemini-1.5")
    res = await adapter.generate_json([{"role": "user", "content": "hello"}])
    assert res.get("status") == "success"
