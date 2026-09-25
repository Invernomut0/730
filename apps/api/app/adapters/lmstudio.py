"""Adapter for LM Studio's local OpenAI-compatible API."""

from __future__ import annotations

import json
import math
from typing import Any, Protocol

import httpx

from app.core.config import Settings


class LLMUnavailable(RuntimeError):
    """Raised when the local model endpoint cannot serve a request."""


class LLMProvider(Protocol):
    @property
    def model_id(self) -> str: ...

    async def models(self) -> list[str]: ...
    async def structured_completion(self, prompt: str, schema: dict[str, Any]) -> dict[str, Any]: ...


class EmbeddingProvider(Protocol):
    """Local vector provider for candidate retrieval only."""

    @property
    def embedding_model_id(self) -> str: ...

    async def embed(self, texts: list[str]) -> list[list[float]]: ...


def parse_embedding_response(payload: dict[str, Any], expected_count: int) -> list[list[float]]:
    """Validate an OpenAI-compatible embedding response without retaining inputs."""
    items = payload["data"]
    if not isinstance(items, list) or len(items) != expected_count:
        raise ValueError("Embedding response count does not match input.")
    ordered: list[list[float] | None] = [None] * expected_count
    for item in items:
        if not isinstance(item, dict):
            raise TypeError("Embedding item must be an object.")
        index = item["index"]
        values = item["embedding"]
        if not isinstance(index, int) or isinstance(index, bool) or not 0 <= index < expected_count:
            raise ValueError("Embedding response contains an invalid index.")
        if ordered[index] is not None or not isinstance(values, list) or not values:
            raise ValueError("Embedding response contains an invalid vector.")
        if any(not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value) for value in values):
            raise ValueError("Embedding vector must contain finite numeric values.")
        ordered[index] = [float(value) for value in values]
    if any(vector is None for vector in ordered):
        raise ValueError("Embedding response is missing an input vector.")
    vectors = [vector for vector in ordered if vector is not None]
    if len({len(vector) for vector in vectors}) != 1:
        raise ValueError("Embedding vectors must have the same dimension.")
    return vectors


def parse_structured_completion_content(content: str) -> dict[str, Any]:
    """Parse a JSON object, accepting an optional Markdown JSON fence."""
    normalized = content.strip()
    if normalized.startswith("```"):
        lines = normalized.splitlines()
        if len(lines) < 3 or not lines[-1].strip().startswith("```"):
            raise ValueError("Structured completion has an incomplete Markdown fence.")
        normalized = "\n".join(lines[1:-1]).strip()
    payload = json.loads(normalized)
    if not isinstance(payload, dict):
        raise TypeError("Structured completion must be a JSON object.")
    return payload


def structured_completion_payload(model: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
    """Build a text-mode request that still gives LM Studio the JSON schema."""
    schema_text = json.dumps(schema, ensure_ascii=False, separators=(",", ":"))
    return {
        "model": model,
        "messages": [{"role": "user", "content": f"{prompt}\n\nReturn only one JSON object matching this schema:\n{schema_text}"}],
        # LM Studio's JSON-schema mode can return an empty `content` field
        # for reasoning models. Pydantic still validates this JSON locally.
        "response_format": {"type": "text"},
        "temperature": 0,
    }


class LMStudioProvider:
    """Small, bounded-retry client isolated from domain services."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @property
    def model_id(self) -> str:
        """Return the configured primary model identifier for provenance."""
        return self._settings.lmstudio_main_model

    @property
    def embedding_model_id(self) -> str:
        """Return the configured local embedding model for provenance."""
        return self._settings.lmstudio_embedding_model

    async def models(self) -> list[str]:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(f"{str(self._settings.lmstudio_base_url).rstrip('/')}/models")
                response.raise_for_status()
                return [str(item["id"]) for item in response.json().get("data", [])]
        except (httpx.HTTPError, KeyError, TypeError) as error:
            raise LLMUnavailable("LM Studio model discovery failed.") from error

    async def structured_completion(self, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        if not self._settings.lmstudio_main_model:
            raise LLMUnavailable("No main LM Studio model is configured.")
        headers = {"Authorization": f"Bearer {self._settings.lmstudio_api_token}"} if self._settings.lmstudio_api_token else {}
        payload = structured_completion_payload(self._settings.lmstudio_main_model, prompt, schema)
        try:
            async with httpx.AsyncClient(timeout=self._settings.lmstudio_request_timeout_seconds) as client:
                response = await client.post(f"{str(self._settings.lmstudio_base_url).rstrip('/')}/chat/completions", json=payload, headers=headers)
                response.raise_for_status()
                content = response.json()["choices"][0]["message"]["content"]
                if not isinstance(content, str):
                    raise TypeError("Non-string model output")
                return parse_structured_completion_content(content)
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as error:
            raise LLMUnavailable("LM Studio structured completion failed.") from error

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Create validated vectors locally for retrieval, never link confirmation."""
        if not self._settings.lmstudio_embedding_model:
            raise LLMUnavailable("No LM Studio embedding model is configured.")
        if not texts or any(not text.strip() for text in texts):
            raise ValueError("Embedding input must contain one or more non-empty texts.")
        headers = {"Authorization": f"Bearer {self._settings.lmstudio_api_token}"} if self._settings.lmstudio_api_token else {}
        payload = {
            "model": self._settings.lmstudio_embedding_model,
            "input": texts,
            "encoding_format": "float",
        }
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.post(f"{str(self._settings.lmstudio_base_url).rstrip('/')}/embeddings", json=payload, headers=headers)
                response.raise_for_status()
                return parse_embedding_response(response.json(), len(texts))
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as error:
            raise LLMUnavailable("LM Studio embedding request failed.") from error
