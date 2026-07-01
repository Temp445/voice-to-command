"""Anthropic Claude Adapter."""
from __future__ import annotations
from typing import AsyncGenerator
from app.services.llm.base import LLMProvider
from loguru import logger


_MODELS = [
    "claude-opus-4-5",
    "claude-sonnet-4-5",
    "claude-haiku-3-5",
    "claude-3-opus-20240229",
]


class ClaudeAdapter(LLMProvider):
    def __init__(self, api_key: str, model: str = "claude-haiku-3-5"):
        import anthropic
        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._model = model

    @property
    def name(self) -> str:
        return "Claude"

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

    def _extract_system(self, messages: list[dict]) -> tuple[str, list[dict]]:
        system = next((m["content"] for m in messages if m["role"] == "system"), "")
        non_system = [m for m in messages if m["role"] != "system"]
        return system, non_system

    async def chat(self, messages: list[dict], *, temperature: float = 0.7, max_tokens: int = 1024) -> str:
        try:
            cleaned_messages = self._clean_messages(messages)
            system, msgs = self._extract_system(cleaned_messages)
            resp = await self._client.messages.create(
                model=self._model,
                system=system or anthropic.NOT_GIVEN,
                messages=msgs,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return resp.content[0].text
        except Exception as e:
            logger.error(f"Claude chat error: {e}")
            raise

    async def stream_chat(self, messages: list[dict], *, temperature: float = 0.7, max_tokens: int = 1024) -> AsyncGenerator[str, None]:
        try:
            import anthropic
            cleaned_messages = self._clean_messages(messages)
            system, msgs = self._extract_system(cleaned_messages)
            async with self._client.messages.stream(
                model=self._model,
                system=system or anthropic.NOT_GIVEN,
                messages=msgs,
                temperature=temperature,
                max_tokens=max_tokens,
            ) as stream:
                async for text in stream.text_stream:
                     yield text
        except Exception as e:
            logger.error(f"Claude stream error: {e}")
            raise
