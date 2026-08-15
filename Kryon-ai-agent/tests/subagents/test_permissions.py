"""Tests that subagents respect graph write permissions."""
from __future__ import annotations

import pytest

from kryon.core.exceptions import GraphError
from kryon.graph.permissions import (
    GRAPH_WRITE_PERMISSIONS,
    check_write_permission,
)


def test_exploit_cannot_write_finding() -> None:
    """exploit subagent must not be able to write Finding nodes."""
    with pytest.raises(GraphError, match=r"cannot write 'Finding'"):
        check_write_permission("exploit", "Finding")


def test_recon_passive_cannot_write_finding() -> None:
    with pytest.raises(GraphError, match=r"cannot write 'Finding'"):
        check_write_permission("recon-passive", "Finding")


def test_analysis_hypothesis_cannot_write_finding() -> None:
    with pytest.raises(GraphError, match=r"cannot write 'Finding'"):
        check_write_permission("analysis-hypothesis", "Finding")


def test_blue_team_cannot_write_finding() -> None:
    with pytest.raises(GraphError, match=r"cannot write 'Finding'"):
        check_write_permission("blue-team", "Finding")


def test_report_cannot_write_anything() -> None:
    for node_type in ("Asset", "Finding", "Hypothesis"):
        with pytest.raises(GraphError):
            check_write_permission("report", node_type)


def test_only_verify_writes_finding() -> None:
    """Only 'verify' has Finding in its allowed set."""
    writers = [
        name
        for name, allowed in GRAPH_WRITE_PERMISSIONS.items()
        if "Finding" in allowed
    ]
    assert writers == ["verify"]


def test_all_8_subagents_in_matrix() -> None:
    expected = {
        "recon-passive",
        "recon-active",
        "analysis-hypothesis",
        "exploit",
        "post-exploit",
        "verify",
        "blue-team",
        "report",
    }
    assert expected.issubset(set(GRAPH_WRITE_PERMISSIONS.keys()))
