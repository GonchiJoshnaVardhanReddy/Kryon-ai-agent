"""Kryon exception hierarchy.

All Kryon-specific exceptions inherit from KryonError. This lets callers
catch everything Kryon-specific with a single ``except KryonError:`` and
access structured context via the ``details`` dict.
"""

from __future__ import annotations

from typing import Any


class KryonError(Exception):
    """Base exception for all Kryon errors.

    Every Kryon-specific exception inherits from this. Carries a
    ``details`` dict for structured context (target_id, step, etc.)
    that flows through logging and audit.
    """

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details: dict[str, Any] = details or {}

    def __str__(self) -> str:
        if self.details:
            return f"{self.message} | details={self.details}"
        return self.message

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.message!r}, details={self.details!r})"


class ConfigError(KryonError):
    """Configuration is missing, invalid, or unreadable."""


class ScopeError(KryonError):
    """Action targets a host or IP outside the scope envelope."""


class AuthorizationError(KryonError):
    """Operator did not provide the required authorization for this engagement."""


class LLMError(KryonError):
    """LLM call failed (network, provider error, validation, budget)."""


class MCPError(KryonError):
    """MCP server connection, invocation, or configuration failed."""


class GraphError(KryonError):
    """Knowledge graph operation failed (query, write, permission, schema)."""


class TargetError(KryonError):
    """Target is invalid, missing, or its scope is unparseable."""


class SkillError(KryonError):
    """Skill loading, parsing, or execution failed."""


class LoopError(KryonError):
    """Autonomous loop state transition or checkpoint failed."""


class ToolError(KryonError):
    """External security tool (subfinder, httpx, etc.) failed or returned invalid output."""


class SubagentError(KryonError):
    """Subagent invocation, lifecycle, or result handling failed."""


class RateLimitError(KryonError):
    """External API rate limit hit; backoff and retry required."""


class NetworkError(KryonError):
    """Network operation (DNS, HTTP, TCP) failed unrecoverably."""


class AuditError(KryonError):
    """Audit log read, write, or integrity check failed."""


class SecretError(KryonError):
    """Secret (API key, credential) missing, unreadable, or undecryptable."""


class StateError(KryonError):
    """Loop state machine entered an invalid state or transition."""


class ApprovalError(KryonError):
    """Operator denied approval for a destructive action."""


class DryRunError(KryonError):
    """Dry-run mode is required but not enabled, or dry-run verification failed."""


class ActivityError(KryonError):
    """Activity event bus, log, or console subscriber failed."""


__all__ = [
    "ActivityError",
    "ApprovalError",
    "AuditError",
    "AuthorizationError",
    "ConfigError",
    "DryRunError",
    "GraphError",
    "KryonError",
    "LLMError",
    "LoopError",
    "MCPError",
    "NetworkError",
    "RateLimitError",
    "ScopeError",
    "SecretError",
    "SkillError",
    "StateError",
    "SubagentError",
    "TargetError",
    "ToolError",
]
