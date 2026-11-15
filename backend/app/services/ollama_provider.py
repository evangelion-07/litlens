from __future__ import annotations

import httpx


class OllamaChat:
    def __init__(self, endpoint: str, model: str):
        self.endpoint = endpoint.rstrip("/")
        self.model = model

    async def complete(self, system_prompt: str, user_prompt: str) -> str:
        async with httpx.AsyncClient(timeout=httpx.Timeout(180, connect=3), trust_env=False) as client:
            response = await client.post(self.endpoint + "/api/chat", json={
                "model": self.model, "stream": False,
                "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
                "options": {"temperature": 0, "num_ctx": 8192, "num_predict": 3000},
                **({"format": "json"} if "JSON" in system_prompt else {}),
            })
            response.raise_for_status()
            content = response.json().get("message", {}).get("content", "")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("Ollama returned an empty answer.")
        return content.strip()


class OllamaEmbeddings:
    def __init__(self, endpoint: str, model: str):
        self.endpoint = endpoint.rstrip("/")
        self.model = model
        self.cache_key = self.endpoint + "/" + model

    async def embed(self, texts):
        vectors = []
        async with httpx.AsyncClient(timeout=httpx.Timeout(120, connect=3), trust_env=False) as client:
            for start in range(0, len(texts), 16):
                response = await client.post(self.endpoint + "/api/embed", json={
                    "model": self.model, "input": list(texts[start:start + 16]), "truncate": False,
                })
                response.raise_for_status()
                vectors.extend(response.json()["embeddings"])
        return vectors
