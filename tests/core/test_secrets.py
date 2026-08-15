"""Tests for the secrets manager."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from kryon.core.exceptions import SecretError
from kryon.core.paths import reset_kryon_home, set_kryon_home
from kryon.core.secrets import (
    SecretsManager,
    delete_secret,
    get_secret,
    has_secret,
    list_secrets,
    reset_secrets_manager,
    set_secret,
)


def test_set_get_delete(tmp_path: Path) -> None:
    set_kryon_home(tmp_path / "kryon")
    reset_secrets_manager()
    mgr = SecretsManager()
    mgr.set("test_key", "test_value_123")
    assert mgr.get("test_key") == "test_value_123"
    assert mgr.has("test_key")
    assert "test_key" in mgr.list_keys()
    assert mgr.delete("test_key")
    assert not mgr.has("test_key")
    reset_kryon_home()


def test_secret_file_is_encrypted(tmp_path: Path) -> None:
    """Verify the .secrets file on disk does NOT contain plaintext values."""
    set_kryon_home(tmp_path / "kryon")
    reset_secrets_manager()
    mgr = SecretsManager()
    plaintext = "sk-1234567890abcdef"
    mgr.set("api_key", plaintext)
    raw = (tmp_path / "kryon" / ".secrets").read_text(encoding="utf-8")
    assert plaintext not in raw
    data = json.loads(raw)
    assert data["api_key"] != plaintext
    # Fernet tokens are base64-encoded and start with the version byte (gAAA...)
    assert data["api_key"].startswith("g")
    reset_kryon_home()


def test_get_missing_raises(tmp_path: Path) -> None:
    set_kryon_home(tmp_path / "kryon")
    reset_secrets_manager()
    mgr = SecretsManager()
    with pytest.raises(SecretError, match="not found"):
        mgr.get("nonexistent")
    reset_kryon_home()


def test_invalid_name_rejected(tmp_path: Path) -> None:
    set_kryon_home(tmp_path / "kryon")
    reset_secrets_manager()
    mgr = SecretsManager()
    with pytest.raises(SecretError):
        mgr.set("invalid name with spaces", "value")
    with pytest.raises(SecretError):
        mgr.set("name/with/slashes", "value")
    with pytest.raises(SecretError):
        mgr.set("", "value")
    with pytest.raises(SecretError):
        mgr.set("ok_name", "")
    reset_kryon_home()


def test_decryption_fails_with_wrong_key(tmp_path: Path) -> None:
    """Verify that the wrong key can't decrypt."""
    from cryptography.fernet import Fernet
    set_kryon_home(tmp_path / "kryon")
    reset_secrets_manager()
    mgr = SecretsManager()
    mgr.set("test", "value")
    # Overwrite the key with a properly-formatted but DIFFERENT key
    # (44 url-safe base64 chars; decrypts to 32 bytes, but not the
    # original key). A truly invalid key (wrong length / non-base64)
    # is tested separately below.
    (tmp_path / "kryon" / ".key").write_bytes(Fernet.generate_key())
    reset_secrets_manager()
    mgr2 = SecretsManager()
    with pytest.raises(SecretError, match="Failed to decrypt"):
        mgr2.get("test")
    reset_kryon_home()


def test_malformed_key_raises_secret_error(tmp_path: Path) -> None:
    """A key file that isn't valid base64 should raise SecretError, not ValueError."""
    set_kryon_home(tmp_path / "kryon")
    reset_secrets_manager()
    mgr = SecretsManager()
    mgr.set("test", "value")
    # Write 44 raw bytes that are NOT valid url-safe base64 for 32 bytes
    (tmp_path / "kryon" / ".key").write_bytes(b"a" * 44)
    reset_secrets_manager()
    mgr2 = SecretsManager()
    with pytest.raises(SecretError, match="malformed"):
        mgr2.get("test")
    reset_kryon_home()


def test_helper_functions(tmp_path: Path) -> None:
    set_kryon_home(tmp_path / "kryon")
    reset_secrets_manager()
    set_secret("k1", "v1")
    set_secret("k2", "v2")
    assert set(list_secrets()) >= {"k1", "k2"}
    assert get_secret("k1") == "v1"
    assert has_secret("k1")
    assert not has_secret("nonexistent")
    assert delete_secret("k1")
    assert delete_secret("nonexistent") is False
    reset_kryon_home()


def test_key_file_created_lazily(tmp_path: Path) -> None:
    """The Fernet key should be generated on first secret write, not on construction."""
    set_kryon_home(tmp_path / "kryon")
    reset_secrets_manager()
    key_path = tmp_path / "kryon" / ".key"
    assert not key_path.exists()
    mgr = SecretsManager()
    # Construction alone should not create the key
    assert not key_path.exists()
    mgr.set("lazy", "value")
    assert key_path.exists()
    # Key is a 44-byte base64 string
    assert len(key_path.read_bytes()) == 44
    reset_kryon_home()


def test_secret_persists_across_instances(tmp_path: Path) -> None:
    """A secret written by one manager instance can be read by a fresh one."""
    set_kryon_home(tmp_path / "kryon")
    reset_secrets_manager()
    SecretsManager().set("persistent", "durable_value")
    reset_secrets_manager()  # drop singleton
    mgr2 = SecretsManager()
    assert mgr2.get("persistent") == "durable_value"
    reset_kryon_home()


def test_multiple_secrets(tmp_path: Path) -> None:
    set_kryon_home(tmp_path / "kryon")
    reset_secrets_manager()
    mgr = SecretsManager()
    mgr.set("a", "1")
    mgr.set("b", "2")
    mgr.set("c", "3")
    assert set(mgr.list_keys()) == {"a", "b", "c"}
    assert mgr.get("a") == "1"
    assert mgr.get("b") == "2"
    assert mgr.get("c") == "3"
    reset_kryon_home()
