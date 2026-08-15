"""Per-subagent transcript files.

Each subagent invocation gets its own log file at
``transcripts/<subagent>_<iter>.log`` inside the target's directory
(or the global transcripts dir for cross-target work). The file is
opened at subagent start, written to during run, and closed at
subagent end. The user can ``tail -f`` (or ``Get-Content -Wait`` on
PowerShell) the file to see real-time progress.

The format is human-readable, NOT JSONL — transcripts are for the
operator to read, not for a downstream parser. JSONL is for the
activity log.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import aiofiles

from kryon.activity.event import Event
from kryon.core.logger import get_logger

_log = get_logger(__name__)


class TranscriptFile:
    """Per-subagent log file writer."""

    def __init__(self, path: Path) -> None:
        """Construct a transcript writer.

        Args:
            path: The file to write to. Parent directories are
                created when ``open()`` is called.
        """
        self._path = path
        self._fd: Any | None = None
        self._subagent: str | None = None
        self._iter: int | None = None

    @property
    def path(self) -> Path:
        """The file this transcript writes to."""
        return self._path

    @property
    def is_open(self) -> bool:
        """Whether the transcript is currently open for writing."""
        return self._fd is not None

    async def open(self, subagent: str, iter_: int) -> None:
        """Open a new transcript file for this subagent+iter.

        If a previous file is still open, it is closed first.

        Args:
            subagent: The subagent name (e.g., "recon-passive").
            iter_: The iteration number (for retries / re-runs).
        """
        self._subagent = subagent
        self._iter = iter_
        if self._fd is not None:
            await self.close()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._fd = await aiofiles.open(self._path, mode="w", encoding="utf-8")
        await self._write_header(subagent, iter_)

    async def _write_header(self, subagent: str, iter_: int) -> None:
        assert self._fd is not None
        header = (
            f"# Kryon transcript | subagent={subagent} | iter={iter_}\n"
            f"# path: {self._path}\n"
            "# format: timestamp | event_type | action\n"
            "#                  | details: {...}\n"
            "#\n"
        )
        await self._fd.write(header)
        await self._fd.flush()

    async def write(self, event: Event) -> None:
        """Write a single event to the transcript file.

        No-op if the file is not open. Call ``open()`` first.

        Args:
            event: The event to record.
        """
        if self._fd is None:
            return
        line = f"{event.timestamp.isoformat()} | {event.event_type:20} | {event.action}\n"
        if event.details:
            line += f"  details: {event.details}\n"
        if event.cost_usd:
            line += f"  cost_usd: {event.cost_usd:.4f}\n"
        await self._fd.write(line)
        await self._fd.flush()

    async def close(self) -> None:
        """Close the transcript file. Safe to call multiple times."""
        if self._fd is not None:
            await self._fd.close()
            self._fd = None
            self._subagent = None
            self._iter = None


_transcript: TranscriptFile | None = None


def get_transcript() -> TranscriptFile:
    """Get the global transcript writer singleton.

    Call ``await transcript.open(subagent, iter)`` at subagent start,
    ``await transcript.write(event)`` for each event, and
    ``await transcript.close()`` at subagent end. The default path is
    ``~/.kryon/transcripts/_default.log`` until a per-subagent file is
    opened.

    Returns:
        The shared ``TranscriptFile`` instance.
    """
    global _transcript
    if _transcript is None:
        from kryon.core.paths import (  # noqa: PLC0415 — lazy import: paths is a stub
            kryon_transcripts_dir,
        )

        _transcript = TranscriptFile(kryon_transcripts_dir() / "_default.log")
    return _transcript


def reset_transcript() -> None:
    """Reset the global transcript (used in tests)."""
    global _transcript
    _transcript = None


__all__ = ["TranscriptFile", "get_transcript", "reset_transcript"]
