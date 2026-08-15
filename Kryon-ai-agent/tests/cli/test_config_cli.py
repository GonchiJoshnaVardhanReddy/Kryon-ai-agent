"""Tests for the `kryon config` CLI commands (single mode, no set-profile)."""
from __future__ import annotations

from pathlib import Path

import yaml
from typer.testing import CliRunner

from kryon.cli.main import app
from kryon.core.config import KryonConfig
from kryon.core.paths import kryon_config_file, reset_kryon_home, set_kryon_home


def test_config_init(tmp_path: Path) -> None:
    set_kryon_home(tmp_path / "kryon")
    runner = CliRunner()
    result = runner.invoke(app, ["config", "init"])
    assert result.exit_code == 0, result.output
    assert kryon_config_file().exists()
    reset_kryon_home()


def test_config_init_refuses_to_overwrite(tmp_path: Path) -> None:
    set_kryon_home(tmp_path / "kryon")
    kryon_config_file().parent.mkdir(parents=True, exist_ok=True)
    kryon_config_file().write_text("llm:\n  provider: anthropic\n")
    runner = CliRunner()
    result = runner.invoke(app, ["config", "init"])
    assert result.exit_code != 0
    assert "already exists" in result.output
    reset_kryon_home()


def test_config_show_redacts_secrets(tmp_path: Path) -> None:
    set_kryon_home(tmp_path / "kryon")
    runner = CliRunner()
    runner.invoke(app, ["config", "init"])
    result = runner.invoke(app, ["config", "show"])
    assert result.exit_code == 0, result.output
    # No real secrets in defaults
    assert "sk-" not in result.output
    # The default provider is shown
    assert "anthropic" in result.output
    reset_kryon_home()


def test_config_set(tmp_path: Path) -> None:
    set_kryon_home(tmp_path / "kryon")
    runner = CliRunner()
    runner.invoke(app, ["config", "init"])
    result = runner.invoke(app, ["config", "set", "llm.provider", "ollama"])
    assert result.exit_code == 0, result.output
    raw = yaml.safe_load(kryon_config_file().read_text(encoding="utf-8"))
    config = KryonConfig.model_validate(raw)
    assert config.llm.provider == "ollama"
    reset_kryon_home()


def test_config_set_ollama_workflow(tmp_path: Path) -> None:
    """Verify the user's main workflow: switch to Ollama with one budget."""
    set_kryon_home(tmp_path / "kryon")
    runner = CliRunner()
    runner.invoke(app, ["config", "init"])
    runner.invoke(app, ["config", "set", "llm.provider", "ollama"])
    runner.invoke(app, ["config", "set", "llm.model", "llama3.1:8b"])
    runner.invoke(app, ["config", "set", "cost.default_per_target_usd", "5"])
    raw = yaml.safe_load(kryon_config_file().read_text(encoding="utf-8"))
    config = KryonConfig.model_validate(raw)
    assert config.llm.provider == "ollama"
    assert config.llm.model == "llama3.1:8b"
    assert config.cost.default_per_target_usd == 5.0
    reset_kryon_home()


def test_config_validate(tmp_path: Path) -> None:
    set_kryon_home(tmp_path / "kryon")
    runner = CliRunner()
    runner.invoke(app, ["config", "init"])
    result = runner.invoke(app, ["config", "validate"])
    assert result.exit_code == 0
    assert "valid" in result.output.lower()
    reset_kryon_home()


def test_config_set_unknown_key_fails(tmp_path: Path) -> None:
    set_kryon_home(tmp_path / "kryon")
    runner = CliRunner()
    runner.invoke(app, ["config", "init"])
    result = runner.invoke(app, ["config", "set", "llm.bogus_key", "x"])
    assert result.exit_code != 0
    reset_kryon_home()


def test_config_set_profile_does_not_exist(tmp_path: Path) -> None:
    """Verify that 'set-profile' is NOT a command (single-mode)."""
    set_kryon_home(tmp_path / "kryon")
    runner = CliRunner()
    result = runner.invoke(app, ["config", "set-profile", "civilian"])
    # Should fail because the command doesn't exist
    assert result.exit_code != 0
    reset_kryon_home()
