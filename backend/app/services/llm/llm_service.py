"""
ACE Voice Controller — LLM Service (Singleton)

Central service that manages:
  - Provider hot-swapping (change model without restarting)
  - Conversation memory (rolling 10-message buffer)
  - Intent classification for the command pipeline fallback
  - Direct chat for the AI Chat page
"""
from __future__ import annotations

import json
from collections import deque
from typing import AsyncGenerator

from loguru import logger

from app.services.llm.base import LLMProvider

# ─── Provider Registry ────────────────────────────────────────────────────────
# Maps provider name → (adapter class, required package)
PROVIDER_REGISTRY: dict[str, dict] = {
    "groq":     {"class": "GroqAdapter",     "module": "app.services.llm.adapters.groq_adapter",     "models": ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "llama3-70b-8192", "mixtral-8x7b-32768", "gemma2-9b-it"]},
    "openai":   {"class": "OpenAIAdapter",   "module": "app.services.llm.adapters.openai_adapter",   "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"]},
    "gemini":   {"class": "GeminiAdapter",   "module": "app.services.llm.adapters.gemini_adapter",   "models": ["gemini-2.0-flash", "gemini-2.0-flash-lite", "gemini-1.5-pro", "gemini-1.5-flash"]},
    "claude":   {"class": "ClaudeAdapter",   "module": "app.services.llm.adapters.claude_adapter",   "models": ["claude-opus-4-5", "claude-sonnet-4-5", "claude-haiku-3-5"]},
    "deepseek": {"class": "DeepSeekAdapter", "module": "app.services.llm.adapters.deepseek_adapter", "models": ["deepseek-chat", "deepseek-reasoner"]},
}

# System prompt used when classifying intents
_INTENT_CLASSIFIER_SYSTEM = """You are a context-aware command router for a desktop voice assistant.
Your ONLY job is to classify the user's latest command into one of the available intents.
Crucially, you must use the provided conversation history to resolve any pronouns (like "it", "this", "that") and extract the correct intent parameters.

Rules:
- Reply with ONLY a valid JSON object. No markdown formatting, no explanations.
- Format: {"intent": "<intent_name>", "confidence": <0.0-1.0>, "params": {"<param_name>": "<resolved_value>"}}
- If the command relies on previous context (e.g., "run it"), use the history to determine what "it" refers to and fill the parameters accordingly.
- If no intent matches reasonably, return: {"intent": null, "confidence": 0.0, "params": {}}
- Choose the single best-matching intent.
"""

# System prompt for general AI chat
_CHAT_SYSTEM = """You are ACE, an intelligent desktop automation assistant.
You help users control their computer, answer questions, and generate content.
Be concise, helpful, and friendly. When generating text to be typed (emails, code, etc.), 
output ONLY the final content — no preamble like "Here is the email:".
"""


class LLMService:
    """
    App-wide singleton. Hot-swappable provider with conversation memory.
    """

    def __init__(self):
        self._provider: LLMProvider | None = None
        self._provider_name: str = ""
        self._model: str = ""
        self._temperature: float = 0.7
        self._enabled: bool = False
        self._mode: str = "fallback"  # "fallback" | "always_on"
        # Rolling conversation history (max 10 exchanges = 20 messages + system)
        self._history: deque[dict] = deque(maxlen=20)

    # ── Configuration ─────────────────────────────────────────────────────────

    def set_provider(
        self,
        provider_name: str,
        api_key: str,
        model: str,
        temperature: float = 0.7,
        mode: str = "fallback",
        enabled: bool = True,
    ) -> None:
        """Hot-swap the active LLM provider. Called when settings are saved."""
        if provider_name not in PROVIDER_REGISTRY:
            raise ValueError(f"Unknown provider: '{provider_name}'. Available: {list(PROVIDER_REGISTRY)}")

        reg = PROVIDER_REGISTRY[provider_name]
        try:
            import importlib
            mod = importlib.import_module(reg["module"])
            cls = getattr(mod, reg["class"])
            self._provider = cls(api_key=api_key, model=model)
            self._provider_name = provider_name
            self._model = model
            self._temperature = temperature
            self._mode = mode
            self._enabled = enabled
            self._history.clear()   # Clear memory on provider switch
            logger.info(f"✅ LLM provider set: {provider_name} / {model} (mode={mode})")
        except ImportError as e:
            raise RuntimeError(
                f"Provider '{provider_name}' SDK not installed. "
                f"Run: pip install {self._install_hint(provider_name)}\n{e}"
            )
        except Exception as e:
            raise RuntimeError(f"Failed to initialize provider '{provider_name}': {e}")

    def disable(self) -> None:
        self._enabled = False
        self._provider = None
        logger.info("LLM service disabled.")

    def _install_hint(self, provider: str) -> str:
        return {"groq": "groq", "openai": "openai", "gemini": "google-generativeai",
                "claude": "anthropic", "deepseek": "openai"}.get(provider, provider)

    # ── Status ────────────────────────────────────────────────────────────────

    @property
    def is_ready(self) -> bool:
        return self._enabled and self._provider is not None

    def status(self) -> dict:
        return {
            "enabled": self._enabled,
            "provider": self._provider_name,
            "model": self._model,
            "mode": self._mode,
            "ready": self.is_ready,
            "history_length": len(self._history),
        }

    # ── Conversation Memory ───────────────────────────────────────────────────

    def add_to_history(self, role: str, content: str) -> None:
        self._history.append({"role": role, "content": content})

    def clear_history(self) -> None:
        self._history.clear()

    def _build_messages(self, system: str, user_prompt: str) -> list[dict]:
        msgs: list[dict] = [{"role": "system", "content": system}]
        msgs.extend(self._history)
        msgs.append({"role": "user", "content": user_prompt})
        return msgs

    # ── Intent Classification (used by CommandService fallback) ───────────────

    async def classify_intent(self, text: str, available_intents: list[dict]) -> dict | None:
        """
        Ask the LLM which intent best matches `text`, using conversation history for context.
        Returns a dict: {"intent": "name", "params": {...}} or None if no match.
        """
        if not self.is_ready:
            return None
        try:
            # Construct available intents JSON including parameter definitions
            intents_json = json.dumps([
                {"name": i["name"], "description": i["description"], "parameters": i.get("param_names", [])} 
                for i in available_intents
            ])
            
            prompt = f"Available intents:\n{intents_json}\n\nLatest user command: \"{text}\"\n\nBased on the conversation history (if any) and the latest command, which intent matches best, and what are its resolved parameters?"
            
            # Inject history for pronoun resolution
            from app.services.context_manager import context_manager
            system_prompt = _INTENT_CLASSIFIER_SYSTEM
            state_injection = context_manager.get_system_prompt_injection()
            if state_injection:
                system_prompt += f"\n\n{state_injection}"
                
            msgs = [{"role": "system", "content": system_prompt}]
            msgs.extend(self._history)
            msgs.append({"role": "user", "content": prompt})
            
            raw = await self._provider.chat(msgs, temperature=0.0, max_tokens=150)
            
            # Strip markdown code blocks if the LLM hallucinated them despite instructions
            if raw.startswith("```"):
                raw = "\n".join(raw.split("\n")[1:-1])
                
            parsed = json.loads(raw.strip())
            intent = parsed.get("intent")
            confidence = parsed.get("confidence", 0.0)
            
            if intent and confidence >= 0.6:
                logger.info(f"LLM contextually classified '{text}' → '{intent}' (params: {parsed.get('params', {})}, confidence={confidence})")
                return parsed
        except Exception as e:
            logger.warning(f"LLM intent classification failed: {e}")
        return None

    # ── Direct Chat ───────────────────────────────────────────────────────────

    async def chat(self, prompt: str) -> str:
        """Send a message and get a full response. Saves to conversation memory."""
        if not self.is_ready:
            raise RuntimeError("LLM provider not configured. Go to Settings → AI Assistant.")
        try:
            msgs = self._build_messages(_CHAT_SYSTEM, prompt)
            reply = await self._provider.chat(msgs, temperature=self._temperature)
            # Save both sides to memory
            self.add_to_history("user", prompt)
            self.add_to_history("assistant", reply)
            return reply
        except Exception as e:
            logger.error(f"LLM chat failed: {e}")
            raise

    async def stream_chat(self, prompt: str) -> AsyncGenerator[str, None]:
        """Stream a response token-by-token. Saves to conversation memory when complete."""
        if not self.is_ready:
            raise RuntimeError("LLM provider not configured.")
        try:
            msgs = self._build_messages(_CHAT_SYSTEM, prompt)
            full_reply = ""
            async for token in self._provider.stream_chat(msgs, temperature=self._temperature):
                full_reply += token
                yield token
            # Save after stream completes
            self.add_to_history("user", prompt)
            self.add_to_history("assistant", full_reply)
        except Exception as e:
            logger.error(f"LLM stream failed: {e}")
            raise

    # ── Available Providers ───────────────────────────────────────────────────

    @staticmethod
    def get_all_providers() -> list[dict]:
        """Return all provider metadata for the Settings UI."""
        return [
            {"id": pid, "name": pid.title(), "models": info["models"]}
            for pid, info in PROVIDER_REGISTRY.items()
        ]


# ─── App-Wide Singleton ───────────────────────────────────────────────────────
llm_service = LLMService()
