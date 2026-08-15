"""Activity log — writes events to JSONL files on disk.

One ``ActivityLog`` per file path. The default singleton is at
``~/.kryon/logs/activity.jsonl``, but per-target logs can be created
at ``~/.kryon/targets/<slug>/activity.jsonl``.

The log is append-only and line-oriented (one JSON object per line).
This format is the standard for event streams and can be tailed in
real time with ``Get-Content -Wait`` (PowerShell) or ``tail -f`` (bash).

The first call to ``get_log()`` auto-subscribes the log to the
global event bus. After that, every event emitted to the bus is
recorded to disk. This is intentional: "the log always logs" is
the safer default than "you have to remember to wire it up."
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import aiofiles

from kryon.activity.event import Event
from kryon.core.logger import get_logger

_log = get_logger(__name__)

try:
    import orjson

    _HAS_ORJSON = True
except ImportError:  # pragma: no cover — orjson is a hard dep but we keep a fallback
    _HAS_ORJSON = False


class ActivityLog:
    """Writes events to a JSONL file (one event per line)."""

    def __init__(self, path: Path) -> None:
        """Construct an activity log.

        Args:
            path: The JSONL file to write to. Parent directories
                are created on open.
        """
        self._path = path
        self._fd: Any | None = None

    @property
    def path(self) -> Path:
        """The file this log writes to."""
        return self._path

    async def open(self) -> None:
        """Open the log file for appending.

        Idempotent. Parent directories are created.
        """
        if self._fd is not None:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._fd = await aiofiles.open(self._path, mode="a", encoding="utf-8")

    async def close(self) -> None:
        """Close the log file. Safe to call multiple times."""
        if self._fd is not None:
            await self._fd.close()
            self._fd = None

    async def write(self, event: Event) -> None:
        """Write a single event as a JSONL line.

        Args:
            event: The event to serialize and append.
        """
        if self._fd is None:
            await self.open()
        assert self._fd is not None
        data = event.model_dump(mode="json")
        line = orjson.dumps(data).decode("utf-8") if _HAS_ORJSON else json.dumps(data, default=str)
        await self._fd.write(line + "\n")
        await self._fd.flush()


_log_singleton: ActivityLog | None = None
_log_subscribed: bool = False


def _make_log_subscriber(log: ActivityLog):  # type: ignore[no-untyped-def]
    """Build an async subscriber that writes events to ``log``."""

    async def subscriber(event: Event) -> None:
        await log.write(event)

    subscriber.__name__ = "log_subscriber"
    return subscriber


def get_log() -> ActivityLog:
    """Get the global activity log singleton.

    On first call, this also auto-subscribes the log to the global
    event bus so every emitted event is recorded to disk. The
    subscription is idempotent — subsequent calls are no-ops.

    The default path is ``~/.kryon/logs/activity.jsonl``. Override
    the ``KRYON_HOME`` env var to relocate Kryon's home directory
    (used in tests).

    Returns:
        The shared ``ActivityLog`` instance.
    """
    global _log_singleton, _log_subscribed
    if _log_singleton is None:
        from kryon.core.paths import (  # noqa: PLC0415 — lazy import: paths is a stub in File #0
            kryon_logs_dir,
        )

        path = kryon_logs_dir() / "activity.jsonl"
        _log_singleton = ActivityLog(path)
    if not _log_subscribed:
        # Import here to avoid circular imports at module load time
        from kryon.activity.bus import (  # noqa: PLC0415 — lazy import: avoid circular dep bus->log
            get_bus,
        )

        get_bus().subscribe(_make_log_subscriber(_log_singleton))
        _log_subscribed = True
    return _log_singleton


def reset_log() -> None:
    """Reset the global log (used in tests).

    Drops the singleton and clears the ``_log_subscribed`` flag so
    a fresh subscription is wired on the next ``get_log()`` call.
    The caller is responsible for awaiting ``close()`` on the
    previous log if they want a clean shutdown.
    """
    global _log_singleton, _log_subscribed
    _log_singleton = None
    _log_subscribed = False


__all__ = ["ActivityLog", "get_log", "reset_log"]
