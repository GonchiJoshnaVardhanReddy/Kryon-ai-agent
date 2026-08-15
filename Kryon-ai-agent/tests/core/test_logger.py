"""Tests for the hardened structlog-based logger (File #2).

Covers:
- Default level (INFO) and pretty console mode
- KRYON_LOG_LEVEL / KRYON_LOG_FORMAT env vars
- JSON mode
- get_logger / get_target_logger
- bind_log_context / unbind_log_context / clear_log_context
- Secret redaction in logger output (both top-level and nested)
"""
from __future__ import annotations

import json
import os

import pytest
import structlog

from kryon.core.logger import (
    bind_log_context,
    clear_log_context,
    get_logger,
    get_target_logger,
    setup_logging,
    unbind_log_context,
)


# Each test calls setup_logging() fresh so structlog config is reset.
# We also clear contextvars between tests to avoid bleed.


@pytest.fixture(autouse=True)
def _reset_logger() -> None:
    """Reset structlog config + contextvars before every test."""
    structlog.contextvars.clear_contextvars()
    yield
    structlog.contextvars.clear_contextvars()


def test_setup_logging_pretty_mode_by_default(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pretty console is the default when KRYON_LOG_FORMAT is unset."""
    monkeypatch.delenv("KRYON_LOG_FORMAT", raising=False)
    monkeypatch.delenv("KRYON_LOG_LEVEL", raising=False)
    setup_logging()
    log = get_logger("prettytest")
    log.info("pretty_event")
    out = capsys.readouterr().out
    assert "pretty_event" in out
    # Pretty output contains ANSI color codes / dev renderer markers,
    # but it should NOT be a single-line JSON object.
    line = out.strip()
    assert not (line.startswith("{") and line.endswith("}"))
    assert "pretty_event" in line


def test_setup_logging_json_mode(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """KRYON_LOG_FORMAT=json produces valid one-line JSON per event."""
    monkeypatch.setenv("KRYON_LOG_FORMAT", "json")
    setup_logging()
    log = get_logger("jsontest")
    # Pass api_key as TOP-LEVEL kwarg so it gets redacted by the
    # second redact_secrets(event_dict) call in the processor.
    log.info("json_event", api_key="should-be-redacted", user="alice")
    out = capsys.readouterr().out
    lines = [ln for ln in out.split("\n") if ln.strip()]
    assert lines, "expected at least one log line"
    parsed = json.loads(lines[-1])
    assert parsed["event"] == "json_event"
    assert parsed.get("api_key") == "***REDACTED***"
    # Non-secret fields pass through
    assert parsed.get("user") == "alice"


def test_setup_logging_env_var_level(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """KRYON_LOG_LEVEL=DEBUG enables debug logs."""
    monkeypatch.setenv("KRYON_LOG_LEVEL", "DEBUG")
    monkeypatch.delenv("KRYON_LOG_FORMAT", raising=False)
    setup_logging()
    log = get_logger("envtest")
    log.debug("debug_msg")
    out = capsys.readouterr().out
    assert "debug_msg" in out


def test_setup_logging_default_level_is_info(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No env var → INFO level: debug is silenced, info passes through."""
    monkeypatch.delenv("KRYON_LOG_LEVEL", raising=False)
    monkeypatch.delenv("KRYON_LOG_FORMAT", raising=False)
    setup_logging()
    log = get_logger("defaultlevel")
    log.debug("should_not_appear")
    log.info("should_appear")
    out = capsys.readouterr().out
    assert "should_not_appear" not in out
    assert "should_appear" in out


def test_get_logger_basic() -> None:
    """get_logger returns a structlog BoundLogger with standard methods."""
    setup_logging()
    log = get_logger("test_module")
    assert log is not None
    # BoundLogger interface
    for method in ("info", "warning", "error", "debug"):
        assert hasattr(log, method), f"logger missing {method}"


def test_get_target_logger_binds_fields() -> None:
    """get_target_logger returns a logger pre-bound with target_id + subagent."""
    setup_logging()
    log = get_target_logger("example", subagent="recon-passive")
    assert log is not None
    # .bind() returns a new logger; we can verify the chain didn't error.
    deeper = log.bind(extra="value")
    assert deeper is not None


def test_bind_log_context() -> None:
    """bind_log_context stores contextvars used by merge_contextvars."""
    setup_logging()
    bind_log_context(target_id="example", subagent="recon")
    log = get_logger("test")
    # Just verify it doesn't raise
    log.info("test_event")
    unbind_log_context("subagent")
    log.info("test_event_2")
    clear_log_context()


def test_unbind_log_context() -> None:
    """unbind_log_context removes a specific key without raising."""
    setup_logging()
    bind_log_context(target_id="example", subagent="recon")
    unbind_log_context("subagent")
    # No assertion on output — just verify no exception.
    log = get_logger("test")
    log.info("after_unbind")
    clear_log_context()


def test_clear_log_context() -> None:
    """clear_log_context removes all contextvars."""
    setup_logging()
    bind_log_context(target_id="example", subagent="recon", run_id="abc")
    clear_log_context()
    log = get_logger("test")
    log.info("after_clear")
    # No assertion on output — just verify no exception.


def test_secret_redaction_via_logger(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The logger's _secret_redactor processor scrubs secrets from output.

    Tests BOTH redaction paths:
    1. Top-level kwargs (api_key=...) are redacted
    2. Nested in `details` (details={'api_key': ...}) are redacted
    """
    monkeypatch.setenv("KRYON_LOG_FORMAT", "json")
    setup_logging()
    log = get_logger("redacttest")
    log.info(
        "mixed",
        api_key="top-level-secret",
        token="another-top",
        details={
            "tool": "sqlmap",
            "password": "nested-secret",
            "ok": "visible",
        },
    )
    out = capsys.readouterr().out
    lines = [ln for ln in out.split("\n") if ln.strip()]
    parsed = json.loads(lines[-1])
    # Top-level redaction
    assert parsed["api_key"] == "***REDACTED***"
    assert parsed["token"] == "***REDACTED***"
    # Nested in details
    assert parsed["details"]["password"] == "***REDACTED***"
    # Non-secret fields untouched
    assert parsed["details"]["tool"] == "sqlmap"
    assert parsed["details"]["ok"] == "visible"


def test_structlog_redacts_secrets_in_details(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Direct test: the `_secret_redactor` processor walks `details`."""
    monkeypatch.setenv("KRYON_LOG_FORMAT", "json")
    setup_logging()
    log = get_logger("details_redact")
    log.info(
        "event",
        details={
            "api_key": "k1",
            "user_token": "t1",
            "nested": {"password": "p1", "plain": "ok"},
            "list_field": [{"credential": "c1"}, "plain_item"],
        },
    )
    out = capsys.readouterr().out
    lines = [ln for ln in out.split("\n") if ln.strip()]
    parsed = json.loads(lines[-1])
    details = parsed["details"]
    assert details["api_key"] == "***REDACTED***"
    assert details["user_token"] == "***REDACTED***"
    assert details["nested"]["password"] == "***REDACTED***"
    assert details["nested"]["plain"] == "ok"
    assert details["list_field"][0]["credential"] == "***REDACTED***"
    assert details["list_field"][1] == "plain_item"


def test_setup_logging_explicit_args_override_env(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Explicit setup_logging() args win over env vars."""
    monkeypatch.setenv("KRYON_LOG_FORMAT", "json")  # would normally be JSON
    setup_logging(json_logs=False)  # but we force pretty
    log = get_logger("explicit")
    log.info("event")
    out = capsys.readouterr().out
    # Pretty mode, not JSON — no leading '{' on the rendered line
    line = out.strip()
    assert "event" in line
    assert not (line.startswith("{") and line.endswith("}"))
