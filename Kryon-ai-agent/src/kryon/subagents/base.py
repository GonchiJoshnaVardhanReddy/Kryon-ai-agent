"""Base class for all subagents.

Adapted from File #5 prompt to use our actual codebase:
- ``AuditLog`` is at ``kryon.core.audit`` (takes ``target_id: str``)
- ``KryonConfig`` is at ``kryon.core.config``
- ``EventBus`` is at ``kryon.activity`` and has ``emit()`` + ``subscribe()``
- The base class is ``ABC`` with two abstract methods + one concrete
  ``run()`` that handles the lifecycle.
"""

from __future__ import annotations

import time
import uuid
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any, ClassVar

from pydantic import BaseModel, ValidationError

from kryon.activity import EventBus, emit, get_bus
from kryon.core.audit import AuditLog
from kryon.core.config import KryonConfig
from kryon.core.exceptions import KryonError
from kryon.graph.store import GraphStore
from kryon.subagents.types import (
    LLMClient,
    LLMResponse,
    SubagentContext,
    SubagentResult,
    SubagentStatus,
)


class Subagent(ABC):
    """Abstract base for all 8 subagents.

    Subclasses define:
    - ``name``, ``description``, ``SYSTEM_PROMPT``, ``OUTPUT_SCHEMA``
    - ``build_user_prompt(ctx)`` -> str
    - ``write_to_graph(output, ctx)`` -> int

    The base class handles:
    - Activity event emission
    - LLM call (with retry on validation failure)
    - JSON parsing and Pydantic validation
    - Cost / time tracking
    - Error wrapping
    """

    name: ClassVar[str] = ""
    description: ClassVar[str] = ""
    SYSTEM_PROMPT: ClassVar[str] = ""
    OUTPUT_SCHEMA: ClassVar[type[BaseModel]] = BaseModel
    MAX_PARSE_RETRIES: ClassVar[int] = 2

    def __init__(
        self,
        *,
        llm: LLMClient,
        graph: GraphStore,
        audit: AuditLog,
        bus: EventBus | None = None,
        config: KryonConfig,
    ) -> None:
        self._llm = llm
        self._graph = graph
        self._audit = audit
        self._bus = bus if bus is not None else get_bus()
        self._config = config

    @abstractmethod
    def build_user_prompt(self, ctx: SubagentContext) -> str:
        """Build the user message from the context."""

    @abstractmethod
    async def write_to_graph(self, output: BaseModel, ctx: SubagentContext) -> int:
        """Write the parsed output to the graph. Returns nodes written."""

    async def run(self, ctx: SubagentContext) -> SubagentResult:
        """Run the subagent. Returns ``SubagentResult`` (never raises)."""
        started = datetime.now(UTC)
        await emit(
            event_type="subagent.start",
            action=f"{self.name} starting: iter {ctx.iteration}",
            subagent=self.name,
            target_id=ctx.target.slug,
            iteration=ctx.iteration,
        )

        try:
            # Check budget before running
            if ctx.extra.get("budget_exceeded"):
                raise KryonError(f"Budget exceeded for target {ctx.target.slug}")

            # Build user prompt
            user_prompt = self.build_user_prompt(ctx)

            # Call LLM (with retry on validation failure)
            response, output = await self._call_llm_with_retry(user_prompt, ctx)

            # Write to graph
            t0 = time.perf_counter()
            n_written = await self.write_to_graph(output, ctx)
            write_duration = time.perf_counter() - t0

            completed = datetime.now(UTC)
            duration = (completed - started).total_seconds()

            await emit(
                event_type="subagent.complete",
                action=f"{self.name} done: {n_written} nodes",
                subagent=self.name,
                target_id=ctx.target.slug,
                cost_usd=response.cost_usd,
                iteration=ctx.iteration,
                details={
                    "nodes_written": n_written,
                    "prompt_tokens": response.prompt_tokens,
                    "completion_tokens": response.completion_tokens,
                    "duration_s": duration,
                    "write_duration_s": write_duration,
                },
            )

            return SubagentResult(
                subagent_name=self.name,
                status=SubagentStatus.COMPLETED,
                output=output,
                nodes_written=n_written,
                cost_usd=response.cost_usd,
                prompt_tokens=response.prompt_tokens,
                completion_tokens=response.completion_tokens,
                duration_s=duration,
                error=None,
                started_at=started,
                completed_at=completed,
            )

        except Exception as e:
            completed = datetime.now(UTC)
            duration = (completed - started).total_seconds()
            await emit(
                event_type="subagent.error",
                action=f"{self.name} failed: {e}",
                subagent=self.name,
                target_id=ctx.target.slug,
                iteration=ctx.iteration,
                details={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "duration_s": duration,
                },
            )
            return SubagentResult(
                subagent_name=self.name,
                status=SubagentStatus.FAILED,
                output=None,
                nodes_written=0,
                cost_usd=0.0,
                prompt_tokens=0,
                completion_tokens=0,
                duration_s=duration,
                error=str(e),
                started_at=started,
                completed_at=completed,
            )

    async def _call_llm_with_retry(
        self, user_prompt: str, ctx: SubagentContext
    ) -> tuple[LLMResponse, BaseModel]:
        """Call LLM and parse output. Retry on validation failure."""
        schema = self.OUTPUT_SCHEMA.model_json_schema()
        last_error: Exception | None = None
        for attempt in range(self.MAX_PARSE_RETRIES + 1):
            await emit(
                event_type="subagent.llm_call",
                action=f"{self.name} LLM call attempt {attempt + 1}",
                subagent=self.name,
                target_id=ctx.target.slug,
                iteration=ctx.iteration,
                details={
                    "attempt": attempt,
                    "model": self._config.llm.model,
                },
            )
            response = await self._llm.complete(
                system=self.SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
                response_schema=schema,
                temperature=0.0,
            )
            try:
                output = self.OUTPUT_SCHEMA.model_validate_json(response.content)
                return response, output
            except (ValidationError, ValueError) as e:
                last_error = e
                await emit(
                    event_type="subagent.parse_error",
                    action=f"{self.name} parse error attempt {attempt + 1}",
                    subagent=self.name,
                    target_id=ctx.target.slug,
                    iteration=ctx.iteration,
                    details={
                        "attempt": attempt,
                        "error": str(e),
                    },
                )
                # On retry, add the error to the user prompt
                if attempt < self.MAX_PARSE_RETRIES:
                    user_prompt = (
                        user_prompt + f"\n\nYour previous response failed validation: {e}\n"
                        "Please respond with valid JSON matching the schema. "
                        "No prose, no markdown fences."
                    )
        raise KryonError(
            f"Failed to parse {self.name} output after "
            f"{self.MAX_PARSE_RETRIES + 1} attempts: {last_error}"
        )


def _gen_id(prefix: str) -> str:
    """Generate a stable id like ``"asset:abcdef12"``."""
    return f"{prefix}:{uuid.uuid4().hex[:8]}"


class MockLLMClient:
    """Mock LLM client for tests.

    Returns canned responses based on a registry, or a default response
    if no canned response is set. Counts calls for test assertions.
    """

    def __init__(self) -> None:
        self._responses: dict[str, LLMResponse] = {}
        self._default_response: LLMResponse | None = None
        self._call_count = 0

    def set_response(self, system_prompt_substring: str, response: LLMResponse) -> None:
        """Register a canned response for a system-prompt substring match."""
        self._responses[system_prompt_substring] = response

    def set_default(self, response: LLMResponse) -> None:
        """Register a default fallback response."""
        self._default_response = response

    @property
    def call_count(self) -> int:
        return self._call_count

    async def complete(
        self,
        *,
        system: str,
        messages: list[dict[str, str]],
        response_schema: dict[str, Any] | None = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        self._call_count += 1
        for substring, response in self._responses.items():
            if substring in system:
                return response
        if self._default_response is not None:
            return self._default_response
        # Fallback: empty JSON
        return LLMResponse(
            content="{}",
            prompt_tokens=10,
            completion_tokens=5,
            cost_usd=0.001,
            model="mock",
        )


__all__ = ["MockLLMClient", "Subagent"]
