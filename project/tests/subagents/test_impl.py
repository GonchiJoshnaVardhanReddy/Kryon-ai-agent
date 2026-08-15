"""Tests for each of the 8 subagent implementations.

Each test wires a real ``MockLLMClient`` + real ``GraphStore``, runs the
subagent, and verifies the graph was updated correctly.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from kryon.graph.models import ExploitAttempt, Hypothesis
from kryon.subagents.base import MockLLMClient
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
from kryon.subagents.types import LLMResponse


# ---------------------------------------------------------------------------
# recon-passive
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_recon_passive_writes_assets(
    kryon_home, ctx, llm, graph, audit, bus, config
) -> None:
    response = """{
        "summary": "found 1 asset",
        "assets": [{"id": "asset:api.example.com", "type": "subdomain",
                    "value": "api.example.com", "parent_id": "asset:example.com",
                    "source": "crt.sh"}],
        "tech": [], "people": [], "credentials": [], "cost_estimate_usd": 0.0
    }"""
    llm.set_default(LLMResponse(content=response))
    sa = ReconPassiveSubagent(llm=llm, graph=graph, audit=audit, bus=bus, config=config)
    result = await sa.run(ctx)
    assert result.status.value == "completed"
    assert result.nodes_written == 1
    asset = graph.get_asset("asset:api.example.com")
    assert asset is not None
    assert asset.value == "api.example.com"


@pytest.mark.asyncio
async def test_recon_passive_marks_out_of_scope(
    kryon_home, ctx, llm, graph, audit, bus, config
) -> None:
    response = """{
        "summary": "found 1 OOS asset",
        "assets": [{"id": "asset:other.com", "type": "domain", "value": "other.com",
                    "source": "crt.sh"}],
        "tech": [], "people": [], "credentials": [], "cost_estimate_usd": 0.0
    }"""
    llm.set_default(LLMResponse(content=response))
    sa = ReconPassiveSubagent(llm=llm, graph=graph, audit=audit, bus=bus, config=config)
    result = await sa.run(ctx)
    assert result.nodes_written == 1
    asset = graph.get_asset("asset:other.com")
    assert asset is not None
    assert asset.in_scope is False  # other.com is not in scope


# ---------------------------------------------------------------------------
# recon-active
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_recon_active_writes_endpoints(
    kryon_home, ctx, llm, graph, audit, bus, config
) -> None:
    response = """{
        "summary": "found 1 endpoint",
        "assets": [],
        "endpoints": [{"id": "endpoint:1", "url": "https://example.com/",
                       "method": "GET", "parameters": {}, "auth_required": false,
                       "source": "katana"}],
        "tech": [], "people": [], "credentials": [], "cost_estimate_usd": 0.0
    }"""
    llm.set_default(LLMResponse(content=response))
    sa = ReconActiveSubagent(llm=llm, graph=graph, audit=audit, bus=bus, config=config)
    result = await sa.run(ctx)
    assert result.nodes_written == 1
    rows = graph.query("MATCH (e:Endpoint) RETURN e.url")
    assert rows[0][0] == "https://example.com/"


# ---------------------------------------------------------------------------
# analysis-hypothesis
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_analysis_hypothesis_writes_hypotheses(
    kryon_home, ctx, llm, graph, audit, bus, config
) -> None:
    response = """{
        "summary": "1 hypothesis",
        "hypotheses": [{
            "id": "hyp:test1234",
            "attack_class": "sqli",
            "target_asset": "asset:example.com",
            "target_endpoint": null,
            "precondition": "search endpoint reflects input",
            "reasoning": "classic SQLi surface",
            "test_plan": "send single quote",
            "expected_evidence": "SQL error",
            "confidence_prior": 0.5
        }],
        "cost_estimate_usd": 0.0
    }"""
    llm.set_default(LLMResponse(content=response))
    sa = AnalysisHypothesisSubagent(llm=llm, graph=graph, audit=audit, bus=bus, config=config)
    result = await sa.run(ctx)
    assert result.nodes_written == 1
    rows = graph.query("MATCH (h:Hypothesis) RETURN h.id, h.attack_class")
    assert rows[0][0] == "hyp:test1234"
    assert rows[0][1] == "sqli"


# ---------------------------------------------------------------------------
# exploit
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_exploit_writes_attempt(
    kryon_home, ctx, llm, graph, audit, bus, config
) -> None:
    ctx.extra["hypothesis"] = {
        "attack_class": "sqli",
        "target_asset": "asset:example.com",
        "test_plan": "1. send quote 2. observe",
        "expected_evidence": "error",
    }
    response = """{
        "summary": "attempted",
        "attempts": [{
            "id": "attempt:abcd1234",
            "hypothesis_id": "hyp:test1234",
            "tool": "sqlmap",
            "command": "sqlmap -u http://example.com/?id=1",
            "raw_output_excerpt": "test output",
            "success": true,
            "evidence": "MySQL version extracted",
            "duration_s": 12.5
        }],
        "cost_estimate_usd": 0.0
    }"""
    llm.set_default(LLMResponse(content=response))
    sa = ExploitSubagent(llm=llm, graph=graph, audit=audit, bus=bus, config=config)
    result = await sa.run(ctx)
    assert result.nodes_written == 1
    rows = graph.query("MATCH (a:ExploitAttempt) RETURN a.tool")
    assert rows[0][0] == "sqlmap"


# ---------------------------------------------------------------------------
# post-exploit
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_exploit_writes_chain(
    kryon_home, ctx, llm, graph, audit, bus, config
) -> None:
    response = """{
        "summary": "1 chain",
        "chains": [{
            "id": "chain:abcdef12",
            "name": "SSRF -> creds",
            "finding_ids": ["finding:1", "finding:2"],
            "root_cause": "SSRF",
            "impact": "cloud creds",
            "prerequisites": ["public metadata endpoint"],
            "steps": ["1. SSRF", "2. read metadata"]
        }],
        "pivots": [],
        "cost_estimate_usd": 0.0
    }"""
    llm.set_default(LLMResponse(content=response))
    sa = PostExploitSubagent(llm=llm, graph=graph, audit=audit, bus=bus, config=config)
    result = await sa.run(ctx)
    assert result.nodes_written == 1
    rows = graph.query("MATCH (c:ExploitChain) RETURN c.name")
    assert rows[0][0] == "SSRF -> creds"


# ---------------------------------------------------------------------------
# verify (THE TRUST BOUNDARY)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_verify_promotes_to_finding(
    kryon_home, ctx, llm, graph, audit, bus, config
) -> None:
    # Seed an ExploitAttempt (exploit subagent's write)
    now = datetime.now(timezone.utc)
    graph.upsert_exploit_attempt(
        ExploitAttempt(
            id="attempt:abcd1234",
            hypothesis_id="hyp:test1234",
            tool="sqlmap",
            raw_output="test",
            success=True,
            evidence="version 5.7",
            created_at=now,
        ),
        subagent_name="exploit",
    )
    ctx.extra["exploit_attempt_id"] = "attempt:abcd1234"

    response = """{
        "summary": "verified",
        "verifications": [{
            "id": "verify:test1234",
            "hypothesis_id": "hyp:test1234",
            "exploit_attempt_id": "attempt:abcd1234",
            "reproduction_count": 3,
            "independent_method": "manual curl + UNION SELECT",
            "is_false_positive": false,
            "evidence": "Reproduced 3 times, extracted @@version with UNION",
            "cvss": 8.5,
            "cwe": "CWE-89",
            "severity": "high"
        }],
        "cost_estimate_usd": 0.0
    }"""
    llm.set_default(LLMResponse(content=response))
    sa = VerifySubagent(llm=llm, graph=graph, audit=audit, bus=bus, config=config)
    result = await sa.run(ctx)
    assert result.status.value == "completed"
    assert result.nodes_written == 1  # 1 Finding
    findings = graph.query("MATCH (f:Finding) RETURN f.severity")
    assert findings[0][0] == "high"


@pytest.mark.asyncio
async def test_verify_rejects_false_positive(
    kryon_home, ctx, llm, graph, audit, bus, config
) -> None:
    graph.upsert_exploit_attempt(
        ExploitAttempt(
            id="attempt:fp123456",
            hypothesis_id="hyp:fp123456",
            tool="nuclei",
            raw_output="test",
            success=False,
            evidence="WAF block page",
            created_at=datetime.now(timezone.utc),
        ),
        subagent_name="exploit",
    )
    # Seed a hypothesis so we can verify it gets updated to rejected
    graph.upsert_hypothesis(
        Hypothesis(
            id="hyp:fp123456",
            target_id="tgt-1",
            attack_class="sqli",
            target_asset="asset:x",
            target_endpoint=None,
            precondition="x",
            reasoning="x",
            test_plan="x",
            expected_evidence="x",
            confidence_prior=0.5,
            status="testing",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        ),
        subagent_name="analysis-hypothesis",
    )
    ctx.extra["exploit_attempt_id"] = "attempt:fp123456"

    response = """{
        "summary": "false positive",
        "verifications": [{
            "id": "verify:fp123456",
            "hypothesis_id": "hyp:fp123456",
            "exploit_attempt_id": "attempt:fp123456",
            "reproduction_count": 0,
            "independent_method": "manual inspection of response",
            "is_false_positive": true,
            "rejection_reason": "Response is a Cloudflare WAF block page, not a SQL error",
            "evidence": "Raw HTML matches Cloudflare block template",
            "cvss": null,
            "cwe": null,
            "severity": null
        }],
        "cost_estimate_usd": 0.0
    }"""
    llm.set_default(LLMResponse(content=response))
    sa = VerifySubagent(llm=llm, graph=graph, audit=audit, bus=bus, config=config)
    result = await sa.run(ctx)
    assert result.status.value == "completed"
    assert result.nodes_written == 0  # no Finding
    rows = graph.query("MATCH (h:Hypothesis {id: 'hyp:fp123456'}) RETURN h.status")
    assert rows[0][0] == "rejected"


# ---------------------------------------------------------------------------
# blue-team
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_blue_team_writes_sigma_and_playbook(
    kryon_home, ctx, llm, graph, audit, bus, config
) -> None:
    response = """{
        "summary": "1 sigma + 1 playbook",
        "sigma_rules": [{
            "id": "sigma:test1234",
            "title": "SQLi Detection",
            "yaml": "title: Test\\nlevel: high\\n",
            "level": "high",
            "mitre_techniques": ["T1190"]
        }],
        "ir_playbooks": [{
            "id": "playbook:test1234",
            "title": "SQLi IR",
            "markdown": "# Steps\\n1. Block IP",
            "mitre_techniques": ["T1190"]
        }],
        "artifacts": [{"finding_id": "finding:1", "sigma_id": "sigma:test1234",
                       "playbook_id": "playbook:test1234"}],
        "cost_estimate_usd": 0.0
    }"""
    llm.set_default(LLMResponse(content=response))
    sa = BlueTeamSubagent(llm=llm, graph=graph, audit=audit, bus=bus, config=config)
    result = await sa.run(ctx)
    assert result.nodes_written == 3  # sigma + playbook + artifact
    title = graph.query("MATCH (r:SigmaRule) RETURN r.title")[0][0]
    assert title == "SQLi Detection"


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_report_does_not_write_to_graph(
    kryon_home, ctx, llm, graph, audit, bus, config
) -> None:
    response = """{
        "summary": "done",
        "executive_summary": "## Summary\\nWe found stuff.",
        "sections": [{"title": "Findings", "markdown": "# Findings"}],
        "total_findings": 0, "critical_count": 0, "high_count": 0,
        "medium_count": 0, "low_count": 0, "info_count": 0,
        "cost_estimate_usd": 0.0
    }"""
    llm.set_default(LLMResponse(content=response))
    sa = ReportSubagent(llm=llm, graph=graph, audit=audit, bus=bus, config=config)
    result = await sa.run(ctx)
    assert result.nodes_written == 0
