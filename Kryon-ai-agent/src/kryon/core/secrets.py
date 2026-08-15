"""Encrypted secret storage for API keys.

Secrets are stored at ``~/.kryon/.secrets`` (JSON, encrypted values)
with the Fernet key at ``~/.kryon/.key``. Both files have 0600
permissions on POSIX systems (best-effort on Windows).

**NO plaintext secrets are ever written to disk.** The Fernet token
is base64-encoded and starts with the version byte ``gAAA...``.

If the user deletes the ``.key`` file, all secrets become undecryptable.
This is a by-design failure mode — decryption raises ``SecretError``.
"""

from __future__ import annotations

import contextlib
import json
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from kryon.core.exceptions import SecretError
from kryon.core.paths import kryon_key_file, kryon_secrets_file


def _restrict_permissions(path: Path) -> None:
    """Best-effort 0600 permissions. Windows is a no-op (NTFS perms differ)."""
    with contextlib.suppress(OSError, AttributeError, NotImplementedError):
        path.chmod(0o600)


class SecretsManager:
    """Encrypted secret storage backed by Fernet (symmetric encryption).

    The Fernet key is generated on first use and stored at
    ``~/.kryon/.key``. Subsequent runs load the existing key.

    Args:
        secrets_path: Path to the JSON file holding encrypted secrets.
            Defaults to ``kryon_secrets_file()``.
        key_path: Path to the Fernet key file. Defaults to
            ``kryon_key_file()``.
    """

    def __init__(
        self,
        secrets_path: Path | None = None,
        key_path: Path | None = None,
    ) -> None:
        self._secrets_path = secrets_path or kryon_secrets_file()
        self._key_path = key_path or kryon_key_file()
        self._fernet: Fernet | None = None

    def _get_fernet(self) -> Fernet:
        """Lazily load or generate the Fernet key.

        The key is loaded from disk if it exists, otherwise a new
        256-bit key is generated and written to ``self._key_path``
        with 0600 permissions.

        Raises:
            SecretError: If the key file exists but is malformed
                (not 44 url-safe base64 chars decoding to 32 bytes).
        """
        if self._fernet is not None:
            return self._fernet
        if not self._key_path.exists():
            key = Fernet.generate_key()
            self._key_path.parent.mkdir(parents=True, exist_ok=True)
            self._key_path.write_bytes(key)
            _restrict_permissions(self._key_path)
        else:
            key = self._key_path.read_bytes()
        try:
            self._fernet = Fernet(key)
        except ValueError as e:
            # Wrong key length / not valid base64. Wrap so the caller
            # gets a typed Kryon error, not a cryptography ValueError.
            raise SecretError(
                f"Fernet key at {self._key_path} is malformed (expected 44 url-safe base64 chars)",
                details={"path": str(self._key_path), "error": str(e)},
            ) from e
        return self._fernet

    def _load_secrets(self) -> dict[str, str]:
        """Load the encrypted secrets file. Returns ``{}`` if missing."""
        if not self._secrets_path.exists():
            return {}
        try:
            with self._secrets_path.open(encoding="utf-8") as f:
                data: dict[str, str] = json.load(f)
            return data
        except json.JSONDecodeError as e:
            raise SecretError(
                "Failed to parse secrets file (corrupted?)",
                details={"path": str(self._secrets_path), "error": str(e)},
            ) from e

    def _save_secrets(self, secrets: dict[str, str]) -> None:
        """Save the encrypted secrets file with restricted permissions."""
        self._secrets_path.parent.mkdir(parents=True, exist_ok=True)
        with self._secrets_path.open("w", encoding="utf-8") as f:
            json.dump(secrets, f, indent=2)
        _restrict_permissions(self._secrets_path)

    @staticmethod
    def _validate_name(name: str) -> None:
        """Validate a secret name: alphanumeric + underscore, non-empty.

        Args:
            name: The candidate secret name.

        Raises:
            SecretError: If the name is empty or contains invalid chars.
        """
        if not name:
            raise SecretError("Secret name cannot be empty")
        if not all(c.isalnum() or c == "_" for c in name):
            raise SecretError(
                f"Invalid secret name {name!r}: only alphanumeric and underscore allowed",
                details={"name": name, "allowed": "a-z, A-Z, 0-9, _"},
            )

    def set(self, name: str, value: str) -> None:
        """Encrypt and store a secret.

        Args:
            name: The secret name (validated).
            value: The plaintext value. Encrypted before write.

        Raises:
            SecretError: If name or value is empty/invalid.
        """
        self._validate_name(name)
        if not value:
            raise SecretError("Secret value cannot be empty")
        fernet = self._get_fernet()
        encrypted = fernet.encrypt(value.encode("utf-8"))
        secrets = self._load_secrets()
        secrets[name] = encrypted.decode("utf-8")
        self._save_secrets(secrets)

    def get(self, name: str) -> str:
        """Decrypt and return a secret.

        Args:
            name: The secret name.

        Returns:
            The plaintext value (decrypted in memory only).

        Raises:
            SecretError: If the secret does not exist, decryption fails
                (wrong key), or the name is invalid.
        """
        self._validate_name(name)
        secrets = self._load_secrets()
        if name not in secrets:
            raise SecretError(
                f"Secret not found: {name}",
                details={"name": name, "available": list(secrets.keys())},
            )
        fernet = self._get_fernet()
        try:
            decrypted = fernet.decrypt(secrets[name].encode("utf-8"))
        except InvalidToken as e:
            raise SecretError(
                f"Failed to decrypt secret {name!r} (key changed?)",
                details={"name": name},
            ) from e
        return decrypted.decode("utf-8")

    def delete(self, name: str) -> bool:
        """Delete a secret.

        Args:
            name: The secret name.

        Returns:
            True if the secret existed and was deleted, False if it
            did not exist.
        """
        self._validate_name(name)
        secrets = self._load_secrets()
        if name not in secrets:
            return False
        del secrets[name]
        self._save_secrets(secrets)
        return True

    def list_keys(self) -> list[str]:
        """List secret names (NEVER values).

        Returns:
            A list of secret names. May be empty.
        """
        return list(self._load_secrets().keys())

    def has(self, name: str) -> bool:
        """Check if a secret exists without retrieving its value.

        Args:
            name: The secret name.

        Returns:
            True if the secret exists, False otherwise.
        """
        self._validate_name(name)
        return name in self._load_secrets()


# Singleton
_manager: SecretsManager | None = None


def get_secrets_manager() -> SecretsManager:
    """Get the global secrets manager singleton.

    Returns:
        The shared ``SecretsManager`` instance.
    """
    global _manager
    if _manager is None:
        _manager = SecretsManager()
    return _manager


def reset_secrets_manager() -> None:
    """Reset the global secrets manager (for tests)."""
    global _manager
    _manager = None


# Module-level helpers (sugar so callers don't need to import the manager)


def set_secret(name: str, value: str) -> None:
    """Store a secret (encrypted)."""
    get_secrets_manager().set(name, value)


def get_secret(name: str) -> str:
    """Retrieve a secret (decrypted). Returns the plaintext value."""
    return get_secrets_manager().get(name)


def has_secret(name: str) -> bool:
    """Check if a secret exists without retrieving it."""
    return get_secrets_manager().has(name)


def delete_secret(name: str) -> bool:
    """Delete a secret. Returns True if it existed."""
    return get_secrets_manager().delete(name)


def list_secrets() -> list[str]:
    """List all secret names (not values)."""
    return get_secrets_manager().list_keys()


__all__ = [
    "SecretsManager",
    "delete_secret",
    "get_secret",
    "get_secrets_manager",
    "has_secret",
    "list_secrets",
    "reset_secrets_manager",
    "set_secret",
]
