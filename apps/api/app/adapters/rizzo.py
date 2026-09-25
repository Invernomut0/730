"""HTTP adapter for a local Rizzo Flow typed-decision endpoint."""

from __future__ import annotations

from typing import Any, Protocol

import httpx

from app.core.config import Settings


class RizzoFlowUnavailable(RuntimeError):
    """Raised when the optional local Rizzo Flow service cannot decide."""


class RizzoFlowProvider(Protocol):
    """Provider contract for atomic batches of schema-constrained decisions."""

    @property
    def model_id(self) -> str: ...

    async def decide_batch(self, decisions: list[dict[str, Any]]) -> list[dict[str, Any]]: ...


class RizzoFlowAdapter:
    """Bounded client for ``POST /decisions`` on a local Rizzo Flow instance.

    The endpoint receives ``{"decisions": [...]}`` and must return the same
    number of JSON objects as ``{"decisions": [{"output": {...}}, ...]}``.
    Only the caller-provided prompt and schema are transported; no application
    logs are emitted by this adapter.
    """

    def __init__(self, settings: Settings) -> None:
        self._enabled = settings.rizzo_flow_enabled
        self._base_url = str(settings.rizzo_flow_base_url).rstrip("/") if settings.rizzo_flow_base_url else None

    @property
    def model_id(self) -> str:
        """Return a stable provenance identifier for the local flow."""
        return "rizzo-flow"

    async def decide_batch(self, decisions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Submit a non-empty typed decision batch and return its JSON outputs."""
        if not self._enabled or not self._base_url:
            raise RizzoFlowUnavailable("Rizzo Flow is disabled or not configured.")
        if not decisions:
            return []
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.post(f"{self._base_url}/decisions", json={"decisions": decisions})
                response.raise_for_status()
                payload = response.json()
            outputs = payload["decisions"]
            if not isinstance(outputs, list) or len(outputs) != len(decisions):
                raise ValueError("Decision count does not match request.")
            return [item["output"] for item in outputs if isinstance(item, dict) and isinstance(item.get("output"), dict)]
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as error:
            raise RizzoFlowUnavailable("Rizzo Flow batch decision failed.") from error