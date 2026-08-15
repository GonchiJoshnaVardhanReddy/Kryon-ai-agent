"""Tests for the `kryon secrets` CLI commands."""
from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from kryon.cli.main import app
from kryon.core.paths import reset_kryon_home, set_kryon_home
from kryon.core.secrets import (
    get_secret,
    has_secret,
    reset_secrets_manager,
    set_secret,
)


def test_secrets_set_and_list(tmp_path: Path) -> None:
    set_kryon_home(tmp_path / "kryon")
    reset_secrets_manager()
    runner = CliRunner()
    result = runner.invoke(app, ["secrets", "set", "test_key", "test_value"])
    assert result.exit_code == 0, result.output
    result = runner.invoke(app, ["secrets", "list"])
    assert result.exit_code == 0, result.output
    assert "test_key" in result.output
    assert "test_value" not in result.output
    reset_kryon_home()


def test_secrets_set_from_stdin(tmp_path: Path) -> None:
    set_kryon_home(tmp_path / "kryon")
    reset_secrets_manager()
    runner = CliRunner()
    result = runner.invoke(app, ["secrets", "set", "stdin_key", "-"], input="piped_value\n")
    assert result.exit_code == 0, result.output
    assert get_secret("stdin_key") == "piped_value"
    reset_kryon_home()


def test_secrets_get_with_confirmation(tmp_path: Path) -> None:
    set_kryon_home(tmp_path / "kryon")
    reset_secrets_manager()
    set_secret("my_key", "my_value")
    runner = CliRunner()
    result = runner.invoke(app, ["secrets", "get", "my_key"], input="y\n")
    assert result.exit_code == 0, result.output
    assert "my_value" in result.output
    reset_kryon_home()


def test_secrets_get_aborted(tmp_path: Path) -> None:
    set_kryon_home(tmp_path / "kryon")
    reset_secrets_manager()
    set_secret("aborted_key", "should_not_appear")
    runner = CliRunner()
    result = runner.invoke(app, ["secrets", "get", "aborted_key"], input="n\n")
    assert "should_not_appear" not in result.output
    reset_kryon_home()


def test_secrets_delete(tmp_path: Path) -> None:
    set_kryon_home(tmp_path / "kryon")
    reset_secrets_manager()
    set_secret("del_key", "del_value")
    runner = CliRunner()
    result = runner.invoke(app, ["secrets", "delete", "del_key"], input="y\n")
    assert result.exit_code == 0, result.output
    assert not has_secret("del_key")
    reset_kryon_home()


def test_secrets_delete_nonexistent(tmp_path: Path) -> None:
    set_kryon_home(tmp_path / "kryon")
    reset_secrets_manager()
    runner = CliRunner()
    result = runner.invoke(app, ["secrets", "delete", "never_existed"], input="y\n")
    # Should not error, just report it didn't exist
    assert result.exit_code == 0, result.output
    assert "did not exist" in result.output
    reset_kryon_home()


def test_secrets_invalid_name_rejected(tmp_path: Path) -> None:
    set_kryon_home(tmp_path / "kryon")
    reset_secrets_manager()
    runner = CliRunner()
    result = runner.invoke(app, ["secrets", "set", "bad name with spaces", "value"])
    assert result.exit_code != 0
    reset_kryon_home()
