"""Tests for the event bus, helpers, and console/log integration."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from kryon.activity import (
    Event,
    emit,
    emit_error,
    emit_finding_confirmed,
    emit_llm_call,
    emit_scope_blocked,
    emit_state_transition,
    emit_subagent_end,
    emit_subagent_start,
    emit_tool_call,
    get_bus,
    get_log,
    reset_activity,
    reset_bus,
    reset_log,
)


def test_event_creation() -> None:
    e = Event(event_type="x", action="y")
    assert e.event_type == "x"
    assert e.action == "y"
    assert e.cost_usd == 0.0
    assert e.details == {}


def test_event_render_one_line() -> None:
    e = Event(
        event_type="tool_call",
        action="subfinder example.com",
        subagent="recon-passive",
        cost_usd=0.001,
    )
    line = e.render_one_line()
    assert "tool_call" in line
    assert "subfinder" in line
    assert "[recon-passive]" in line
    assert "$0.001" in line


async def test_bus_emits_to_subscribers() -> None:
    reset_bus()
    bus = get_bus()
    received: list[Event] = []

    async def subscriber(event: Event) -> None:
        received.append(event)

    bus.subscribe(subscriber)
    await emit("test", "hello")
    assert len(received) == 1
    assert received[0].event_type == "test"
    assert received[0].action == "hello"
    reset_bus()


async def test_failing_subscriber_does_not_break_others() -> None:
    reset_bus()
    bus = get_bus()
    received: list[Event] = []

    async def bad(_: Event) -> None:
        raise RuntimeError("subscriber boom")

    async def good(event: Event) -> None:
        received.append(event)

    bus.subscribe(bad)
    bus.subscribe(good)
    # Should not raise, and the good subscriber should still get the event
    await emit("test", "ok")
    assert len(received) == 1
    reset_bus()


async def test_subagent_helpers_emit_events() -> None:
    reset_bus()
    bus = get_bus()
    received: list[Event] = []

    async def subscriber(event: Event) -> None:
        received.append(event)

    bus.subscribe(subscriber)

    await emit_subagent_start("recon-passive", "tgt-1", "find subdomains", iteration=3)
    await emit_subagent_end("recon-passive", "tgt-1", "success", 5, 0.01, 1234)
    await emit_tool_call("recon-passive", "subfinder", "example.com", 500)
    await emit_llm_call("analysis-hypothesis", "claude-sonnet-4-5", 100, 50, 0.005)
    await emit_state_transition("tgt-1", "RECON_PASSIVE", "RECON_ACTIVE", 1)
    await emit_finding_confirmed("tgt-1", "f-1", "Reflected XSS in /search", "high")
    await emit_scope_blocked("tgt-1", "evil.com", "not in scope")
    await emit_error("exploit", RuntimeError("boom"))

    assert [e.event_type for e in received] == [
        "subagent_start",
        "subagent_end",
        "tool_call",
        "llm_call",
        "state_transition",
        "finding_confirmed",
        "scope_blocked",
        "error",
    ]
    # Iteration flows through to subagent_start
    assert received[0].iteration == 3
    # Cost flows through to llm_call
    assert received[3].cost_usd == 0.005
    reset_bus()


async def test_emit_event_writes_to_log(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Redirect log to a temp file
    monkeypatch.setenv("KRYON_HOME", str(tmp_path))
    reset_activity()
    # Wire the log subscriber (via setup_activity -> get_log)
    from kryon.activity import setup_activity
    setup_activity(verbose=False)

    await emit_subagent_start("test", "tgt", "goal", iteration=1)
    await emit_subagent_end("test", "tgt", "success", 0, 0.0, 42)

    log_path = tmp_path / "logs" / "activity.jsonl"
    assert log_path.exists()
    lines = log_path.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 2
    events = [json.loads(line) for line in lines]
    assert events[0]["event_type"] == "subagent_start"
    assert events[1]["event_type"] == "subagent_end"
    # Timestamp serialized as ISO string
    assert "timestamp" in events[0]
    reset_activity()
