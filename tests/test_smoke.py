"""Smoke test — verify File #0 works end-to-end."""
from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from kryon import __version__
from kryon.activity import reset_activity
from kryon.cli.main import app
from kryon.core.exceptions import KryonError, ScopeError


def test_version() -> None:
    assert __version__ == "0.1.0"


def test_kryon_error_has_details() -> None:
    err = KryonError("test", details={"a": 1})
    assert err.message == "test"
    assert err.details == {"a": 1}
    assert "details" in str(err)


def test_scope_error_inherits() -> None:
    err = ScopeError("blocked", details={"target": "evil.com"})
    assert isinstance(err, KryonError)
    assert err.details["target"] == "evil.com"


def test_event_renders_one_line() -> None:
    from kryon.activity import Event
    e = Event(event_type="test", action="hello", subagent="recon")
    line = e.render_one_line()
    assert "test" in line
    assert "hello" in line
    assert "[recon]" in line


def test_cli_version() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.output


def test_cli_emit_test_event(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("KRYON_HOME", str(tmp_path))
    reset_activity()
    runner = CliRunner()
    result = runner.invoke(app, ["emit-test-event"])
    assert result.exit_code == 0
    log_path = tmp_path / "logs" / "activity.jsonl"
    assert log_path.exists()
