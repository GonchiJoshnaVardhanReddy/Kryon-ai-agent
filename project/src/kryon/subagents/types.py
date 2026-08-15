"""Subagent types — the contract between subagents, LLM, graph, and loop.

Adapted from File #5 prompt. The shape matches our actual codebase:
- ``Scope`` is a Pydantic model with ``domains: list[str]`` and ``ips: list[str]``
  (NOT ``set[str]`` from the prompt) — we use ``Scope.contains`` / ``contains_hostname`` /
  ``contains_ip`` for scope checks.
- ``Target`` is a Pydantic model with ``authorization: Authorization | None``
  (NOT a flat ``authorized: bool`` from the prompt).
- The activity emitter is the event bus (which has ``emit()`` and ``subscribe()``).
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

from kryon.targets.models import Scope, Target

# ============================================================================
# LLM types
# ============================================================================


class LLMResponse(BaseModel):
    """What the LLM client returns."""

    content: str
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0
    model: str = ""
    finish_reason: str = "stop"


class LLMClient(Protocol):
    """Protocol for LLM clients.

    Real implementation: File #9 (LiteLLM).
    Test implementation: ``MockLLMClient`` in ``kryon.subagents.base``.
    """

    async def complete(
        self,
        *,
        system: str,
        messages: list[dict[str, str]],
        response_schema: dict[str, Any] | None = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> LLMResponse: ...


# ============================================================================
# Subagent types
# ============================================================================


class SubagentStatus(StrEnum):
    """Lifecycle status of a subagent run."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    COST_EXCEEDED = "cost_exceeded"


class SubagentContext(BaseModel):
    """Input to a subagent run.

    ``extra`` is a free-form bag for loop-driven arguments (the
    hypothesis dict for exploit, the attempt id for verify, etc.).
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    target: Target
    scope: Scope
    iteration: int = 0
    extra: dict[str, Any] = Field(default_factory=dict)


class SubagentResult(BaseModel):
    """Output of a subagent run. Returned by ``Subagent.run()`` — never raised."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    subagent_name: str
    status: SubagentStatus
    output: BaseModel | None = None
    nodes_written: int = 0
    cost_usd: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    duration_s: float = 0.0
    error: str | None = None
    started_at: datetime
    completed_at: datetime


__all__ = [
    "LLMClient",
    "LLMResponse",
    "SubagentContext",
    "SubagentResult",
    "SubagentStatus",
]
