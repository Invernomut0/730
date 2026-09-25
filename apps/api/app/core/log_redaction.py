"""Small, explicit redaction helpers for application log contexts."""

from __future__ import annotations

import logging
from typing import Any

_SENSITIVE_KEYS = {"password", "secret", "token", "authorization", "fiscal_code", "content", "text"}
_REDACTED = "[REDACTED]"


def redact_log_context(value: Any, key: str | None = None) -> Any:
    """Recursively remove known sensitive values before structured logging."""
    if key and any(term in key.casefold() for term in _SENSITIVE_KEYS):
        return _REDACTED
    if isinstance(value, dict):
        return {str(item_key): redact_log_context(item_value, str(item_key)) for item_key, item_value in value.items()}
    if isinstance(value, list):
        return [redact_log_context(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_log_context(item) for item in value)
    return value


class RedactingFilter(logging.Filter):
    """Apply structured-context redaction before a handler writes a record."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, dict):
            record.msg = redact_log_context(record.msg)
        if isinstance(record.args, dict):
            record.args = redact_log_context(record.args)
        return True


def configure_log_redaction() -> None:
    """Attach one redacting filter to each configured root log handler."""
    for handler in logging.getLogger().handlers:
        if not any(isinstance(item, RedactingFilter) for item in handler.filters):
            handler.addFilter(RedactingFilter())