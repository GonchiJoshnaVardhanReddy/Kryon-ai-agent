"""Tests for graph node type models (Pydantic validation)."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from kryon.graph.models import (
    Asset,
    Credential,
    DefensiveArtifact,
    Endpoint,
    ExploitAttempt,
    ExploitChain,
    Finding,
    Hypothesis,
    IRPlaybook,
    Person,
    SigmaRule,
    Tech,
)


# ---- Asset ----------------------------------------------------------------


def test_asset_creation() -> None:
    a = Asset(
        id="asset:example.com",
        type="domain",
        value="example.com",
        source="subfinder",
        discovered_at=datetime.now(timezone.utc),
    )
    assert a.id == "asset:example.com"
    assert a.in_scope is True
    assert a.parent_id is None


def test_asset_invalid_type() -> None:
    with pytest.raises(ValidationError):
        Asset(
            id="x",
            type="not_a_type",  # type: ignore[arg-type]
            value="x",
            source="x",
            discovered_at=datetime.now(timezone.utc),
        )


def test_asset_all_types_valid() -> None:
    for t in (
        "domain",
        "subdomain",
        "ip",
        "repo",
        "service",
        "url",
        "certificate",
    ):
        Asset(
            id=f"asset:{t}",
            type=t,  # type: ignore[arg-type]
            value="x",
            source="x",
            discovered_at=datetime.now(timezone.utc),
        )


# ---- Endpoint -------------------------------------------------------------


def test_endpoint_creation() -> None:
    e = Endpoint(
        id="endpoint:GET_/api/users",
        url="https://api.example.com/users",
        method="GET",
        parameters={"q": "search"},
        source="katana",
        discovered_at=datetime.now(timezone.utc),
    )
    assert e.method == "GET"
    assert e.auth_required is False
    assert e.parameters == {"q": "search"}


def test_endpoint_invalid_method() -> None:
    with pytest.raises(ValidationError):
        Endpoint(
            id="x",
            url="x",
            method="FOOBAR",  # type: ignore[arg-type]
            source="x",
            discovered_at=datetime.now(timezone.utc),
        )


def test_endpoint_default_params() -> None:
    e = Endpoint(
        id="x",
        url="x",
        method="*",
        source="x",
        discovered_at=datetime.now(timezone.utc),
    )
    assert e.parameters == {}


# ---- Tech -----------------------------------------------------------------


def test_tech_creation() -> None:
    t = Tech(id="tech:cloudflare", name="Cloudflare", version="unknown", category="waf")
    assert t.category == "waf"
    assert t.version == "unknown"


def test_tech_no_version() -> None:
    t = Tech(id="t:php", name="PHP", category="language")
    assert t.version is None


def test_tech_invalid_category() -> None:
    with pytest.raises(ValidationError):
        Tech(id="x", name="x", category="not_a_category")  # type: ignore[arg-type]


# ---- Person ---------------------------------------------------------------


def test_person_creation() -> None:
    p = Person(
        id="person:1",
        name="Alice",
        email="alice@example.com",
        role="admin",
        source="github",
        discovered_at=datetime.now(timezone.utc),
    )
    assert p.name == "Alice"
    assert p.confidence == 1.0


def test_person_minimal() -> None:
    p = Person(
        id="person:2",
        name="Bob",
        source="x",
        discovered_at=datetime.now(timezone.utc),
    )
    assert p.email is None
    assert p.role is None


# ---- Finding --------------------------------------------------------------


def test_finding_creation() -> None:
    f = Finding(
        id="finding:1",
        title="IDOR in /api/users/{id}",
        severity="high",
        attack_class="idor",
        affected_asset_id="asset:api.example.com",
        evidence="Test response included victim data",
        created_at=datetime.now(timezone.utc),
        confirmed_at=datetime.now(timezone.utc),
    )
    assert f.severity == "high"
    assert f.status == "confirmed"  # default
    assert f.confidence == 1.0


def test_finding_severity_values() -> None:
    for sev in ("critical", "high", "medium", "low", "info"):
        Finding(
            id=f"f:{sev}",
            title="x",
            severity=sev,  # type: ignore[arg-type]
            attack_class="other",
            affected_asset_id="x",
            evidence="x",
            created_at=datetime.now(timezone.utc),
            confirmed_at=datetime.now(timezone.utc),
        )


def test_finding_invalid_severity() -> None:
    with pytest.raises(ValidationError):
        Finding(
            id="x",
            title="x",
            severity="super-critical",  # type: ignore[arg-type]
            attack_class="other",
            affected_asset_id="x",
            evidence="x",
            created_at=datetime.now(timezone.utc),
            confirmed_at=datetime.now(timezone.utc),
        )


# ---- Credential -----------------------------------------------------------


def test_credential_creation() -> None:
    c = Credential(
        id="cred:1",
        type="password",
        value="hunter2",
        source="leaked",
        discovered_at=datetime.now(timezone.utc),
    )
    assert c.value == "hunter2"
    assert c.valid is True


# ---- Hypothesis (the core innovation) -------------------------------------


def test_hypothesis_schema() -> None:
    """The Hypothesis schema is the core innovation — verify it validates cleanly."""
    hyp = Hypothesis(
        id="hyp:1",
        target_id="tgt:1",
        attack_class="sqli",
        target_asset="asset:example.com",
        target_endpoint="endpoint:GET_/search",
        precondition="The /search endpoint reflects user input",
        reasoning="Classic SQLi surface for PHP-MySQL stack",
        test_plan="1. Send single quote\n2. Check for SQL error",
        expected_evidence="SQL error message in response",
        confidence_prior=0.5,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    assert hyp.confidence_prior == 0.5
    assert hyp.status == "pending"  # default
    assert hyp.attempts == 0
    assert hyp.cost_spent == 0.0
    assert hyp.generated_by == "analysis-hypothesis"  # default


def test_hypothesis_status_values() -> None:
    for s in (
        "pending",
        "testing",
        "verifying",
        "confirmed",
        "rejected",
        "exhausted",
    ):
        Hypothesis(
            id=f"h:{s}",
            target_id="t",
            attack_class="other",
            target_asset="a",
            target_endpoint=None,
            precondition="x",
            reasoning="x",
            test_plan="x",
            expected_evidence="x",
            confidence_prior=0.0,
            status=s,  # type: ignore[arg-type]
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )


# ---- ExploitAttempt -------------------------------------------------------


def test_exploit_attempt_creation() -> None:
    a = ExploitAttempt(
        id="attempt:1",
        hypothesis_id="hyp:1",
        tool="sqlmap",
        raw_output="lots of output...",
        success=False,
        evidence="no error returned",
        created_at=datetime.now(timezone.utc),
    )
    assert a.tool == "sqlmap"
    assert a.success is False


# ---- SigmaRule ------------------------------------------------------------


def test_sigma_rule_creation() -> None:
    r = SigmaRule(
        id="sigma:1",
        title="Detect SQLi error strings",
        yaml="title: x\nlogsource: x\n",
        level="high",
    )
    assert r.status == "experimental"  # default


# ---- IRPlaybook -----------------------------------------------------------


def test_ir_playbook_creation() -> None:
    p = IRPlaybook(id="ir:1", title="SQLi response", markdown="## Steps\n1. ...")
    assert p.title == "SQLi response"


# ---- DefensiveArtifact ----------------------------------------------------


def test_defensive_artifact_creation() -> None:
    a = DefensiveArtifact(
        id="da:1",
        finding_id="finding:1",
        sigma_rule_id="sigma:1",
        ir_playbook_id="ir:1",
        mitre_techniques=["T1190"],
        generated_at=datetime.now(timezone.utc),
    )
    assert a.mitre_techniques == ["T1190"]


# ---- ExploitChain ---------------------------------------------------------


def test_exploit_chain_creation() -> None:
    c = ExploitChain(
        id="chain:1",
        name="SSRF → metadata → creds",
        finding_ids=["f:1", "f:2"],
        root_cause="SSRF in image proxy",
        impact="Cloud creds exfil",
        discovered_at=datetime.now(timezone.utc),
    )
    assert len(c.finding_ids) == 2
