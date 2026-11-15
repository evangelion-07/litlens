from __future__ import annotations

import os
from typing import Protocol

import httpx


class LLMProvider(Protocol):
    async def complete(self, system_prompt: str, user_prompt: str) -> str:
        """Generate a response from the supplied instructions and evidence."""


class LLMProviderError(RuntimeError):
    """The configured language model endpoint returned an unusable response."""


class OpenAICompatibleLLMProvider:
    """Adapter for a configurable chat-completions endpoint."""

    def __init__(self, endpoint: str, model: str, api_key: str | None = None):
        self.endpoint = endpoint
        self.model = model
        self.api_key = api_key

    async def complete(self, system_prompt: str, user_prompt: str) -> str:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(45.0, connect=5.0)) as client:
                response = await client.post(
                    self.endpoint,
                    headers=headers,
                    json={
                        "model": self.model,
                        "temperature": 0.1,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                    },
                )
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise LLMProviderError("The language model request failed.") from exc

        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMProviderError("The language model returned an invalid response.") from exc
        if not isinstance(content, str) or not content.strip():
            raise LLMProviderError("The language model returned an empty response.")
        return content.strip()


def configured_llm_provider() -> LLMProvider | None:
    from app.services.user_context import profile_directory
    if profile_directory.get() is not None:
        from app.services.settings import get_settings
        from app.services.ollama_provider import OllamaChat
        settings = get_settings(include_secret=True)
        if settings["provider"] == "ollama":
            return OllamaChat(settings["ollama_url"], settings["ollama_model"])
        if settings["provider"] == "api" and settings["allow_external_ai"]:
            return OpenAICompatibleLLMProvider(settings["api_url"], settings["api_model"], settings.get("api_key"))
        return None
    endpoint = os.getenv("LLM_API_URL", "").strip()
    model = os.getenv("LLM_MODEL", "").strip()
    if not endpoint or not model:
        return None
    return OpenAICompatibleLLMProvider(
        endpoint=endpoint,
        model=model,
        api_key=os.getenv("LLM_API_KEY") or None,
    )
