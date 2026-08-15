"""Tests for the paths module."""
from __future__ import annotations

from pathlib import Path

import pytest

from kryon.core.exceptions import TargetError
from kryon.core.paths import (
    kryon_config_file,
    kryon_home,
    kryon_key_file,
    kryon_logs_dir,
    kryon_mcp_catalog_dir,
    kryon_profiles_dir,
    kryon_secrets_file,
    kryon_skill_bundles_dir,
    kryon_state_db_file,
    kryon_target_audit_file,
    kryon_target_dir,
    kryon_target_graph_dir,
    kryon_target_scope_file,
    kryon_targets_dir,
    kryon_transcripts_dir,
    reset_kryon_home,
    set_kryon_home,
)


def test_kryon_home_creates_directory(tmp_path: Path) -> None:
    set_kryon_home(tmp_path / "kryon")
    home = kryon_home()
    assert home == tmp_path / "kryon"
    assert home.exists()
    assert home.is_dir()
    reset_kryon_home()


def test_subdirectory_helpers_create_dirs(tmp_path: Path) -> None:
    set_kryon_home(tmp_path / "kryon")
    for fn in [
        kryon_logs_dir,
        kryon_transcripts_dir,
        kryon_targets_dir,
        kryon_profiles_dir,
        kryon_skill_bundles_dir,
        kryon_mcp_catalog_dir,
    ]:
        d = fn()
        assert d.exists(), f"{fn.__name__} did not create its directory"
        assert d.is_dir()
    reset_kryon_home()


def test_target_dir_helpers(tmp_path: Path) -> None:
    set_kryon_home(tmp_path / "kryon")
    td = kryon_target_dir("example")
    assert td == tmp_path / "kryon" / "targets" / "example"
    assert td.exists()
    gd = kryon_target_graph_dir("example")
    assert gd.exists()
    af = kryon_target_audit_file("example")
    assert af == tmp_path / "kryon" / "targets" / "example" / "audit.db"
    sf = kryon_target_scope_file("example")
    assert sf == tmp_path / "kryon" / "targets" / "example" / "scope.yaml"
    reset_kryon_home()


def test_target_dir_invalid_slug(tmp_path: Path) -> None:
    set_kryon_home(tmp_path / "kryon")
    with pytest.raises(TargetError):
        kryon_target_dir("../etc")
    with pytest.raises(TargetError):
        kryon_target_dir("")
    with pytest.raises(TargetError):
        kryon_target_dir("foo;rm -rf /")
    reset_kryon_home()


def test_file_helpers(tmp_path: Path) -> None:
    set_kryon_home(tmp_path / "kryon")
    assert kryon_config_file() == tmp_path / "kryon" / "config.yaml"
    assert kryon_secrets_file() == tmp_path / "kryon" / ".secrets"
    assert kryon_key_file() == tmp_path / "kryon" / ".key"
    assert kryon_state_db_file() == tmp_path / "kryon" / "state.db"
    reset_kryon_home()


def test_env_var_wins_over_global(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """File #0 tests use env var; this confirms it takes precedence."""
    env_home = tmp_path / "env-home"
    override_home = tmp_path / "override-home"
    override_home.mkdir()
    set_kryon_home(override_home)
    monkeypatch.setenv("KRYON_HOME", str(env_home))
    home = kryon_home()
    assert home == env_home
    reset_kryon_home()
