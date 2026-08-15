"""Tests for the exception hierarchy."""
from __future__ import annotations

from kryon.core.exceptions import (
    ApprovalError,
    AuditError,
    AuthorizationError,
    ConfigError,
    DryRunError,
    GraphError,
    KryonError,
    LLMError,
    LoopError,
    MCPError,
    NetworkError,
    RateLimitError,
    ScopeError,
    SecretError,
    SkillError,
    StateError,
    SubagentError,
    TargetError,
    ToolError,
)


def test_all_inherit_from_kryon_error() -> None:
    classes = [
        ConfigError, ScopeError, AuthorizationError, LLMError, MCPError,
        GraphError, TargetError, SkillError, LoopError, ToolError,
        SubagentError, RateLimitError, NetworkError, AuditError, SecretError,
        StateError, ApprovalError, DryRunError,
    ]
    for cls in classes:
        assert issubclass(cls, KryonError), f"{cls.__name__} must inherit from KryonError"


def test_kryon_error_default_details() -> None:
    err = KryonError("msg")
    assert err.details == {}
    assert err.message == "msg"
    assert str(err) == "msg"


def test_kryon_error_with_details() -> None:
    err = KryonError("msg", details={"a": 1})
    assert err.details == {"a": 1}


def test_str_includes_details() -> None:
    err = KryonError("msg", details={"a": 1})
    s = str(err)
    assert "msg" in s
    assert "details" in s
    assert "a" in s


def test_repr_includes_type_and_details() -> None:
    err = ScopeError("blocked", details={"target": "evil.com"})
    r = repr(err)
    assert "ScopeError" in r
    assert "evil.com" in r


def test_subclass_details() -> None:
    err = ScopeError("blocked", details={"target": "evil.com"})
    assert err.details["target"] == "evil.com"
    assert "blocked" in str(err)
    assert "evil.com" in str(err)


def test_can_catch_all_via_kryon_error() -> None:
    """Single ``except KryonError`` should catch every typed error."""
    for exc_cls in [ConfigError, ScopeError, LLMError, GraphError, ToolError]:
        try:
            raise exc_cls("boom", details={"k": "v"})
        except KryonError as e:
            assert e.details == {"k": "v"}
