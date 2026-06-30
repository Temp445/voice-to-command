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
import asyncio
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
    "deepseek": {"class": "DeepSeekAdapter", "module": "app.services.llm.adapters.deepseek_adapter", "models": ["deepseek-v4-flash", "deepseek-v4-pro"]},
    "ollama":   {"class": "OllamaAdapter",   "module": "app.services.llm.adapters.ollama_adapter",   "models": ["llama3.2", "llama3.1", "qwen2.5:3b", "qwen2.5:1.5b", "mistral", "phi3"]},
}

# System prompt used when classifying intents
_INTENT_CLASSIFIER_SYSTEM = """You are ACE, a zero-latency desktop command router. Your ONLY function is to map
the user's spoken command to exactly one intent from the provided list and extract
its parameters. You operate at enterprise speed — every millisecond matters.

RULES (non-negotiable):
1. Reply ONLY with a valid JSON object on a single line. No markdown. No explanation.
   Format: {"intent":"<name>","confidence":<0.0–1.0>,"params":{"<key>":"<value>"}}
2. Resolve pronouns (it/this/that/them) using conversation history before choosing intent.
3. If the user gives a noun after an action (e.g., "payroll" after opening a site),
   repeat the last action with the new noun as the parameter.
4. If the command contains a navigation verb (open/launch/go to/visit/start) followed
   by a word matching a known site keyword, return intent "open_website_shortcut" with
   the matched URL as the param — even if not in the formal intent list.
5. For ambiguous short commands (1–2 words), bias toward the last executed intent's domain.
6. Confidence < 0.6 → return {"intent":null,"confidence":0.0,"params":{}}
7. Never guess. Never hallucinate intent names not in the provided list.
8. max_tokens for your response: 80. Be terse.
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
        self.last_error: str | None = "Not configured."
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
            self.last_error = None
            self._history.clear()   # Clear memory on provider switch
            logger.info(f"✅ LLM provider set: {provider_name} / {model} (mode={mode})")
        except ImportError as e:
            msg = f"Provider '{provider_name}' SDK not installed. Run: pip install {self._install_hint(provider_name)}"
            self.last_error = msg
            raise RuntimeError(msg)
        except Exception as e:
            msg = f"Failed to initialize provider '{provider_name}': {e}"
            self.last_error = msg
            raise RuntimeError(msg)

    def disable(self, reason: str = "Not configured.") -> None:
        self._enabled = False
        self._provider = None
        self.last_error = reason
        logger.info(f"LLM service disabled: {reason}")

    def _install_hint(self, provider: str) -> str:
        return {"groq": "groq", "openai": "openai", "gemini": "google-generativeai",
                "claude": "anthropic", "deepseek": "openai", "ollama": "ollama"}.get(provider, provider)

    def _handle_llm_error(self, e: Exception) -> None:
        """Centralized error handler to surface quota/rate limits to the user."""
        err_msg = str(e).lower()
        if any(keyword in err_msg for keyword in ["429", "quota", "limit", "resourceexhausted", "too many requests"]):
            error_text = "LLM Quota or Rate Limit Exceeded. Please check your API key tier."
            logger.error(f"Broadcasting quota error to UI and OS: {error_text}")
            
            # 1. Native OS Notification
            try:
                from winsdk.windows.ui.notifications import ToastNotificationManager, ToastNotification, ToastTemplateType
                
                toast_xml = ToastNotificationManager.get_template_content(ToastTemplateType.TOAST_TEXT02)
                text_nodes = toast_xml.get_elements_by_tag_name("text")
                text_nodes[0].append_child(toast_xml.create_text_node("ACE AI Limit Exceeded"))
                text_nodes[1].append_child(toast_xml.create_text_node(error_text))
                
                toast = ToastNotification(toast_xml)
                ToastNotificationManager.create_toast_notifier("ACE Controller").show(toast)
            except Exception as pe:
                logger.error(f"Winsdk notification failed: {pe}")
                
            # 2. Frontend UI Toast
            import asyncio
            from app.websocket.manager import ws_manager
            
            async def notify_frontend():
                try:
                    await ws_manager.broadcast("system_error", {"error": error_text})
                except Exception as wse:
                    logger.error(f"Failed to broadcast system_error: {wse}")
                    
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(notify_frontend())
            except RuntimeError:
                asyncio.run(notify_frontend())

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
        import datetime
        current_time = datetime.datetime.now().strftime("%A, %B %d, %Y %I:%M %p")
        system += f"\n\nThe current date and time is: {current_time}."
        
        from app.services.context_state import get_context
        ctx = get_context().get_all()
        # Only inject if there's meaningful context (not all None)
        if any(v is not None for v in ctx.values()):
            import json
            system += f"\n\n[SYSTEM CONTEXT STATE]\n{json.dumps(ctx, indent=2)}\nUse this state to resolve ambiguous pronouns (it, this, that)."
        
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
            
            # Build context injection — injected into the USER message, NOT the system prompt.
            # Keeping the system prompt (_INTENT_CLASSIFIER_SYSTEM) byte-for-byte identical
            # across calls lets Gemini's implicit server-side cache activate, cutting
            # first-token latency by 30–60% on repeated commands.
            from app.services.context_manager import context_manager
            state_injection = context_manager.get_system_prompt_injection()
            context_prefix = f"[Context: {state_injection}]\n\n" if state_injection else ""

            # Inject live page context so the LLM knows what's on screen
            try:
                from app.services.page_context_service import page_context_service as _pcs
                _snap = _pcs.get_cached_snapshot()
                if _snap:
                    context_prefix += f"[SCREEN CONTEXT]\n{_snap.summary_for_llm()}\n\n"
            except Exception:
                pass


            prompt = (
                f"{context_prefix}"
                f"Available intents:\n{intents_json}\n\n"
                f"Latest command: \"{text}\"\n\n"
                f"Which intent matches best? Reply with JSON only."
            )

            msgs = [{"role": "system", "content": _INTENT_CLASSIFIER_SYSTEM}]  # static — cacheable
            msgs.extend(self._history)
            msgs.append({"role": "user", "content": prompt})
            
            # Timeout set to 5.0 seconds to keep interaction responsive
            raw = await asyncio.wait_for(
                self._provider.chat(msgs, temperature=0.0, max_tokens=150),
                timeout=5.0
            )
            
            # Strip markdown code blocks if the LLM hallucinated them despite instructions
            if raw.startswith("```"):
                raw = "\n".join(raw.split("\n")[1:-1])
                
            parsed = json.loads(raw.strip())
            intent = parsed.get("intent")
            confidence = parsed.get("confidence", 0.0)
            
            if intent and confidence >= 0.6:
                logger.info(f"LLM contextually classified '{text}' → '{intent}' (params: {parsed.get('params', {})}, confidence={confidence})")
                return parsed
        except asyncio.TimeoutError:
            logger.warning(f"LLM intent classification timed out after 5.0s")
        except Exception as e:
            logger.warning(f"LLM intent classification failed: {e}")
            self._handle_llm_error(e)
        return None

    # ── Direct Chat ───────────────────────────────────────────────────────────

    async def chat(self, prompt: str) -> str:
        """Send a message and get a full response. Saves to conversation memory."""
        if not self.is_ready:
            raise RuntimeError("LLM provider not configured. Go to Settings → AI Assistant.")
        try:
            msgs = self._build_messages(_CHAT_SYSTEM, prompt)
            # Timeout set to 8.0 seconds for general chat
            reply = await asyncio.wait_for(
                self._provider.chat(msgs, temperature=self._temperature),
                timeout=8.0
            )
            # Save both sides to memory
            self.add_to_history("user", prompt)
            self.add_to_history("assistant", reply)
            return reply
        except asyncio.TimeoutError:
            logger.error("LLM chat timed out after 8.0s")
            raise RuntimeError("Request to AI Assistant timed out. Please try again.")
        except Exception as e:
            logger.error(f"LLM chat failed: {e}")
            self._handle_llm_error(e)
            raise
            
    async def rewrite_for_speech(self, raw_result: str, original_command: str) -> str:
        """Rewrite a hardcoded technical result into a conversational sentence."""
        if not self.is_ready:
            return raw_result
            
        sys_prompt = (
            "You are ACE, a desktop voice assistant. Rewrite the provided technical result "
            "into a short, friendly, and natural conversational sentence that will be spoken aloud to the user. "
            "CRITICAL RULES:\n"
            "1. Do NOT include any markdown, emojis, or explanations. Keep it under 2 sentences.\n"
            "2. If the technical result explicitly gives the user a multiple-choice option (e.g., 'Say 1 for X, or 2 for Y', or 'open a file, folder, application, or search Google'), "
            "you MUST preserve those exact trigger words ('1', '2', 'file', 'folder', 'application', 'search Google'). Do NOT use synonyms for the choices.\n"
            "3. NEVER invent or add multiple-choice options, questions, or follow-ups if the technical result does not explicitly contain them.\n"
            "4. If the technical result contains a URL, do NOT read out 'https://', 'http://', or 'www.'. Just say the core domain name naturally (e.g., say 'payroll acesoftcloud' instead of 'https://payroll-acesoftcloud.netlify.app/')."
        )
        user_prompt = f"User said: '{original_command}'\nTechnical result: '{raw_result}'\n\nRewrite the result:"
        
        try:
            msgs = self._build_messages(sys_prompt, user_prompt)
            # Strict timeout of 5.0 seconds. Speech synthesis must be fast.
            reply = await asyncio.wait_for(
                self._provider.chat(msgs, temperature=self._temperature),
                timeout=5.0
            )
            return reply.strip()
        except asyncio.TimeoutError:
            logger.warning("LLM rewrite timed out after 5.0s, falling back to raw result")
            return raw_result
        except Exception as e:
            logger.warning(f"LLM rewrite failed, falling back to raw result: {e}")
            self._handle_llm_error(e)
            return raw_result

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