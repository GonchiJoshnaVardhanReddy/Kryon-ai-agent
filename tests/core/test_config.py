"""Tests for the configuration system (single mode, no profiles)."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from kryon.core.config import (
    KryonConfig,
    LLMConfig,
    load_config,
    save_config,
    set_config_value,
)
from kryon.core.paths import kryon_config_file, reset_kryon_home, set_kryon_home


def test_default_config() -> None:
    """KryonConfig() returns Pydantic defaults — no profile needed."""
    c = KryonConfig()
    assert c.llm.provider == "anthropic"
    assert c.llm.model == "claude-sonnet-4-5"
    assert c.cost.default_per_target_usd == 50.0
    # No profile fields (single mode)
    assert not hasattr(c, "active_profile")
    assert not hasattr(c, "profile")


def test_save_and_load(tmp_path: Path) -> None:
    set_kryon_home(tmp_path / "kryon")
    path = kryon_config_file()
    config = KryonConfig()
    save_config(config, path)
    assert path.exists()
    loaded = load_config(path)
    assert loaded.llm.provider == "anthropic"
    assert loaded.cost.default_per_target_usd == 50.0
    reset_kryon_home()


def test_env_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    set_kryon_home(tmp_path / "kryon")
    path = kryon_config_file()
    save_config(KryonConfig(), path)
    monkeypatch.setenv("KRYON__LLM__PROVIDER", "ollama")
    monkeypatch.setenv("KRYON__COST__DEFAULT_PER_TARGET_USD", "100")
    config = load_config(path)
    assert config.llm.provider == "ollama"
    assert config.cost.default_per_target_usd == 100.0
    reset_kryon_home()


def test_load_missing_file_returns_default(tmp_path: Path) -> None:
    set_kryon_home(tmp_path / "kryon")
    config = load_config(tmp_path / "nonexistent.yaml")
    assert config.llm.provider == "anthropic"
    reset_kryon_home()


def test_set_config_value(tmp_path: Path) -> None:
    set_kryon_home(tmp_path / "kryon")
    config = KryonConfig()
    new_config = set_config_value(config, "llm.provider", "ollama")
    assert new_config.llm.provider == "ollama"
    # Original not mutated (immutable update)
    assert config.llm.provider == "anthropic"
    reset_kryon_home()


def test_set_config_value_coerces_types() -> None:
    config = KryonConfig()
    new = set_config_value(config, "cost.default_per_target_usd", "5")
    assert new.cost.default_per_target_usd == 5.0
    assert isinstance(new.cost.default_per_target_usd, float)

    new2 = set_config_value(new, "subagent_defaults.max_iterations", "100")
    assert new2.subagent_defaults.max_iterations == 100
    assert isinstance(new2.subagent_defaults.max_iterations, int)


def test_set_config_value_unknown_key_raises() -> None:
    config = KryonConfig()
    with pytest.raises(Exception):
        set_config_value(config, "llm.nonsense_key", "x")
    with pytest.raises(Exception):
        set_config_value(config, "totally.bogus.path", "x")


def test_ollama_provider_via_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify the user's main use case: switch to Ollama via env var."""
    set_kryon_home(tmp_path / "kryon")
    monkeypatch.setenv("KRYON__LLM__PROVIDER", "ollama")
    monkeypatch.setenv("KRYON__LLM__MODEL", "llama3.1:8b")
    monkeypatch.setenv("KRYON__COST__DEFAULT_PER_TARGET_USD", "5")
    config = load_config()
    assert config.llm.provider == "ollama"
    assert config.llm.model == "llama3.1:8b"
    assert config.cost.default_per_target_usd == 5.0
    reset_kryon_home()


def test_save_strips_none_values(tmp_path: Path) -> None:
    """The saved YAML should not have a forest of `key: null` entries."""
    set_kryon_home(tmp_path / "kryon")
    path = kryon_config_file()
    save_config(KryonConfig(), path)
    raw = path.read_text(encoding="utf-8")
    assert ": null" not in raw
    assert "None" not in raw
    reset_kryon_home()


def test_save_restricted_permissions_posix(tmp_path: Path) -> None:
    """On POSIX, save_config should chmod 0600. (No-op on Windows.)"""
    set_kryon_home(tmp_path / "kryon")
    path = kryon_config_file()
    save_config(KryonConfig(), path)
    if hasattr(__import__("os").stat, "S_IMODE"):
        import os
        import stat
        mode = stat.S_IMODE(os.stat(path).st_mode)
        # On POSIX, expect 0o600. On Windows, expect whatever Windows gives.
        import sys
        if sys.platform != "win32":
            assert mode == 0o600
    reset_kryon_home()


def test_llm_config_defaults() -> None:
    llm = LLMConfig()
    assert llm.provider == "anthropic"
    assert llm.model == "claude-sonnet-4-5"
    assert llm.max_tokens == 4096
    assert llm.temperature == 0.0
    assert llm.timeout_seconds == 120
    assert llm.max_retries == 3
    assert llm.api_key is None
    assert llm.base_url is None
