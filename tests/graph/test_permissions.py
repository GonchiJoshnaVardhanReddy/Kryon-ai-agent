"""Tests for graph write permissions — the security property.

CRITICAL: This is the trust model. If a test in this file fails, an
exploit subagent could write a Finding directly without going through
verify. The audit log + graph permissions together = the trust model.
"""
from __future__ import annotations

import pytest

from kryon.core.exceptions import GraphError
from kryon.graph.permissions import (
    GRAPH_WRITE_PERMISSIONS,
    check_write_permission,
)


# ---- The 8 subagent types in the matrix ---------------------------------


def test_permission_matrix_has_eight_subagents() -> None:
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


# ---- recon-passive: Asset, Tech, Person, Credential ----------------------


def test_recon_passive_can_write_asset() -> None:
    check_write_permission("recon-passive", "Asset")


def test_recon_passive_can_write_tech() -> None:
    check_write_permission("recon-passive", "Tech")


def test_recon_passive_can_write_person() -> None:
    check_write_permission("recon-passive", "Person")


def test_recon_passive_can_write_credential() -> None:
    check_write_permission("recon-passive", "Credential")


def test_recon_passive_cannot_write_endpoint() -> None:
    """recon-passive does NOT do active probing — Endpoint belongs to recon-active."""
    with pytest.raises(GraphError, match=r"cannot write 'Endpoint'"):
        check_write_permission("recon-passive", "Endpoint")


def test_recon_passive_cannot_write_finding() -> None:
    with pytest.raises(GraphError, match=r"cannot write 'Finding'"):
        check_write_permission("recon-passive", "Finding")


# ---- recon-active: Asset, Endpoint, Tech, Person, Credential -------------


def test_recon_active_can_write_endpoint() -> None:
    check_write_permission("recon-active", "Endpoint")


def test_recon_active_cannot_write_finding() -> None:
    with pytest.raises(GraphError, match=r"cannot write 'Finding'"):
        check_write_permission("recon-active", "Finding")


# ---- analysis-hypothesis: Hypothesis only -------------------------------


def test_analysis_hypothesis_can_write_hypothesis() -> None:
    check_write_permission("analysis-hypothesis", "Hypothesis")


def test_analysis_hypothesis_cannot_write_asset() -> None:
    with pytest.raises(GraphError, match=r"cannot write 'Asset'"):
        check_write_permission("analysis-hypothesis", "Asset")


def test_analysis_hypothesis_cannot_write_finding() -> None:
    with pytest.raises(GraphError, match=r"cannot write 'Finding'"):
        check_write_permission("analysis-hypothesis", "Finding")


# ---- exploit: ExploitAttempt only (CRITICAL: cannot write Finding) -------


def test_exploit_can_write_exploit_attempt() -> None:
    check_write_permission("exploit", "ExploitAttempt")


def test_exploit_cannot_write_finding() -> None:
    """CRITICAL: only verify can write Finding."""
    with pytest.raises(GraphError, match=r"cannot write 'Finding'"):
        check_write_permission("exploit", "Finding")


def test_exploit_cannot_write_hypothesis() -> None:
    with pytest.raises(GraphError, match=r"cannot write 'Hypothesis'"):
        check_write_permission("exploit", "Hypothesis")


# ---- post-exploit: ExploitChain only ------------------------------------


def test_post_exploit_can_write_exploit_chain() -> None:
    check_write_permission("post-exploit", "ExploitChain")


def test_post_exploit_cannot_write_finding() -> None:
    with pytest.raises(GraphError, match=r"cannot write 'Finding'"):
        check_write_permission("post-exploit", "Finding")


# ---- verify: Finding ONLY -------------------------------------------------


def test_verify_can_write_finding() -> None:
    check_write_permission("verify", "Finding")


def test_verify_cannot_write_asset() -> None:
    """verify can only write Finding — not other types."""
    with pytest.raises(GraphError, match=r"cannot write 'Asset'"):
        check_write_permission("verify", "Asset")


def test_verify_cannot_write_exploit_attempt() -> None:
    with pytest.raises(GraphError, match=r"cannot write 'ExploitAttempt'"):
        check_write_permission("verify", "ExploitAttempt")


# ---- blue-team: DefensiveArtifact, SigmaRule, IRPlaybook -----------------


def test_blue_team_can_write_defensive_artifact() -> None:
    check_write_permission("blue-team", "DefensiveArtifact")


def test_blue_team_can_write_sigma_rule() -> None:
    check_write_permission("blue-team", "SigmaRule")


def test_blue_team_can_write_ir_playbook() -> None:
    check_write_permission("blue-team", "IRPlaybook")


def test_blue_team_cannot_write_finding() -> None:
    """blue-team must NOT be able to write Findings — only verify can."""
    with pytest.raises(GraphError, match=r"cannot write 'Finding'"):
        check_write_permission("blue-team", "Finding")


def test_blue_team_cannot_write_asset() -> None:
    with pytest.raises(GraphError, match=r"cannot write 'Asset'"):
        check_write_permission("blue-team", "Asset")


# ---- report: no graph writes at all ------------------------------------


def test_report_cannot_write_anything() -> None:
    """The report subagent writes to file system, not graph."""
    for node_type in (
        "Asset",
        "Endpoint",
        "Finding",
        "Hypothesis",
        "ExploitAttempt",
        "DefensiveArtifact",
    ):
        with pytest.raises(GraphError):
            check_write_permission("report", node_type)


# ---- unknown subagent is denied -----------------------------------------


def test_unknown_subagent_denied() -> None:
    with pytest.raises(GraphError):
        check_write_permission("rogue", "Asset")


def test_empty_subagent_denied() -> None:
    with pytest.raises(GraphError):
        check_write_permission("", "Asset")


def test_graph_error_includes_context() -> None:
    """The error message must include subagent name, node type, and allowed types."""
    with pytest.raises(GraphError) as exc_info:
        check_write_permission("exploit", "Finding")
    err = exc_info.value
    assert "exploit" in str(err)
    assert "Finding" in str(err)
    # details dict has structured info
    assert err.details.get("subagent") == "exploit"
    assert err.details.get("node_type") == "Finding"
    assert "ExploitAttempt" in err.details.get("allowed_node_types", [])
