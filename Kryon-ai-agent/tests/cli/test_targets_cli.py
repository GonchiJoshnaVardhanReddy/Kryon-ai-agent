"""Tests for `kryon targets` CLI commands."""
from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from kryon.cli.main import app
from kryon.core.paths import reset_kryon_home, set_kryon_home
from kryon.targets import reset_target_manager


def test_targets_create(tmp_path: Path) -> None:
    set_kryon_home(tmp_path / "kryon")
    reset_target_manager()
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "targets",
            "create",
            "example",
            "--name",
            "Example Corp",
            "--mode",
            "bug_bounty",
            "--domains",
            "example.com, *.example.com",
            "--budget",
            "25.0",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "Created target" in result.output
    assert "example.com" in result.output
    reset_kryon_home()


def test_targets_create_invalid_mode(tmp_path: Path) -> None:
    set_kryon_home(tmp_path / "kryon")
    reset_target_manager()
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "targets",
            "create",
            "example",
            "--name",
            "X",
            "--mode",
            "invalid",
        ],
    )
    assert result.exit_code != 0
    assert "Invalid mode" in result.output
    reset_kryon_home()


def test_targets_create_invalid_scope(tmp_path: Path) -> None:
    set_kryon_home(tmp_path / "kryon")
    reset_target_manager()
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "targets",
            "create",
            "example",
            "--name",
            "X",
            "--mode",
            "bug_bounty",
            "--domains",
            "not a valid thing",
        ],
    )
    assert result.exit_code != 0
    reset_kryon_home()


def test_targets_list_empty(tmp_path: Path) -> None:
    set_kryon_home(tmp_path / "kryon")
    reset_target_manager()
    runner = CliRunner()
    result = runner.invoke(app, ["targets", "list"])
    assert result.exit_code == 0
    assert "No targets" in result.output
    reset_kryon_home()


def test_targets_list_with_targets(tmp_path: Path) -> None:
    set_kryon_home(tmp_path / "kryon")
    reset_target_manager()
    runner = CliRunner()
    runner.invoke(
        app,
        ["targets", "create", "example", "--name", "Example", "--mode", "bug_bounty"],
    )
    result = runner.invoke(app, ["targets", "list"])
    assert result.exit_code == 0
    assert "example" in result.output
    assert "bug_bounty" in result.output
    reset_kryon_home()


def test_targets_show(tmp_path: Path) -> None:
    set_kryon_home(tmp_path / "kryon")
    reset_target_manager()
    runner = CliRunner()
    runner.invoke(
        app,
        ["targets", "create", "example", "--name", "Example", "--mode", "bug_bounty"],
    )
    result = runner.invoke(app, ["targets", "show", "example"])
    assert result.exit_code == 0
    assert "example" in result.output
    assert "bug_bounty" in result.output
    reset_kryon_home()


def test_targets_show_nonexistent(tmp_path: Path) -> None:
    set_kryon_home(tmp_path / "kryon")
    reset_target_manager()
    runner = CliRunner()
    result = runner.invoke(app, ["targets", "show", "does-not-exist"])
    assert result.exit_code != 0
    assert "not found" in result.output.lower() or "Target" in result.output
    reset_kryon_home()


def test_targets_authorize_accept(tmp_path: Path) -> None:
    set_kryon_home(tmp_path / "kryon")
    reset_target_manager()
    runner = CliRunner()
    runner.invoke(
        app,
        ["targets", "create", "example", "--name", "Example", "--mode", "bug_bounty"],
    )
    result = runner.invoke(
        app,
        [
            "targets",
            "authorize",
            "example",
            "--by",
            "tester",
            "--hours",
            "2.0",
        ],
        input="authorized\n",
    )
    assert result.exit_code == 0, result.output
    assert "authorized" in result.output.lower()
    assert "Target authorized" in result.output
    reset_kryon_home()


def test_targets_authorize_deny(tmp_path: Path) -> None:
    set_kryon_home(tmp_path / "kryon")
    reset_target_manager()
    runner = CliRunner()
    runner.invoke(
        app,
        ["targets", "create", "example", "--name", "Example", "--mode", "bug_bounty"],
    )
    result = runner.invoke(
        app,
        ["targets", "authorize", "example"],
        input="no\n",
    )
    assert result.exit_code != 0
    assert "denied" in result.output.lower()
    reset_kryon_home()


def test_targets_authorize_unknown_raises(tmp_path: Path) -> None:
    set_kryon_home(tmp_path / "kryon")
    reset_target_manager()
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["targets", "authorize", "nope", "--by", "tester"],
        input="authorized\n",
    )
    assert result.exit_code != 0
    reset_kryon_home()


def test_targets_delete(tmp_path: Path) -> None:
    set_kryon_home(tmp_path / "kryon")
    reset_target_manager()
    runner = CliRunner()
    runner.invoke(
        app,
        ["targets", "create", "example", "--name", "Example", "--mode", "bug_bounty"],
    )
    result = runner.invoke(app, ["targets", "delete", "example", "--yes"])
    assert result.exit_code == 0
    assert "Deleted" in result.output
    reset_kryon_home()


def test_targets_delete_nonexistent(tmp_path: Path) -> None:
    set_kryon_home(tmp_path / "kryon")
    reset_target_manager()
    runner = CliRunner()
    result = runner.invoke(app, ["targets", "delete", "nope", "--yes"])
    assert result.exit_code == 0
    assert "did not exist" in result.output.lower()
    reset_kryon_home()


def test_targets_help() -> None:
    """`kryon targets --help` should list the sub-commands."""
    runner = CliRunner()
    result = runner.invoke(app, ["targets", "--help"])
    assert result.exit_code == 0
    assert "create" in result.output
    assert "list" in result.output
    assert "show" in result.output
    assert "authorize" in result.output
    assert "delete" in result.output
