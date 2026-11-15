from __future__ import annotations

import base64
import ctypes
import json
import os
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, Field, model_validator

from app.services.library_repository import _connection, init_db


class Settings(BaseModel):
    provider: Literal["ollama", "api", "local"] = "ollama"
    ollama_url: str = "http://127.0.0.1:11434"
    ollama_model: str = Field(default="qwen2.5:3b", max_length=150)
    embedding_model: str = Field(default="nomic-embed-text", min_length=1, max_length=150)
    embeddings_enabled: bool = True
    api_url: str = Field(default="", max_length=500)
    api_model: str = Field(default="", max_length=150)
    api_key: str | None = Field(default=None, max_length=1000)
    clear_api_key: bool = False
    openalex_api_key: str | None = Field(default=None, max_length=1000)
    clear_openalex_api_key: bool = False
    auto_analyze: bool = True
    allow_external_ai: bool = False

    @model_validator(mode="after")
    def endpoints(self):
        local = urlparse(self.ollama_url)
        if local.scheme != "http" or local.hostname not in {"127.0.0.1", "localhost", "::1"} or local.username or local.query or local.fragment:
            raise ValueError("Ollama must use a local HTTP address, for example http://127.0.0.1:11434.")
        if self.api_url:
            url = urlparse(self.api_url)
            if url.scheme != "https" or not url.hostname or url.username or url.query or url.fragment:
                raise ValueError("Use an HTTPS chat-completions endpoint without credentials or query parameters.")
        if self.provider == "api" and (not self.api_url or not self.api_model or not self.allow_external_ai):
            raise ValueError("API mode needs an endpoint, a model, and consent to send paper passages to that provider.")
        return self


def _crypt(data: bytes, decrypt=False) -> bytes:
    """Windows DPAPI ties saved credentials to this Windows account."""
    if os.name != "nt":
        raise ValueError("Persistent API keys are supported on Windows. Use local Ollama here.")
    from ctypes import wintypes
    class Blob(ctypes.Structure):
        _fields_ = [("size", wintypes.DWORD), ("data", ctypes.POINTER(ctypes.c_ubyte))]
    buffer = ctypes.create_string_buffer(data)
    source = Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    output = Blob()
    crypt = ctypes.WinDLL("crypt32", use_last_error=True)
    if decrypt:
        ok = crypt.CryptUnprotectData(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(output))
    else:
        ok = crypt.CryptProtectData(ctypes.byref(source), "LitLens", None, None, None, 1, ctypes.byref(output))
    if not ok:
        raise ValueError("Windows could not protect or unlock the saved API key. Enter the key again.")
    try:
        return ctypes.string_at(output.data, output.size)
    finally:
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.LocalFree.argtypes = [ctypes.c_void_p]
        kernel.LocalFree(ctypes.cast(output.data, ctypes.c_void_p))


def _stored() -> dict:
    init_db()
    with _connection() as db:
        db.execute("CREATE TABLE IF NOT EXISTS user_settings (id INTEGER PRIMARY KEY, value TEXT NOT NULL)")
        row = db.execute("SELECT value FROM user_settings WHERE id=1").fetchone()
    return json.loads(row["value"]) if row else {}


def get_settings(include_secret=False) -> dict:
    stored = _stored()
    secret_fields = {"api_key", "clear_api_key", "openalex_api_key", "clear_openalex_api_key"}
    result = Settings().model_dump(exclude=secret_fields)
    result.update({key: value for key, value in stored.items() if key not in {"protected_key", "protected_openalex_key"} | secret_fields})
    result["has_api_key"] = bool(stored.get("protected_key"))
    result["has_openalex_api_key"] = bool(stored.get("protected_openalex_key"))
    if include_secret:
        result["api_key"] = _crypt(base64.b64decode(stored["protected_key"]), True).decode() if stored.get("protected_key") else None
    return result


def save_settings(settings: Settings) -> dict:
    stored = _stored()
    value = settings.model_dump(exclude={"api_key", "clear_api_key", "openalex_api_key", "clear_openalex_api_key"})
    if not settings.clear_api_key and stored.get("protected_key"):
        value["protected_key"] = stored["protected_key"]
    if settings.api_key:
        value["protected_key"] = base64.b64encode(_crypt(settings.api_key.encode())).decode()
    if not settings.clear_openalex_api_key and stored.get("protected_openalex_key"):
        value["protected_openalex_key"] = stored["protected_openalex_key"]
    if settings.openalex_api_key:
        value["protected_openalex_key"] = base64.b64encode(_crypt(settings.openalex_api_key.encode())).decode()
    with _connection() as db:
        db.execute("INSERT OR REPLACE INTO user_settings VALUES (1, ?)", (json.dumps(value),))
    return get_settings()


def get_openalex_key() -> str | None:
    from app.services.user_context import profile_directory
    if profile_directory.get() is not None:
        value = _stored().get("protected_openalex_key")
        if value:
            return _crypt(base64.b64decode(value), True).decode()
    return os.getenv("OPENALEX_API_KEY") or None
