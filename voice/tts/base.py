"""
ACE Voice Controller — Abstract TTS Provider Interface
All TTS backends must implement this contract.
"""

from abc import ABC, abstractmethod


class TTSProvider(ABC):
    """Abstract base class for Text-to-Speech providers."""

    @abstractmethod
    async def synthesize(self, text: str) -> bytes:
        """
        Convert text to audio bytes (WAV format).
        Returns raw WAV bytes ready for playback.
        """
        ...

    @abstractmethod
    async def get_available_voices(self) -> list[str]:
        """Return list of available voice IDs for this provider."""
        ...

    @abstractmethod
    def requires_api_key(self) -> bool:
        """True if this provider needs an API key to function."""
        ...

    @abstractmethod
    def is_configured(self) -> bool:
        """True if the provider has everything it needs to function."""
        ...

    @property
    def provider_name(self) -> str:
        return self.__class__.__name__
