"""Activity event model — every meaningful agent action emits one of these.

Events are the lingua franca of the activity system. Subagents, the loop,
tools, and the LLM gateway all construct ``Event`` objects and hand them
to the ``EventBus``. Subscribers (the JSONL log, the color console, the
per-subagent transcript file, and Phase 2's TUI / webhooks) consume
them.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class Event(BaseModel):
    """A single structured activity event.

    Events flow through the EventBus to all subscribers. The ActivityLog
    subscriber writes them to disk; the LiveConsole subscriber renders them
    to the terminal; the TranscriptFile subscriber writes them to per-subagent
    log files.
    """

    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    event_type: str  # e.g., "subagent_start", "tool_call", "llm_call", "state_transition"
    subagent: str | None = None
    target_id: str | None = None
    action: str  # short action description
    details: dict[str, Any] = Field(default_factory=dict)
    cost_usd: float = 0.0
    iteration: int | None = None

    def render_one_line(self) -> str:
        """Render a one-line summary for the console.

        Format: ``HH:MM:SS [subagent] event_type | action [$cost] (iter N)``
        """
        ts = self.timestamp.strftime("%H:%M:%S")
        sub = f"[{self.subagent}]" if self.subagent else "    "
        cost = f" ${self.cost_usd:.3f}" if self.cost_usd > 0 else ""
        iter_ = f" (iter {self.iteration})" if self.iteration is not None else ""
        return f"{ts} {sub} {self.event_type:20} | {self.action}{cost}{iter_}"


__all__ = ["Event"]
