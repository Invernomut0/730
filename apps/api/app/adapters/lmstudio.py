"""Adapter for LM Studio's local OpenAI-compatible API."""

from __future__ import annotations

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


class LMStudioProvider:
    """Small, bounded-retry client isolated from domain services."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @property
    def model_id(self) -> str:
        """Return the configured primary model identifier for provenance."""
        return self._settings.lmstudio_main_model

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
        payload = {
            "model": self._settings.lmstudio_main_model,
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_schema", "json_schema": {"name": "extraction", "schema": schema}},
            "temperature": 0,
        }
        try:
            async with httpx.AsyncClient(timeout=45) as client:
                response = await client.post(f"{str(self._settings.lmstudio_base_url).rstrip('/')}/chat/completions", json=payload, headers=headers)
                response.raise_for_status()
                content = response.json()["choices"][0]["message"]["content"]
                if not isinstance(content, str):
                    raise TypeError("Non-string model output")
                return httpx.Response(200, content=content).json()
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as error:
            raise LLMUnavailable("LM Studio structured completion failed.") from error
