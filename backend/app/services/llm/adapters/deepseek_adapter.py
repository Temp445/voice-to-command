"""DeepSeek Adapter — Uses the OpenAI-compatible DeepSeek API."""
from __future__ import annotations
from typing import AsyncGenerator
from app.services.llm.base import LLMProvider
from loguru import logger

_DEEPSEEK_BASE_URL = "https://api.deepseek.com"

_MODELS = [
    "deepseek-chat",
    "deepseek-reasoner",
]


class DeepSeekAdapter(LLMProvider):
    def __init__(self, api_key: str, model: str = "deepseek-chat"):
        from openai import AsyncOpenAI
        self._client = AsyncOpenAI(api_key=api_key, base_url=_DEEPSEEK_BASE_URL)
        self._model = model

    @property
    def name(self) -> str:
        return "DeepSeek"

    @property
    def available_models(self) -> list[str]:
        return _MODELS

    async def chat(self, messages: list[dict], *, temperature: float = 0.7, max_tokens: int = 1024) -> str:
        try:
            resp = await self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return resp.choices[0].message.content or ""
        except Exception as e:
            logger.error(f"DeepSeek chat error: {e}")
            raise

    async def stream_chat(self, messages: list[dict], *, temperature: float = 0.7, max_tokens: int = 1024) -> AsyncGenerator[str, None]:
        try:
            stream = await self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
            )
            async for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta
        except Exception as e:
            logger.error(f"DeepSeek stream error: {e}")
            raise
