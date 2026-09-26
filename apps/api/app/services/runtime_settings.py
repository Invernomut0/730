"""Redis-backed local runtime controls for worker operations and model selection."""

from __future__ import annotations

import json

from arq import create_pool
from arq.connections import RedisSettings

from app.core.config import Settings

_RUNTIME_LLM_KEY = "healthdocs:runtime:llm"
_JOBS_PAUSED_KEY = "healthdocs:jobs:paused"
_LLM_FIELDS = {
    "lmstudio_main_model",
    "lmstudio_simple_model",
    "lmstudio_fallback_model",
    "lmstudio_relation_model",
    "rizzo_flow_enabled",
    "rizzo_flow_base_url",
}


async def runtime_settings(settings: Settings) -> Settings:
    """Return environment settings overlaid with non-secret local runtime choices."""
    try:
        redis = await create_pool(RedisSettings.from_dsn(settings.redis_url))
        raw = await redis.get(_RUNTIME_LLM_KEY)
        await redis.aclose()
        if not raw:
            return settings
        payload = json.loads(raw.decode() if isinstance(raw, bytes) else raw)
        if not isinstance(payload, dict):
            return settings
        return settings.model_copy(update={key: value for key, value in payload.items() if key in _LLM_FIELDS})
    except (OSError, json.JSONDecodeError):
        return settings


async def save_runtime_llm_settings(settings: Settings, updates: dict[str, object]) -> Settings:
    """Persist selected non-secret model settings and return their effective value."""
    effective = await runtime_settings(settings)
    payload = {
        field: str(value) if field == "rizzo_flow_base_url" and value is not None else value
        for field in _LLM_FIELDS
        for value in [getattr(effective, field)]
    }
    payload.update({key: value for key, value in updates.items() if key in _LLM_FIELDS})
    redis = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    try:
        await redis.set(_RUNTIME_LLM_KEY, json.dumps(payload))
    finally:
        await redis.aclose()
    return settings.model_copy(update=payload)


async def jobs_paused(settings: Settings) -> bool:
    """Tell workers whether new queued processing must remain paused."""
    try:
        redis = await create_pool(RedisSettings.from_dsn(settings.redis_url))
        paused = await redis.get(_JOBS_PAUSED_KEY)
        await redis.aclose()
        return bool(paused)
    except OSError:
        return False


async def set_jobs_paused(settings: Settings, paused: bool) -> int:
    """Pause/resume job consumption and return the number of discarded queued jobs."""
    redis = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    try:
        if paused:
            await redis.set(_JOBS_PAUSED_KEY, "1")
            return int(await redis.delete("arq:queue"))
        await redis.delete(_JOBS_PAUSED_KEY)
        return 0
    finally:
        await redis.aclose()
