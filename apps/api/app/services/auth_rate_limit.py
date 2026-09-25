"""Redis-backed login throttling without persisting client addresses in logs."""

from __future__ import annotations

import hashlib

from arq import create_pool
from arq.connections import RedisSettings
from redis.exceptions import RedisError


class LoginRateLimitUnavailable(RuntimeError):
    """Raised when authentication cannot safely consult Redis."""


def login_rate_limit_key(client_host: str) -> str:
    """Return an opaque, stable Redis key for a client address."""
    return f"auth:login:{hashlib.sha256(client_host.encode()).hexdigest()}"


async def consume_login_attempt(redis_url: str, client_host: str, limit: int, window_seconds: int) -> bool:
    """Record an attempt and report whether it remains within the fixed window."""
    try:
        redis = await create_pool(RedisSettings.from_dsn(redis_url))
        try:
            key = login_rate_limit_key(client_host)
            attempts = await redis.incr(key)
            if attempts == 1:
                await redis.expire(key, window_seconds)
            return attempts <= limit
        finally:
            await redis.aclose()
    except (OSError, RedisError) as error:
        raise LoginRateLimitUnavailable("Login rate limiting is unavailable.") from error


async def clear_login_attempts(redis_url: str, client_host: str) -> None:
    """Clear the client window after a successful login."""
    try:
        redis = await create_pool(RedisSettings.from_dsn(redis_url))
        try:
            await redis.delete(login_rate_limit_key(client_host))
        finally:
            await redis.aclose()
    except (OSError, RedisError) as error:
        raise LoginRateLimitUnavailable("Login rate limiting is unavailable.") from error