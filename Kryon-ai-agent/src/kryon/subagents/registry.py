"""Subagent registry — all 8 subagents."""

from __future__ import annotations

from kryon.subagents.base import Subagent
from kryon.subagents.impl import (
    AnalysisHypothesisSubagent,
    BlueTeamSubagent,
    ExploitSubagent,
    PostExploitSubagent,
    ReconActiveSubagent,
    ReconPassiveSubagent,
    ReportSubagent,
    VerifySubagent,
)

SUBAGENTS: dict[str, type[Subagent]] = {
    "recon-passive": ReconPassiveSubagent,
    "recon-active": ReconActiveSubagent,
    "analysis-hypothesis": AnalysisHypothesisSubagent,
    "exploit": ExploitSubagent,
    "post-exploit": PostExploitSubagent,
    "verify": VerifySubagent,
    "blue-team": BlueTeamSubagent,
    "report": ReportSubagent,
}


def get_subagent_class(name: str) -> type[Subagent]:
    """Get a subagent class by name.

    Args:
        name: One of the keys in :data:`SUBAGENTS`.

    Raises:
        ValueError: If the name is unknown.
    """
    if name not in SUBAGENTS:
        raise ValueError(f"Unknown subagent: {name!r}. Available: {sorted(SUBAGENTS.keys())}")
    return SUBAGENTS[name]


def list_subagents() -> list[dict[str, str]]:
    """List all subagents with their name + description."""
    return [{"name": cls.name, "description": cls.description} for cls in SUBAGENTS.values()]


__all__ = [
    "SUBAGENTS",
    "get_subagent_class",
    "list_subagents",
]
