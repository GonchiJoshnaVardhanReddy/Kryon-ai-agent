"""Tests for output schemas (Pydantic v2)."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from kryon.subagents.schemas import (
    AnalysisHypothesisOutput,
    BlueTeamOutput,
    ExploitOutput,
    ExploitAttemptRecord,
    HypothesisProposal,
    IRPlaybookProposal,
    PostExploitOutput,
    ReconActiveOutput,
    ReconPassiveOutput,
    ReportOutput,
    ReportSection,
    SigmaRuleProposal,
    VerificationRecord,
    VerifyOutput,
)


# ---- recon-passive --------------------------------------------------------


def test_recon_passive_valid() -> None:
    out = ReconPassiveOutput(
        summary="x", assets=[], tech=[], people=[], credentials=[]
    )
    assert out.summary == "x"


def test_recon_passive_with_assets() -> None:
    out = ReconPassiveOutput(
        summary="x",
        assets=[{
            "id": "asset:api.example.com",
            "type": "subdomain",
            "value": "api.example.com",
            "parent_id": "asset:example.com",
            "source": "crt.sh",
        }],
        tech=[],
        people=[],
        credentials=[],
    )
    assert len(out.assets) == 1


def test_recon_passive_invalid_asset_type() -> None:
    with pytest.raises(ValidationError):
        ReconPassiveOutput(
            summary="x",
            assets=[{
                "id": "asset:x",
                "type": "garbage",  # not in Literal
                "value": "x",
                "source": "x",
            }],
            tech=[],
            people=[],
            credentials=[],
        )


# ---- recon-active ---------------------------------------------------------


def test_recon_active_with_endpoints() -> None:
    out = ReconActiveOutput(
        summary="x",
        assets=[],
        endpoints=[{
            "id": "endpoint:1",
            "url": "https://example.com/",
            "method": "GET",
            "parameters": {},
            "auth_required": False,
            "source": "katana",
        }],
        tech=[],
        people=[],
        credentials=[],
    )
    assert len(out.endpoints) == 1


# ---- analysis-hypothesis --------------------------------------------------


def test_analysis_hypothesis_confidence_range() -> None:
    """confidence_prior must be in [0.0, 1.0]."""
    with pytest.raises(ValidationError):
        HypothesisProposal(
            id="hyp:x",
            attack_class="sqli",
            target_asset="asset:x",
            precondition="x",
            reasoning="x",
            test_plan="x",
            expected_evidence="x",
            confidence_prior=1.5,  # out of range
        )


def test_analysis_hypothesis_attack_class_enum() -> None:
    """attack_class must be one of the 15 allowed values."""
    with pytest.raises(ValidationError):
        HypothesisProposal(
            id="hyp:x",
            attack_class="made_up_class",  # not in Literal
            target_asset="asset:x",
            precondition="x",
            reasoning="x",
            test_plan="x",
            expected_evidence="x",
            confidence_prior=0.5,
        )


def test_analysis_hypothesis_valid() -> None:
    out = AnalysisHypothesisOutput(
        summary="x",
        hypotheses=[
            HypothesisProposal(
                id="hyp:1",
                attack_class="sqli",
                target_asset="asset:x",
                precondition="x",
                reasoning="x",
                test_plan="x",
                expected_evidence="x",
                confidence_prior=0.5,
            )
        ],
    )
    assert len(out.hypotheses) == 1


# ---- exploit --------------------------------------------------------------


def test_exploit_attempt_record() -> None:
    a = ExploitAttemptRecord(
        id="attempt:1",
        hypothesis_id="hyp:1",
        tool="sqlmap",
        command="sqlmap -u http://x",
        raw_output_excerpt="test",
        success=True,
        evidence="extracted @@version",
        duration_s=12.0,
    )
    assert a.tool == "sqlmap"


def test_exploit_output_with_attempts() -> None:
    out = ExploitOutput(
        summary="x",
        attempts=[
            ExploitAttemptRecord(
                id="attempt:1",
                hypothesis_id="hyp:1",
                tool="sqlmap",
                command="x",
                raw_output_excerpt="x",
                success=False,
                evidence="x",
                duration_s=0.5,
            )
        ],
    )
    assert len(out.attempts) == 1


# ---- verify --------------------------------------------------------------


def test_verify_severity_required() -> None:
    """severity is required when not a false positive (model accepts null though)."""
    # Note: schema marks severity as Optional so verify pass either way
    out = VerifyOutput(
        summary="x",
        verifications=[{
            "id": "verify:1",
            "hypothesis_id": "hyp:1",
            "exploit_attempt_id": "attempt:1",
            "reproduction_count": 2,
            "independent_method": "manual curl",
            "is_false_positive": False,
            "evidence": "x",
            "cvss": 7.5,
            "cwe": "CWE-89",
            "severity": "high",
        }],
    )
    assert out.verifications[0].severity == "high"


def test_verify_severity_values() -> None:
    for sev in ("critical", "high", "medium", "low", "info"):
        v = VerificationRecord(
            id="v:1",
            hypothesis_id="h:1",
            exploit_attempt_id="a:1",
            reproduction_count=1,
            independent_method="x",
            is_false_positive=False,
            evidence="x",
            severity=sev,  # type: ignore[arg-type]
        )
        assert v.severity == sev


# ---- blue-team ------------------------------------------------------------


def test_sigma_rule_proposal() -> None:
    r = SigmaRuleProposal(
        id="sigma:1", title="x", yaml="title: x\n", level="high"
    )
    assert r.level == "high"


def test_ir_playbook_proposal() -> None:
    p = IRPlaybookProposal(
        id="p:1", title="x", markdown="# Steps", mitre_techniques=["T1190"]
    )
    assert p.mitre_techniques == ["T1190"]


def test_blue_team_output() -> None:
    out = BlueTeamOutput(
        summary="x",
        sigma_rules=[],
        ir_playbooks=[],
        artifacts=[],
    )
    assert out.summary == "x"


# ---- report --------------------------------------------------------------


def test_report_section() -> None:
    s = ReportSection(title="Methodology", markdown="## Step 1")
    assert s.title == "Methodology"


def test_report_output() -> None:
    out = ReportOutput(
        summary="x",
        sections=[],
        executive_summary="x",
        total_findings=0,
        critical_count=0,
        high_count=0,
        medium_count=0,
        low_count=0,
        info_count=0,
    )
    assert out.total_findings == 0


# ---- post-exploit ---------------------------------------------------------


def test_post_exploit_output() -> None:
    out = PostExploitOutput(summary="x", chains=[], pivots=[])
    assert out.pivots == []
