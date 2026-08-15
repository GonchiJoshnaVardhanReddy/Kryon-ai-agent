"""Structured logger using structlog — hardened in File #2.

Resolution order for configuration:
    1. Explicit ``setup_logging(level=..., json_logs=...)`` arguments.
    2. ``KRYON_LOG_LEVEL`` and ``KRYON_LOG_FORMAT`` env vars.
    3. Defaults: ``INFO`` level, pretty console output.

A secret-redaction processor is installed in the structlog chain so
API keys, tokens, passwords, etc. are scrubbed from log output BEFORE
rendering — they never reach console, JSON, or files.

Per-target and per-subagent loggers can be created via
``get_target_logger()``. Context variables (e.g., ``target_id``,
``subagent``) can be bound for an entire async context via
``bind_log_context``.
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any

import structlog

from kryon.core.audit import redact_secrets


def _secret_redactor(
    _logger: Any,
    _method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """Structlog processor: redact secrets BEFORE rendering.

    Walks the event_dict once, redacting:
    - The ``details`` field, if present and a dict/list
    - Any top-level key whose name matches a secret pattern
    """
    if "details" in event_dict and isinstance(event_dict["details"], (dict, list)):
        event_dict["details"] = redact_secrets(event_dict["details"])
    return redact_secrets(event_dict)  # type: ignore[no-any-return]


def setup_logging(
    level: str | None = None,
    json_logs: bool | None = None,
) -> None:
    """Configure structlog for the whole app.

    Args:
        level: Log level name. Defaults to ``$KRYON_LOG_LEVEL`` env var,
            or ``"INFO"``.
        json_logs: If True, emit JSON lines. If False, use the
            dev-friendly colored console renderer. If None, defaults
            to ``$KRYON_LOG_FORMAT`` env var (``"json"`` enables JSON,
            anything else uses pretty).

    Call once at app startup. Re-calling reconfigures, but cached
    loggers (created with ``get_logger``) may still use the original
    config — prefer using unique logger names per test or process.
    """
    if level is None:
        level = os.environ.get("KRYON_LOG_LEVEL", "INFO")
    if json_logs is None:
        json_logs = os.environ.get("KRYON_LOG_FORMAT", "").lower() == "json"

    log_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
        force=True,  # override any prior basicConfig
    )

    processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        _secret_redactor,  # redact secrets BEFORE rendering
    ]
    if json_logs:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer(colors=True))

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a logger for a module. Usage: ``log = get_logger(__name__)``."""
    # structlog.get_logger returns a FilteringBoundLogger at runtime
    # but its type signature is too dynamic for mypy --strict to
    # infer without help.
    return structlog.get_logger(name)  # type: ignore[no-any-return]


def get_target_logger(
    target_id: str,
    subagent: str | None = None,
) -> structlog.stdlib.BoundLogger:
    """Get a logger bound to a ``target_id`` (and optionally ``subagent``).

    All log calls through this logger will automatically include the
    ``target_id`` and ``subagent`` fields.

    Args:
        target_id: The target engagement id.
        subagent: The subagent name, if any.

    Returns:
        A structlog ``BoundLogger``.
    """
    log = structlog.get_logger(target_id).bind(target_id=target_id)
    if subagent:
        log = log.bind(subagent=subagent)
    return log  # type: ignore[no-any-return]


def bind_log_context(**kwargs: Any) -> None:
    """Bind context variables for the current async context.

    All subsequent log calls in this async context will include
    these fields. Use ``unbind_log_context`` or ``clear_log_context``
    to remove.

    Example::

        bind_log_context(target_id="example", subagent="recon-passive")
        log.info("starting")  # auto-includes target_id and subagent
    """
    structlog.contextvars.bind_contextvars(**kwargs)


def unbind_log_context(*keys: str) -> None:
    """Unbind specific context variables."""
    structlog.contextvars.unbind_contextvars(*keys)


def clear_log_context() -> None:
    """Clear all bound context variables."""
    structlog.contextvars.clear_contextvars()


__all__ = [
    "bind_log_context",
    "clear_log_context",
    "get_logger",
    "get_target_logger",
    "setup_logging",
    "unbind_log_context",
]
