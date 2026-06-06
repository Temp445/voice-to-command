"""Ollama Adapter for local LLM inference."""
from __future__ import annotations

import base64
from typing import AsyncGenerator

import ollama
from loguru import logger

from app.services.llm.base import LLMProvider

_MODELS = [
    "llama3.2",
    "llama3.1",
    "qwen2.5:3b",
    "qwen2.5:1.5b",
    "mistral",
    "phi3",
]


class OllamaAdapter(LLMProvider):
    def __init__(self, api_key: str, model: str = "llama3.2"):
        """
        api_key is repurposed here as the host URL for Ollama.
        If not provided or not a valid URL, it defaults to the local instance.
        """
        self._is_custom_proxy = False
        self._custom_proxy_url = ""
        
        host = api_key if api_key and api_key.startswith("http") else "http://localhost:11434"
        
        # Detect if the user provided their custom FastAPI proxy endpoint
        if host.endswith("/chat"):
            self._is_custom_proxy = True
            self._custom_proxy_url = host
            self._client = None
        else:
            self._client = ollama.AsyncClient(host=host)
            
        self._model_name = model

    @property
    def name(self) -> str:
        return "Ollama"

    @property
    def available_models(self) -> list[str]:
        return _MODELS

    def _to_ollama_format(self, messages: list[dict]) -> list[dict]:
        """Convert standard messages to Ollama format."""
        formatted_messages = []
        for m in messages:
            role = m["role"]
            content = m["content"]
            
            # Map 'assistant' to 'model' or keep 'assistant' depending on what ollama API expects
            # ollama API expects: system, user, assistant
            if role == "system":
                formatted_messages.append({"role": "system", "content": content})
            elif role == "user":
                if isinstance(content, list):
                    # Handle multimodal input
                    text_parts = []
                    images = []
                    for part in content:
                        if part.get("type") == "text":
                            text_parts.append(part.get("text", ""))
                        elif part.get("type") == "image_url":
                            url = part.get("image_url", {}).get("url", "")
                            if url.startswith("data:"):
                                # Extract base64 data
                                b64_data = url.split(",")[1]
                                images.append(b64_data)
                    
                    msg = {"role": "user", "content": "\n".join(text_parts)}
                    if images:
                        msg["images"] = images
                    formatted_messages.append(msg)
                else:
                    formatted_messages.append({"role": "user", "content": content})
            elif role == "assistant":
                formatted_messages.append({"role": "assistant", "content": content})
                
        return formatted_messages

    async def chat(self, messages: list[dict], *, temperature: float = 0.7, max_tokens: int = 1024) -> str:
        try:
            # Connect to user's custom FastAPI proxy
            if self._is_custom_proxy:
                import httpx
                # Extract user message and system message
                user_msg = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
                system_msg = next((m["content"] for m in messages if m["role"] == "system"), "")
                
                # Prepend system message to user prompt since proxy only takes one string
                prompt = f"{system_msg}\n\nUser: {user_msg}" if system_msg else user_msg
                
                async with httpx.AsyncClient(timeout=60.0) as client:
                    resp = await client.post(self._custom_proxy_url, params={"prompt": prompt})
                    resp.raise_for_status()
                    data = resp.json()
                    prompt_tokens = data.get("prompt_eval_count", 0)
                    completion_tokens = data.get("eval_count", 0)
                    logger.info(f"🤖 LLM Usage (Proxy): Model=custom-proxy, Tokens=({prompt_tokens} prompt, {completion_tokens} completion)")
                    # The user's proxy returns the Ollama generate response
                    return data.get("response", str(data))
                    
            # Connect natively to Ollama
            formatted_messages = self._to_ollama_format(messages)
            options = {
                "temperature": temperature,
                "num_predict": max_tokens
            }
            
            response = await self._client.chat(
                model=self._model_name,
                messages=formatted_messages,
                options=options
            )
            prompt_tokens = response.get("prompt_eval_count", 0)
            completion_tokens = response.get("eval_count", 0)
            logger.info(f"🤖 LLM Usage: Model={self._model_name}, Tokens=({prompt_tokens} prompt, {completion_tokens} completion)")
            return response.get("message", {}).get("content", "")
            
        except Exception as e:
            logger.error(f"Ollama chat error: {e}")
            raise

    async def stream_chat(self, messages: list[dict], *, temperature: float = 0.7, max_tokens: int = 1024) -> AsyncGenerator[str, None]:
        try:
            # Connect to user's custom FastAPI proxy (fallback to blocking chat since proxy doesn't stream)
            if self._is_custom_proxy:
                yield await self.chat(messages, temperature=temperature, max_tokens=max_tokens)
                return
                
            formatted_messages = self._to_ollama_format(messages)
            options = {
                "temperature": temperature,
                "num_predict": max_tokens
            }
            
            prompt_tokens = 0
            completion_tokens = 0
            async for chunk in await self._client.chat(
                model=self._model_name,
                messages=formatted_messages,
                options=options,
                stream=True
            ):
                if "prompt_eval_count" in chunk:
                    prompt_tokens = chunk["prompt_eval_count"]
                if "eval_count" in chunk:
                    completion_tokens = chunk["eval_count"]
                    logger.info(f"🤖 LLM Usage: Model={self._model_name}, Tokens=({prompt_tokens} prompt, {completion_tokens} completion)")
                    
                content = chunk.get("message", {}).get("content", "")
                if content:
                    yield content
                    
        except Exception as e:
            logger.error(f"Ollama stream error: {e}")
            raise
