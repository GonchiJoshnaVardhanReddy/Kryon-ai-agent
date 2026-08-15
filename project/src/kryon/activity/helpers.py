"""Convenience helpers for emitting common events.

These are thin wrappers around ``bus.emit()``. They exist so that
calling code reads naturally::

    await emit_subagent_start("recon-passive", target_id, goal)

instead of::

    await get_bus().emit(Event(
        event_type="subagent_start",
        action=f"recon-passive starting: {goal}",
        subagent="recon-passive",
        target_id=target_id,
        details={"goal": goal},
    ))

Every subagent MUST emit ``subagent_start`` and ``subagent_end`` events
per the meta-prompt's real-time-visibility rules. These helpers enforce
the event-type strings and the payload shape.
"""

from __future__ import annotations

from typing import Any

from kryon.activity.bus import get_bus
from kryon.activity.event import Event


async def emit(
    event_type: str,
    action: str,
    subagent: str | None = None,
    target_id: str | None = None,
    details: dict[str, Any] | None = None,
    cost_usd: float = 0.0,
    iteration: int | None = None,
) -> None:
    """Emit a custom event.

    Args:
        event_type: The event type tag (e.g., "subagent_start").
        action: Short human-readable action description.
        subagent: The emitting subagent, if any.
        target_id: The target engagement ID, if any.
        details: Arbitrary structured payload.
        cost_usd: Cost in USD, if this event represents a paid op.
        iteration: The current loop iteration, if applicable.
    """
    event = Event(
        event_type=event_type,
        action=action,
        subagent=subagent,
        target_id=target_id,
        details=details or {},
        cost_usd=cost_usd,
        iteration=iteration,
    )
    await get_bus().emit(event)


async def emit_subagent_start(
    subagent: str,
    target_id: str,
    goal: str,
    iteration: int | None = None,
) -> None:
    """Emit a ``subagent_start`` event.

    Args:
        subagent: The subagent name (e.g., "recon-passive").
        target_id: The target engagement ID.
        goal: A short description of what this subagent will do.
        iteration: The current loop iteration, if applicable.
    """
    await emit(
        event_type="subagent_start",
        action=f"{subagent} starting: {goal}",
        subagent=subagent,
        target_id=target_id,
        details={"goal": goal},
        iteration=iteration,
    )


async def emit_subagent_end(
    subagent: str,
    target_id: str,
    status: str,
    entities_added: int = 0,
    cost_usd: float = 0.0,
    duration_ms: int = 0,
) -> None:
    """Emit a ``subagent_end`` event.

    Args:
        subagent: The subagent name.
        target_id: The target engagement ID.
        status: Final status string ("success", "failed", "aborted", ...).
        entities_added: Number of entities (assets, endpoints, hypotheses,
            findings, ...) the subagent created.
        cost_usd: Total LLM cost incurred, in USD.
        duration_ms: Wall-clock duration in milliseconds.
    """
    await emit(
        event_type="subagent_end",
        action=(
            f"{subagent} {status}: +{entities_added} entities, {duration_ms}ms, ${cost_usd:.3f}"
        ),
        subagent=subagent,
        target_id=target_id,
        details={
            "status": status,
            "entities_added": entities_added,
            "duration_ms": duration_ms,
        },
        cost_usd=cost_usd,
    )


async def emit_tool_call(
    subagent: str,
    tool: str,
    args_summary: str,
    duration_ms: int = 0,
    success: bool = True,
) -> None:
    """Emit a ``tool_call`` event.

    Args:
        subagent: The subagent making the call.
        tool: Tool name (e.g., "subfinder", "httpx", "sqlmap").
        args_summary: One-line summary of the arguments (NEVER raw args;
            they may contain credentials).
        duration_ms: Tool execution time in milliseconds.
        success: Whether the tool call succeeded.
    """
    await emit(
        event_type="tool_call",
        action=f"{tool}({args_summary})",
        subagent=subagent,
        details={
            "tool": tool,
            "args": args_summary,
            "success": success,
            "duration_ms": duration_ms,
        },
    )


async def emit_llm_call(
    subagent: str,
    model: str,
    prompt_tokens: int = 0,
    response_tokens: int = 0,
    cost_usd: float = 0.0,
) -> None:
    """Emit an ``llm_call`` event.

    Args:
        subagent: The subagent making the call.
        model: The model identifier (e.g., "claude-sonnet-4-5").
        prompt_tokens: Input tokens consumed.
        response_tokens: Output tokens generated.
        cost_usd: Total cost in USD.
    """
    await emit(
        event_type="llm_call",
        action=f"{model}: {prompt_tokens} prompt + {response_tokens} response",
        subagent=subagent,
        details={
            "model": model,
            "prompt_tokens": prompt_tokens,
            "response_tokens": response_tokens,
        },
        cost_usd=cost_usd,
    )


async def emit_state_transition(
    target_id: str,
    from_state: str,
    to_state: str,
    iteration: int,
) -> None:
    """Emit a ``state_transition`` event.

    Args:
        target_id: The target engagement ID.
        from_state: The state being exited.
        to_state: The state being entered.
        iteration: The current loop iteration.
    """
    await emit(
        event_type="state_transition",
        action=f"{from_state} → {to_state}",
        target_id=target_id,
        details={"from": from_state, "to": to_state},
        iteration=iteration,
    )


async def emit_finding_confirmed(
    target_id: str,
    finding_id: str,
    title: str,
    severity: str,
) -> None:
    """Emit a ``finding_confirmed`` event.

    Args:
        target_id: The target engagement ID.
        finding_id: The finding's stable ID.
        title: The finding's short title.
        severity: The severity string (e.g., "high", "critical").
    """
    await emit(
        event_type="finding_confirmed",
        action=f"✅ {severity.upper()}: {title}",
        target_id=target_id,
        details={"finding_id": finding_id, "title": title, "severity": severity},
    )


async def emit_scope_blocked(
    target_id: str,
    target: str,
    reason: str,
) -> None:
    """Emit a ``scope_blocked`` event.

    Args:
        target_id: The target engagement ID.
        target: The out-of-scope target that was blocked.
        reason: Why the action was blocked.
    """
    await emit(
        event_type="scope_blocked",
        action=f"🛑 BLOCKED: {target} ({reason})",
        target_id=target_id,
        details={"target": target, "reason": reason},
    )


async def emit_error(
    subagent: str | None,
    error: BaseException,
    target_id: str | None = None,
) -> None:
    """Emit an ``error`` event.

    Args:
        subagent: The subagent that encountered the error, if any.
        error: The exception (or any ``BaseException``) that was raised.
        target_id: The target engagement ID, if applicable.
    """
    await emit(
        event_type="error",
        action=f"❌ {type(error).__name__}: {error}",
        subagent=subagent,
        target_id=target_id,
        details={
            "error_type": type(error).__name__,
            "error_message": str(error),
        },
    )


__all__ = [
    "emit",
    "emit_error",
    "emit_finding_confirmed",
    "emit_llm_call",
    "emit_scope_blocked",
    "emit_state_transition",
    "emit_subagent_end",
    "emit_subagent_start",
    "emit_tool_call",
]
