"""Standard Kryon paths.

All filesystem paths used by Kryon are centralized here. Every function
that returns a Path creates the parent directory if it doesn't exist
(idempotent).

Precedence for the home directory:
    1. ``$KRYON_HOME`` environment variable
    2. Module-level override set by ``set_kryon_home()`` (test convenience)
    3. ``~/.kryon`` (default)

Env var wins over the module-level override so tests that use
``monkeypatch.setenv("KRYON_HOME", ...)`` (File #0 pattern) keep
working even after tests that use ``set_kryon_home()`` (File #1+)
have run.
"""

from __future__ import annotations

import os
from pathlib import Path

_KRYON_HOME: Path | None = None


def set_kryon_home(path: Path) -> None:
    """Override the Kryon home directory. Used in tests.

    The directory is created if missing. To clear the override, call
    ``reset_kryon_home()``.

    Args:
        path: Directory to use as Kryon's home.
    """
    global _KRYON_HOME
    _KRYON_HOME = path
    _KRYON_HOME.mkdir(parents=True, exist_ok=True)


def reset_kryon_home() -> None:
    """Clear the module-level Kryon home override.

    After calling this, ``kryon_home()`` falls back to the env var
    (or the default ``~/.kryon``). Used in tests to ensure isolation
    between test cases.
    """
    global _KRYON_HOME
    _KRYON_HOME = None


def kryon_home() -> Path:
    """The Kryon home directory.

    Precedence: ``$KRYON_HOME`` env var > module override > ``~/.kryon``.

    The chosen directory is created if missing.
    """
    env_home = os.environ.get("KRYON_HOME")
    if env_home:
        home = Path(env_home)
    elif _KRYON_HOME is not None:
        home = _KRYON_HOME
    else:
        home = Path.home() / ".kryon"
    home.mkdir(parents=True, exist_ok=True)
    return home


def kryon_logs_dir() -> Path:
    """Directory for activity logs (~/.kryon/logs/)."""
    p = kryon_home() / "logs"
    p.mkdir(parents=True, exist_ok=True)
    return p


def kryon_transcripts_dir() -> Path:
    """Directory for per-subagent transcripts (~/.kryon/transcripts/)."""
    p = kryon_home() / "transcripts"
    p.mkdir(parents=True, exist_ok=True)
    return p


def kryon_targets_dir() -> Path:
    """Directory for per-target state (~/.kryon/targets/)."""
    p = kryon_home() / "targets"
    p.mkdir(parents=True, exist_ok=True)
    return p


def kryon_target_dir(slug: str) -> Path:
    """A specific target's directory (~/.kryon/targets/<slug>/).

    The slug is validated to be safe: alphanumeric, hyphen, underscore only.
    This prevents path traversal attacks like ``../etc``.

    Args:
        slug: A short identifier for the target (e.g., "example-com").

    Returns:
        The target directory. Created if missing.

    Raises:
        TargetError: If the slug is empty or contains unsafe characters.
    """
    if not slug or not slug.replace("-", "").replace("_", "").isalnum():
        from kryon.core.exceptions import (  # noqa: PLC0415 — lazy: avoid circular import at module load
            TargetError,
        )

        raise TargetError(
            f"Invalid target slug: {slug!r}",
            details={"slug": slug, "allowed": "alphanumeric, '-', '_'"},
        )
    p = kryon_targets_dir() / slug
    p.mkdir(parents=True, exist_ok=True)
    return p


def kryon_target_graph_dir(slug: str) -> Path:
    """The knowledge graph database directory for a target."""
    p = kryon_target_dir(slug) / "graph"
    p.mkdir(parents=True, exist_ok=True)
    return p


def kryon_target_transcripts_dir(slug: str) -> Path:
    """The transcripts directory for a target."""
    p = kryon_target_dir(slug) / "transcripts"
    p.mkdir(parents=True, exist_ok=True)
    return p


def kryon_target_audit_file(slug: str) -> Path:
    """The audit log SQLite file for a target."""
    return kryon_target_dir(slug) / "audit.db"


def kryon_target_activity_log(slug: str) -> Path:
    """The activity log JSONL file for a target."""
    return kryon_target_dir(slug) / "activity.jsonl"


def kryon_target_reports_dir(slug: str) -> Path:
    """The reports directory for a target."""
    p = kryon_target_dir(slug) / "reports"
    p.mkdir(parents=True, exist_ok=True)
    return p


def kryon_target_scope_file(slug: str) -> Path:
    """The scope file for a target (YAML)."""
    return kryon_target_dir(slug) / "scope.yaml"


def kryon_config_file() -> Path:
    """The main config file (~/.kryon/config.yaml)."""
    return kryon_home() / "config.yaml"


def kryon_profiles_dir() -> Path:
    """Directory for profile-specific configs (~/.kryon/profiles/).

    Reserved for future use. Not used in single-mode (File #1+).
    """
    p = kryon_home() / "profiles"
    p.mkdir(parents=True, exist_ok=True)
    return p


def kryon_secrets_file() -> Path:
    """The encrypted secrets file (~/.kryon/.secrets)."""
    return kryon_home() / ".secrets"


def kryon_key_file() -> Path:
    """The Fernet key for the secrets file (~/.kryon/.key)."""
    return kryon_home() / ".key"


def kryon_skill_bundles_dir() -> Path:
    """Directory for installed skill bundles (~/.kryon/skill_bundles/)."""
    p = kryon_home() / "skill_bundles"
    p.mkdir(parents=True, exist_ok=True)
    return p


def kryon_mcp_catalog_dir() -> Path:
    """Directory for the MCP catalog (~/.kryon/mcp_catalog/)."""
    p = kryon_home() / "mcp_catalog"
    p.mkdir(parents=True, exist_ok=True)
    return p


def kryon_state_db_file() -> Path:
    """The global state SQLite database (~/.kryon/state.db)."""
    return kryon_home() / "state.db"


__all__ = [
    "kryon_config_file",
    "kryon_home",
    "kryon_key_file",
    "kryon_logs_dir",
    "kryon_mcp_catalog_dir",
    "kryon_profiles_dir",
    "kryon_secrets_file",
    "kryon_skill_bundles_dir",
    "kryon_state_db_file",
    "kryon_target_activity_log",
    "kryon_target_audit_file",
    "kryon_target_dir",
    "kryon_target_graph_dir",
    "kryon_target_reports_dir",
    "kryon_target_scope_file",
    "kryon_target_transcripts_dir",
    "kryon_targets_dir",
    "kryon_transcripts_dir",
    "reset_kryon_home",
    "set_kryon_home",
]
