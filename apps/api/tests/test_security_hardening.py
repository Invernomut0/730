import logging

import pytest

from app.core.log_redaction import RedactingFilter, redact_log_context
from app.services.auth_rate_limit import clear_login_attempts, consume_login_attempt, login_rate_limit_key


def test_log_redaction_removes_sensitive_context_recursively() -> None:
    context = {"password": "do-not-log", "nested": {"fiscal_code": "RSSMRA00A01H501U"}, "status": "ok"}

    assert redact_log_context(context) == {"password": "[REDACTED]", "nested": {"fiscal_code": "[REDACTED]"}, "status": "ok"}
    record = logging.LogRecord("healthdocs", logging.INFO, __file__, 1, {"token": "secret"}, (), None)
    assert RedactingFilter().filter(record)
    assert record.msg == {"token": "[REDACTED]"}


@pytest.mark.asyncio
async def test_login_rate_limit_uses_redis_and_resets_after_success() -> None:
    redis_url = "redis://redis:6379/0"
    client_host = "198.51.100.42"
    await clear_login_attempts(redis_url, client_host)
    try:
        assert await consume_login_attempt(redis_url, client_host, limit=2, window_seconds=60)
        assert await consume_login_attempt(redis_url, client_host, limit=2, window_seconds=60)
        assert not await consume_login_attempt(redis_url, client_host, limit=2, window_seconds=60)
        assert login_rate_limit_key(client_host) != client_host
        await clear_login_attempts(redis_url, client_host)
        assert await consume_login_attempt(redis_url, client_host, limit=2, window_seconds=60)
    finally:
        await clear_login_attempts(redis_url, client_host)