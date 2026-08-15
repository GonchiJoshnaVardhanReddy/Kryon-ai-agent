"""Append-only audit log — Layer 8 of the security model.

Every action taken during an engagement is recorded here. The audit
log is the operator's primary evidence trail, the system's debugging
lifeline, and the program's compliance artifact.

The audit log is enforced as append-only at the **database level** via
SQLite triggers. Even a programming error, a compromised process, or a
malicious actor with direct DB access cannot modify or delete entries.

NO ``update()`` method. NO ``delete()`` method. Only ``log()`` and
``query()`` on the ``AuditLog`` class.
"""

from __future__ import annotations

import contextlib
import json
from pathlib import Path
from typing import Any

import aiosqlite

from kryon.core.exceptions import AuditError
from kryon.core.paths import kryon_target_audit_file

# ============================================================================
# Schema
# ============================================================================

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    target_id TEXT NOT NULL,
    subagent TEXT,
    action TEXT NOT NULL,
    details TEXT,
    reasoning TEXT,
    state_from TEXT,
    state_to TEXT,
    cost_usd REAL DEFAULT 0.0
);

CREATE INDEX IF NOT EXISTS idx_audit_target ON audit_log(target_id);
CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_log(action);

-- ENFORCE APPEND-ONLY AT THE DATABASE LEVEL
-- Any attempt to UPDATE or DELETE raises ABORT. The data is immutable.
CREATE TRIGGER IF NOT EXISTS audit_log_no_update
BEFORE UPDATE ON audit_log
BEGIN
    SELECT RAISE(ABORT, 'audit_log is append-only: UPDATE forbidden');
END;

CREATE TRIGGER IF NOT EXISTS audit_log_no_delete
BEFORE DELETE ON audit_log
BEGIN
    SELECT RAISE(ABORT, 'audit_log is append-only: DELETE forbidden');
END;
"""

# ============================================================================
# Secret redaction
# ============================================================================

# Any dict key whose lowercased name CONTAINS one of these substrings
# has its value replaced with "***REDACTED***". The list is broad on
# purpose — false positives (redacting a non-secret value) are cheap,
# false negatives (leaking a secret) are not.
_SECRET_KEYS: frozenset[str] = frozenset(
    {
        "secret",
        "token",
        "password",
        "api_key",
        "apikey",
        "api-key",
        "credential",
        "key",
        "auth",
        "authorization",
    }
)

_REDACTED = "***REDACTED***"


def _redact_secrets(obj: Any) -> Any:
    """Recursively redact values for keys that look like secrets.

    Any dict key whose lowercased name contains a secret keyword
    has its value replaced with ``"***REDACTED***"``. Lists are
    walked recursively. Non-dict/list values pass through.

    Args:
        obj: The structure to redact. May be a dict, list, or scalar.

    Returns:
        A redacted copy (original is not mutated).
    """
    if isinstance(obj, dict):
        result: dict[str, Any] = {}
        for k, v in obj.items():
            if isinstance(k, str) and any(s in k.lower() for s in _SECRET_KEYS):
                result[k] = _REDACTED
            else:
                result[k] = _redact_secrets(v)
        return result
    if isinstance(obj, list):
        return [_redact_secrets(i) for i in obj]
    return obj


# Public alias used by the logger module and exported for tests.
redact_secrets = _redact_secrets


# ============================================================================
# AuditLog class
# ============================================================================


class AuditLog:
    """Append-only audit log for one target engagement.

    All write methods are async (uses ``aiosqlite``). Each target has
    its own ``audit.db`` file. The schema includes SQLite triggers
    that ABORT any ``UPDATE`` or ``DELETE`` — append-only is enforced
    at the database level, not in Python.

    Usage::

        audit = AuditLog("example")
        row_id = await audit.log(
            action="subagent_start",
            subagent="recon-passive",
            details={"goal": "enumerate subdomains"},
        )
        entries = await audit.query(limit=10)
    """

    def __init__(
        self,
        target_id: str,
        path: Path | None = None,
    ) -> None:
        """Construct an audit log for a target.

        Args:
            target_id: The target identifier. Must be non-empty and
                contain only alphanumeric characters, hyphens, and
                underscores.
            path: Override the audit.db path. Defaults to
                ``kryon_target_audit_file(target_id)``.

        Raises:
            AuditError: If ``target_id`` is empty or contains invalid
                characters.
        """
        if not target_id:
            raise AuditError(
                "target_id cannot be empty",
                details={"target_id": target_id},
            )
        if not all(c.isalnum() or c in "-_" for c in target_id):
            raise AuditError(
                f"Invalid target_id {target_id!r}: "
                "only alphanumeric, hyphen, and underscore allowed",
                details={"target_id": target_id},
            )
        self._target_id = target_id
        self._path = path or kryon_target_audit_file(target_id)
        self._schema_initialized = False

    @property
    def target_id(self) -> str:
        """The target this audit log is for."""
        return self._target_id

    @property
    def path(self) -> Path:
        """The path to the audit.db file."""
        return self._path

    async def _ensure_schema(self) -> None:
        """Create the schema if not already initialized. Idempotent."""
        if self._schema_initialized:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self._path) as conn:
            await conn.executescript(SCHEMA_SQL)
            await conn.commit()
        self._schema_initialized = True

    async def log(
        self,
        action: str,
        subagent: str | None = None,
        details: dict[str, Any] | None = None,
        reasoning: str | None = None,
        state_from: str | None = None,
        state_to: str | None = None,
        cost_usd: float = 0.0,
    ) -> int:
        """Append an entry to the audit log.

        ``details`` is JSON-encoded. Secret values are redacted before
        being written to disk (see ``_redact_secrets``).

        Args:
            action: A short action tag (e.g., "subagent_start",
                "tool_call", "state_transition"). Required.
            subagent: The subagent name, if applicable.
            details: Arbitrary structured payload. Will be JSON-encoded
                and have secrets redacted.
            reasoning: Why the action was taken (for audit).
            state_from: The previous state (for state transitions).
            state_to: The new state (for state transitions).
            cost_usd: The cost of this action, if any.

        Returns:
            The row id of the inserted entry.

        Raises:
            AuditError: If ``action`` is empty.
        """
        if not action:
            raise AuditError("action cannot be empty")
        await self._ensure_schema()
        redacted_details = _redact_secrets(details or {})
        details_json = json.dumps(redacted_details) if redacted_details else None
        async with aiosqlite.connect(self._path) as conn:
            cursor = await conn.execute(
                """
                INSERT INTO audit_log
                    (target_id, subagent, action, details, reasoning,
                     state_from, state_to, cost_usd)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    self._target_id,
                    subagent,
                    action,
                    details_json,
                    reasoning,
                    state_from,
                    state_to,
                    cost_usd,
                ),
            )
            await conn.commit()
            return cursor.lastrowid or 0

    async def query(
        self,
        limit: int = 100,
        subagent: str | None = None,
        action: str | None = None,
        since_id: int | None = None,
    ) -> list[dict[str, Any]]:
        """Query recent audit entries, newest first.

        Args:
            limit: Maximum number of entries to return (default 100).
            subagent: Filter to entries from this subagent.
            action: Filter to entries with this action name.
            since_id: Only return entries with id > this.

        Returns:
            List of dicts with keys: ``id``, ``timestamp``, ``target_id``,
            ``subagent``, ``action``, ``details`` (parsed JSON),
            ``reasoning``, ``state_from``, ``state_to``, ``cost_usd``.
        """
        await self._ensure_schema()
        async with aiosqlite.connect(self._path) as conn:
            conn.row_factory = aiosqlite.Row
            sql = "SELECT * FROM audit_log WHERE 1=1"
            params: list[Any] = []
            if subagent is not None:
                sql += " AND subagent = ?"
                params.append(subagent)
            if action is not None:
                sql += " AND action = ?"
                params.append(action)
            if since_id is not None:
                sql += " AND id > ?"
                params.append(since_id)
            sql += " ORDER BY id DESC LIMIT ?"
            params.append(limit)
            cursor = await conn.execute(sql, params)
            rows = await cursor.fetchall()
            result: list[dict[str, Any]] = []
            for row in rows:
                d = dict(row)
                if d.get("details"):
                    with contextlib.suppress(json.JSONDecodeError, TypeError):
                        d["details"] = json.loads(d["details"])
                result.append(d)
            return result

    async def count(self) -> int:
        """Return the total number of entries in the audit log."""
        await self._ensure_schema()
        async with aiosqlite.connect(self._path) as conn:
            cursor = await conn.execute("SELECT COUNT(*) FROM audit_log")
            row = await cursor.fetchone()
            return int(row[0]) if row else 0


# ============================================================================
# Singleton registry (per target_id)
# ============================================================================

_logs: dict[str, AuditLog] = {}


def get_audit_log(target_id: str) -> AuditLog:
    """Get the audit log instance for a specific target.

    Same target_id always returns the same ``AuditLog`` instance
    (within a process). For tests, use ``reset_audit_log`` to clear
    the registry.

    Args:
        target_id: The target identifier.

    Returns:
        The cached ``AuditLog`` for this target, or a fresh one.
    """
    cached = _logs.get(target_id)
    if cached is not None:
        return cached
    fresh = AuditLog(target_id)
    _logs[target_id] = fresh
    return fresh


def reset_audit_log(target_id: str | None = None) -> None:
    """Reset the audit log registry.

    If ``target_id`` is given, only that target's instance is removed.
    If ``target_id`` is None, the entire registry is cleared.

    Args:
        target_id: The target to reset, or None for all.
    """
    global _logs
    if target_id is None:
        _logs = {}
    else:
        _logs.pop(target_id, None)


__all__ = [
    "SCHEMA_SQL",
    "AuditLog",
    "get_audit_log",
    "redact_secrets",
    "reset_audit_log",
]
