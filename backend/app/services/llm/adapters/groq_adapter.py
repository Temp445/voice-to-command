"""Groq Adapter — Ultra-fast inference via Groq LPU cloud API."""
from __future__ import annotations
from typing import AsyncGenerator
from app.services.llm.base import LLMProvider
from loguru import logger


_MODELS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "llama3-70b-8192",
    "mixtral-8x7b-32768",
    "gemma2-9b-it",
]


class GroqAdapter(LLMProvider):
    def __init__(self, api_key: str, model: str = "llama-3.3-70b-versatile"):
        from groq import AsyncGroq
        self._client = AsyncGroq(api_key=api_key, timeout=10.0)
        self._model = model

    @property
    def name(self) -> str:
        return "Groq"

    @property
    def available_models(self) -> list[str]:
        return _MODELS

    def _clean_messages(self, messages: list[dict]) -> list[dict]:
        cleaned = []
        for msg in messages:
            role = msg.get("role")
            content = msg.get("content")
            if isinstance(content, list):
                text_parts = []
                for item in content:
                    if isinstance(item, dict):
                        if item.get("type") == "text":
                            text_parts.append(item.get("text", ""))
                    elif isinstance(item, str):
                        text_parts.append(item)
                content = "\n".join(text_parts)
            cleaned.append({"role": role, "content": content})
        return cleaned

    async def chat(self, messages: list[dict], *, temperature: float = 0.7, max_tokens: int = 1024) -> str:
        try:
            cleaned_messages = self._clean_messages(messages)
            resp = await self._client.chat.completions.create(
                model=self._model,
                messages=cleaned_messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return resp.choices[0].message.content or ""
        except Exception as e:
            logger.error(f"Groq chat error: {e}")
            raise

    async def stream_chat(self, messages: list[dict], *, temperature: float = 0.7, max_tokens: int = 1024) -> AsyncGenerator[str, None]:
        try:
            cleaned_messages = self._clean_messages(messages)
            stream = await self._client.chat.completions.create(
                model=self._model,
                messages=cleaned_messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
            )
            async for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta
        except Exception as e:
            logger.error(f"Groq stream error: {e}")
            raise
