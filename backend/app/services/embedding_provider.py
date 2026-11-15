from __future__ import annotations

import os
from collections.abc import Sequence
from typing import Protocol

import httpx


class EmbeddingProvider(Protocol):
    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Return one embedding vector for each input text."""


class EmbeddingProviderError(RuntimeError):
    """The configured embedding endpoint returned an unusable response."""


class OpenAICompatibleEmbeddingProvider:
    """Adapter for any endpoint that implements the common embeddings response shape."""

    def __init__(self, endpoint: str, model: str, api_key: str | None = None):
        self.endpoint = endpoint
        self.model = model
        self.api_key = api_key
        self.cache_key = endpoint + "/" + model

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(20.0, connect=5.0)) as client:
                response = await client.post(
                    self.endpoint,
                    headers=headers,
                    json={"model": self.model, "input": list(texts)},
                )
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise EmbeddingProviderError("The embedding provider request failed.") from exc

        entries = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(entries, list) or len(entries) != len(texts):
            raise EmbeddingProviderError("The embedding provider returned the wrong number of vectors.")
        try:
            ordered = sorted(entries, key=lambda item: item.get("index", 0))
            vectors = [[float(value) for value in item["embedding"]] for item in ordered]
        except (KeyError, TypeError, ValueError) as exc:
            raise EmbeddingProviderError("The embedding provider returned malformed vectors.") from exc
        if not vectors or not vectors[0] or any(len(vector) != len(vectors[0]) for vector in vectors):
            raise EmbeddingProviderError("The embedding provider returned inconsistent vector dimensions.")
        return vectors


def configured_embedding_provider() -> EmbeddingProvider | None:
    from app.services.user_context import profile_directory
    if profile_directory.get() is not None:
        from app.services.settings import get_settings
        from app.services.ollama_provider import OllamaEmbeddings
        settings = get_settings()
        return OllamaEmbeddings(settings["ollama_url"], settings["embedding_model"]) if settings["embeddings_enabled"] else None
    endpoint = os.getenv("EMBEDDING_API_URL", "").strip()
    model = os.getenv("EMBEDDING_MODEL", "").strip()
    if not endpoint or not model:
        return None
    return OpenAICompatibleEmbeddingProvider(
        endpoint=endpoint,
        model=model,
        api_key=os.getenv("EMBEDDING_API_KEY") or None,
    )
