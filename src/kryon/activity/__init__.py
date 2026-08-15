"""Kryon activity system — real-time event bus, log, console, transcripts.

This is the first-class real-time visibility layer. Every other module
emits events through this.

Public surface:
    - ``Event`` — the Pydantic model
    - ``EventBus`` — async pub/sub
    - ``ActivityLog`` — JSONL file writer
    - ``LiveConsole`` — terminal subscriber
    - ``TranscriptFile`` — per-subagent human-readable log
    - ``setup_activity`` — wire the default subscribers
    - ``emit_*`` helpers — typed convenience emitters
"""

from kryon.activity.bus import EventBus, Subscriber, get_bus, reset_bus
from kryon.activity.console import LiveConsole, get_console, reset_console
from kryon.activity.event import Event
from kryon.activity.helpers import (
    emit,
    emit_error,
    emit_finding_confirmed,
    emit_llm_call,
    emit_scope_blocked,
    emit_state_transition,
    emit_subagent_end,
    emit_subagent_start,
    emit_tool_call,
)
from kryon.activity.log import ActivityLog, get_log, reset_log
from kryon.activity.setup import reset_activity, setup_activity
from kryon.activity.transcript import TranscriptFile, get_transcript, reset_transcript

__all__ = [
    "ActivityLog",
    # Core types
    "Event",
    "EventBus",
    "LiveConsole",
    "Subscriber",
    "TranscriptFile",
    # Emitters
    "emit",
    "emit_error",
    "emit_finding_confirmed",
    "emit_llm_call",
    "emit_scope_blocked",
    "emit_state_transition",
    "emit_subagent_end",
    "emit_subagent_start",
    "emit_tool_call",
    # Singletons
    "get_bus",
    "get_console",
    "get_log",
    "get_transcript",
    "reset_activity",
    # Test helpers
    "reset_bus",
    "reset_console",
    "reset_log",
    "reset_transcript",
    # Setup / teardown
    "setup_activity",
]
