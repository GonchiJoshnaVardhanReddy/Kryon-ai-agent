"""Shared fixtures for subagent tests."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from kryon.activity import get_bus, reset_bus
from kryon.core.audit import AuditLog, reset_audit_log
from kryon.core.config import KryonConfig
from kryon.core.paths import reset_kryon_home, set_kryon_home
from kryon.graph.store import GraphStore, reset_graph_store
from kryon.subagents.base import MockLLMClient
from kryon.subagents.types import SubagentContext
from kryon.targets.models import Scope, Target


def _make_target() -> Target:
    return Target(
        id="tgt-1",
        slug="example",
        name="Example",
        mode="bug_bounty",
    )


def _make_scope() -> Scope:
    return Scope(domains=["example.com", "*.example.com"], ips=[])


@pytest.fixture
def kryon_home(tmp_path: Path) -> None:
    """Point kryon_home at a per-test tmp dir."""
    set_kryon_home(tmp_path / "kryon")
    reset_graph_store()
    reset_audit_log()
    reset_bus()
    yield
    reset_graph_store()
    reset_audit_log()
    reset_bus()
    reset_kryon_home()


@pytest.fixture
def target() -> Target:
    return _make_target()


@pytest.fixture
def scope() -> Scope:
    return _make_scope()


@pytest.fixture
def ctx(target: Target, scope: Scope) -> SubagentContext:
    return SubagentContext(target=target, scope=scope)


@pytest.fixture
def graph(target: Target) -> GraphStore:
    s = GraphStore(target)
    yield s
    s.close()


@pytest.fixture
def audit(target: Target) -> AuditLog:
    return AuditLog(target.slug)


@pytest.fixture
def bus():
    return get_bus()


@pytest.fixture
def config() -> KryonConfig:
    return KryonConfig()


@pytest.fixture
def llm() -> MockLLMClient:
    return MockLLMClient()
