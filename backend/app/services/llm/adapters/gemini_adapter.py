"""Google Gemini Adapter."""
from __future__ import annotations
from typing import AsyncGenerator
from app.services.llm.base import LLMProvider
from loguru import logger


_MODELS = [
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-1.5-pro",
    "gemini-1.5-flash",
]


class GeminiAdapter(LLMProvider):
    def __init__(self, api_key: str, model: str = "gemini-2.0-flash"):
        import google.generativeai as genai
        # Do not use global genai.configure to avoid caching issues
        self._genai = genai
        self._api_key = api_key
        self._model_name = model

    @property
    def name(self) -> str:
        return "Gemini"

    @property
    def available_models(self) -> list[str]:
        return _MODELS

    def _to_gemini_format(self, messages: list[dict]) -> tuple[str, list]:
        """Convert OpenAI-style messages to Gemini format."""
        system = ""
        history = []
        for m in messages:
            if m["role"] == "system":
                system = m["content"]
            elif m["role"] == "user":
                history.append({"role": "user", "parts": [m["content"]]})
            elif m["role"] == "assistant":
                history.append({"role": "model", "parts": [m["content"]]})
        return system, history

    async def chat(self, messages: list[dict], *, temperature: float = 0.7, max_tokens: int = 1024) -> str:
        try:
            system_prompt, history = self._to_gemini_format(messages)
            model = self._genai.GenerativeModel(
                self._model_name,
                system_instruction=system_prompt or None,
                generation_config={"temperature": temperature, "max_output_tokens": max_tokens},
                client_options={"api_key": self._api_key},
            )
            # Last message should be the user prompt
            last_user = next((m["parts"][0] for m in reversed(history) if m["role"] == "user"), "")
            chat_history = history[:-1] if history and history[-1]["role"] == "user" else history
            chat = model.start_chat(history=chat_history)
            resp = await chat.send_message_async(last_user)
            return resp.text
        except Exception as e:
            logger.error(f"Gemini chat error: {e}")
            raise

    async def stream_chat(self, messages: list[dict], *, temperature: float = 0.7, max_tokens: int = 1024) -> AsyncGenerator[str, None]:
        try:
            system_prompt, history = self._to_gemini_format(messages)
            model = self._genai.GenerativeModel(
                self._model_name,
                system_instruction=system_prompt or None,
                generation_config={"temperature": temperature, "max_output_tokens": max_tokens},
                client_options={"api_key": self._api_key},
            )
            last_user = next((m["parts"][0] for m in reversed(history) if m["role"] == "user"), "")
            chat_history = history[:-1] if history and history[-1]["role"] == "user" else history
            chat = model.start_chat(history=chat_history)
            async for chunk in await chat.send_message_async(last_user, stream=True):
                if chunk.text:
                    yield chunk.text
        except Exception as e:
            logger.error(f"Gemini stream error: {e}")
            raise
