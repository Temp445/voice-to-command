"""
ACE Voice Controller — LLM Provider Abstract Base
All provider adapters must implement this interface.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import AsyncGenerator


class LLMProvider(ABC):
    """Abstract base for all LLM provider adapters."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Friendly provider name e.g. 'Groq', 'OpenAI'."""

    @property
    @abstractmethod
    def available_models(self) -> list[str]:
        """List of model IDs this provider supports."""

    @abstractmethod
    async def chat(
        self,
        messages: list[dict],
        *,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str:
        """
        Send a conversation to the LLM and return the complete reply.
        `messages` follows the OpenAI format:
            [{"role": "system" | "user" | "assistant", "content": "..."}]
        """

    @abstractmethod
    async def stream_chat(
        self,
        messages: list[dict],
        *,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> AsyncGenerator[str, None]:
        """
        Stream the LLM reply token-by-token.
        Yields partial text strings as they arrive.
        """
        # This makes the method a generator; subclasses must use `yield`.
        # The pragma below silences the abstract-method linter warning.
        yield  # pragma: no cover
