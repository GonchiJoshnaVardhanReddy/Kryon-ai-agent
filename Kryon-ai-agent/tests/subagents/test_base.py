"""Tests for the Subagent base class."""
from __future__ import annotations

from typing import Any

import pytest
from pydantic import BaseModel

from kryon.subagents.base import MockLLMClient, Subagent
from kryon.subagents.schemas import ReconPassiveOutput
from kryon.subagents.types import LLMResponse, SubagentStatus


class _StubSubagent(Subagent):
    name = "stub"
    description = "Stub for testing"
    SYSTEM_PROMPT = "stub prompt"
    OUTPUT_SCHEMA = ReconPassiveOutput

    def build_user_prompt(self, ctx: Any) -> str:
        return "stub user prompt"

    async def write_to_graph(self, output: BaseModel, ctx: Any) -> int:
        return 0


def _make_stub_subagent(ctx, llm, graph, audit, bus, config) -> _StubSubagent:
    return _StubSubagent(llm=llm, graph=graph, audit=audit, bus=bus, config=config)


@pytest.mark.asyncio
async def test_run_with_valid_json(
    kryon_home, ctx, llm, graph, audit, bus, config
) -> None:
    llm.set_default(
        LLMResponse(
            content=(
                '{"summary": "test", "assets": [], "tech": [], '
                '"people": [], "credentials": [], "cost_estimate_usd": 0.0}'
            ),
            cost_usd=0.001,
            prompt_tokens=10,
            completion_tokens=5,
        )
    )
    sa = _make_stub_subagent(ctx, llm, graph, audit, bus, config)
    result = await sa.run(ctx)
    assert result.status == SubagentStatus.COMPLETED
    assert result.cost_usd == 0.001
    assert result.prompt_tokens == 10
    assert result.completion_tokens == 5


@pytest.mark.asyncio
async def test_run_with_invalid_json_retries(
    kryon_home, ctx, graph, audit, bus, config
) -> None:
    """First call returns invalid JSON, second returns valid."""
    call_count = 0

    class _FlakyClient(MockLLMClient):
        async def complete(self, **kwargs: Any) -> LLMResponse:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return LLMResponse(content="not valid json")
            return LLMResponse(
                content=(
                    '{"summary": "ok", "assets": [], "tech": [], '
                    '"people": [], "credentials": [], "cost_estimate_usd": 0.0}'
                )
            )

    sa = _make_stub_subagent(ctx, _FlakyClient(), graph, audit, bus, config)
    result = await sa.run(ctx)
    assert result.status == SubagentStatus.COMPLETED
    assert call_count == 2


@pytest.mark.asyncio
async def test_run_fails_after_max_retries(
    kryon_home, ctx, llm, graph, audit, bus, config
) -> None:
    llm.set_default(LLMResponse(content="not valid json"))
    sa = _make_stub_subagent(ctx, llm, graph, audit, bus, config)
    result = await sa.run(ctx)
    assert result.status == SubagentStatus.FAILED
    assert "Failed to parse" in (result.error or "")


@pytest.mark.asyncio
async def test_run_tracks_cost_and_time(
    kryon_home, ctx, llm, graph, audit, bus, config
) -> None:
    llm.set_default(
        LLMResponse(
            content=(
                '{"summary": "x", "assets": [], "tech": [], '
                '"people": [], "credentials": [], "cost_estimate_usd": 0.0}'
            ),
            cost_usd=0.05,
            prompt_tokens=100,
            completion_tokens=50,
        )
    )
    sa = _make_stub_subagent(ctx, llm, graph, audit, bus, config)
    result = await sa.run(ctx)
    assert result.cost_usd == 0.05
    assert result.prompt_tokens == 100
    assert result.completion_tokens == 50
    assert result.duration_s >= 0


@pytest.mark.asyncio
async def test_activity_events_emitted(
    kryon_home, ctx, llm, graph, audit, bus, config
) -> None:
    events: list[Any] = []
    bus.subscribe(lambda e: events.append(e))
    llm.set_default(
        LLMResponse(
            content=(
                '{"summary": "x", "assets": [], "tech": [], '
                '"people": [], "credentials": [], "cost_estimate_usd": 0.0}'
            )
        )
    )
    sa = _make_stub_subagent(ctx, llm, graph, audit, bus, config)
    await sa.run(ctx)
    event_types = [e.event_type for e in events]
    assert "subagent.start" in event_types
    assert "subagent.llm_call" in event_types
    assert "subagent.complete" in event_types


@pytest.mark.asyncio
async def test_budget_exceeded_returns_cost_exceeded(
    kryon_home, ctx, llm, graph, audit, bus, config
) -> None:
    """When ctx.extra has budget_exceeded, return FAILED with the right error."""
    ctx.extra["budget_exceeded"] = True
    sa = _make_stub_subagent(ctx, llm, graph, audit, bus, config)
    result = await sa.run(ctx)
    assert result.status == SubagentStatus.FAILED
    assert "Budget exceeded" in (result.error or "")


def test_mock_llm_call_count() -> None:
    """MockLLMClient tracks call count."""
    import asyncio

    async def main() -> None:
        m = MockLLMClient()
        m.set_default(LLMResponse(content="{}"))
        for _ in range(3):
            await m.complete(system="x", messages=[])
        assert m.call_count == 3

    asyncio.run(main())
