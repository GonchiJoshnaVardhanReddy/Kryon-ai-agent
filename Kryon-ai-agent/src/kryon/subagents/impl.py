"""The 8 subagent implementations.

Each subagent:
1. Knows which graph node types it can write (enforced by ``check_write_permission``)
2. Builds a context-specific user prompt (with current graph state)
3. Writes the parsed LLM output to the graph
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

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
from kryon.subagents.base import Subagent
from kryon.subagents.prompts import (
    ANALYSIS_HYPOTHESIS_PROMPT,
    BLUE_TEAM_PROMPT,
    EXPLOIT_PROMPT,
    POST_EXPLOIT_PROMPT,
    RECON_ACTIVE_PROMPT,
    RECON_PASSIVE_PROMPT,
    REPORT_PROMPT,
    VERIFY_PROMPT,
)
from kryon.subagents.schemas import (
    AnalysisHypothesisOutput,
    BlueTeamOutput,
    ExploitOutput,
    PostExploitOutput,
    ReconActiveOutput,
    ReconPassiveOutput,
    ReportOutput,
    VerifyOutput,
)
from kryon.subagents.types import SubagentContext


def _gen_id(prefix: str) -> str:
    return f"{prefix}:{uuid.uuid4().hex[:8]}"


def _format_rows(rows: list[list[Any]], max_rows: int = 10, cell_width: int = 60) -> list[str]:
    """Format rows from ``store.query()`` for prompt display."""
    if not rows:
        return ["  (none)"]
    out: list[str] = []
    for row in rows[:max_rows]:
        cells = [str(c)[:cell_width] for c in row]
        out.append("  " + " | ".join(cells))
    if len(rows) > max_rows:
        out.append(f"  ... and {len(rows) - max_rows} more")
    return out


def _in_scope(scope: Any, value: str) -> bool:
    """Check if a hostname or IP is in scope. Our Scope has no ``is_in_scope``."""
    return bool(scope.contains(value))


# ============================================================================
# recon-passive
# ============================================================================


class ReconPassiveSubagent(Subagent):
    name = "recon-passive"
    description = "Passive reconnaissance (no direct traffic)"
    SYSTEM_PROMPT = RECON_PASSIVE_PROMPT
    OUTPUT_SCHEMA = ReconPassiveOutput

    def build_user_prompt(self, ctx: SubagentContext) -> str:
        domains = ", ".join(ctx.scope.domains)
        ips = ", ".join(ctx.scope.ips)
        return (
            f"Conduct passive reconnaissance on the following target.\n\n"
            f"Target: {ctx.target.name} ({ctx.target.slug})\n"
            f"Domains: {domains}\n"
            f"IPs: {ips}\n"
            f"Authorization: confirmed\n"
            f"\nUse ONLY passive sources (crt.sh, WHOIS, Shodan, GitHub search, etc.).\n"
            f"Do NOT send any traffic to the target directly.\n"
            f"\nRespond with valid JSON matching the schema. No prose, no markdown fences.\n"
        )

    async def write_to_graph(  # type: ignore[override]
        self, output: ReconPassiveOutput, ctx: SubagentContext
    ) -> int:
        n = 0
        now = datetime.now(UTC)
        for a in output.assets:
            in_scope = _in_scope(ctx.scope, a.value)
            self._graph.upsert_asset(
                Asset(
                    id=a.id,
                    type=a.type,
                    value=a.value,
                    parent_id=a.parent_id,
                    in_scope=in_scope,
                    source=a.source,
                    discovered_at=now,
                ),
                subagent_name=self.name,
            )
            n += 1
        for t in output.tech:
            self._graph.upsert_tech(
                Tech(id=t.id, name=t.name, version=t.version, category=t.category),
                subagent_name=self.name,
            )
            n += 1
        for p in output.people:
            self._graph.upsert_person(
                Person(
                    id=p.id,
                    name=p.name,
                    email=p.email,
                    role=p.role,
                    source=p.source,
                    confidence=p.confidence,
                    discovered_at=now,
                ),
                subagent_name=self.name,
            )
            n += 1
        for c in output.credentials:
            self._graph.upsert_credential(
                Credential(
                    id=c.id,
                    type=c.type,
                    value=c.value,
                    source=c.source,
                    valid=True,
                    discovered_at=now,
                ),
                subagent_name=self.name,
            )
            n += 1
        return n


# ============================================================================
# recon-active
# ============================================================================


class ReconActiveSubagent(Subagent):
    name = "recon-active"
    description = "Active reconnaissance (sends traffic to target)"
    SYSTEM_PROMPT = RECON_ACTIVE_PROMPT
    OUTPUT_SCHEMA = ReconActiveOutput

    def build_user_prompt(self, ctx: SubagentContext) -> str:
        return (
            f"Conduct active reconnaissance on the following target.\n\n"
            f"Target: {ctx.target.name} ({ctx.target.slug})\n"
            f"Scope: domains={ctx.scope.domains}, ips={ctx.scope.ips}, "
            f"exclude={ctx.scope.excluded_paths}\n"
            f"Authorization: confirmed\n"
            f"\nSend controlled traffic to enumerate the live attack surface.\n"
            f"Respect scope and rate limits (max 10 req/s per host).\n"
            f"\nRespond with valid JSON matching the schema. No prose, no markdown fences.\n"
        )

    async def write_to_graph(  # type: ignore[override]
        self, output: ReconActiveOutput, ctx: SubagentContext
    ) -> int:
        n = 0
        now = datetime.now(UTC)
        for a in output.assets:
            in_scope = _in_scope(ctx.scope, a.value)
            self._graph.upsert_asset(
                Asset(
                    id=a.id,
                    type=a.type,
                    value=a.value,
                    parent_id=a.parent_id,
                    in_scope=in_scope,
                    source=a.source,
                    discovered_at=now,
                ),
                subagent_name=self.name,
            )
            n += 1
        for e in output.endpoints:
            self._graph.upsert_endpoint(
                Endpoint(
                    id=e.id,
                    url=e.url,
                    method=e.method,
                    parameters=e.parameters,
                    auth_required=e.auth_required,
                    source=e.source,
                    discovered_at=now,
                ),
                subagent_name=self.name,
            )
            n += 1
        for t in output.tech:
            self._graph.upsert_tech(
                Tech(id=t.id, name=t.name, version=t.version, category=t.category),
                subagent_name=self.name,
            )
            n += 1
        for p in output.people:
            self._graph.upsert_person(
                Person(
                    id=p.id,
                    name=p.name,
                    email=p.email,
                    role=p.role,
                    source=p.source,
                    confidence=p.confidence,
                    discovered_at=now,
                ),
                subagent_name=self.name,
            )
            n += 1
        for c in output.credentials:
            self._graph.upsert_credential(
                Credential(
                    id=c.id,
                    type=c.type,
                    value=c.value,
                    source=c.source,
                    valid=True,
                    discovered_at=now,
                ),
                subagent_name=self.name,
            )
            n += 1
        return n


# ============================================================================
# analysis-hypothesis
# ============================================================================


class AnalysisHypothesisSubagent(Subagent):
    name = "analysis-hypothesis"
    description = "Generate vulnerability hypotheses from recon output"
    SYSTEM_PROMPT = ANALYSIS_HYPOTHESIS_PROMPT
    OUTPUT_SCHEMA = AnalysisHypothesisOutput

    def build_user_prompt(self, ctx: SubagentContext) -> str:
        in_scope_assets = self._graph.query(
            "MATCH (a:Asset {in_scope: true}) RETURN a.id, a.type, a.value"
        )
        endpoints = self._graph.query(
            "MATCH (e:Endpoint) RETURN e.id, e.url, e.method, e.auth_required"
        )
        techs = self._graph.query("MATCH (t:Tech) RETURN t.id, t.name, t.version, t.category")
        existing_hyps = self._graph.query(
            "MATCH (h:Hypothesis) RETURN h.attack_class, h.target_asset"
        )

        return (
            f"Generate 3-10 vulnerability hypotheses for the following target.\n\n"
            f"Target: {ctx.target.name} ({ctx.target.slug})\n"
            f"Authorization: confirmed\n"
            f"\n## Known attack surface\n"
            f"In-scope assets ({len(in_scope_assets)}):\n"
            + "\n".join(_format_rows(in_scope_assets, max_rows=10))
            + f"\n\nEndpoints ({len(endpoints)}):\n"
            + "\n".join(_format_rows(endpoints, max_rows=10))
            + f"\n\nTech stack ({len(techs)}):\n"
            + "\n".join(_format_rows(techs, max_rows=10))
            + "\n\n## Existing hypotheses (do not duplicate)\n"
            + "\n".join(_format_rows(existing_hyps, max_rows=10))
            + "\n\nGenerate hypotheses that:\n"
            "- Are specific to the known tech and endpoints\n"
            "- Have a realistic test plan\n"
            "- Estimate confidence honestly\n"
            "- Do NOT duplicate existing hypotheses\n"
            "\nRespond with valid JSON matching the schema. No prose, no markdown fences.\n"
        )

    async def write_to_graph(  # type: ignore[override]
        self, output: AnalysisHypothesisOutput, ctx: SubagentContext
    ) -> int:
        n = 0
        now = datetime.now(UTC)
        for h in output.hypotheses:
            self._graph.upsert_hypothesis(
                Hypothesis(
                    id=h.id,
                    target_id=ctx.target.id,
                    attack_class=h.attack_class,
                    target_asset=h.target_asset,
                    target_endpoint=h.target_endpoint,
                    precondition=h.precondition,
                    reasoning=h.reasoning,
                    test_plan=h.test_plan,
                    expected_evidence=h.expected_evidence,
                    confidence_prior=h.confidence_prior,
                    created_at=now,
                    updated_at=now,
                    generated_by=self.name,
                ),
                subagent_name=self.name,
            )
            n += 1
        return n


# ============================================================================
# exploit
# ============================================================================


class ExploitSubagent(Subagent):
    name = "exploit"
    description = "Execute exploits and capture evidence"
    SYSTEM_PROMPT = EXPLOIT_PROMPT
    OUTPUT_SCHEMA = ExploitOutput

    def build_user_prompt(self, ctx: SubagentContext) -> str:
        hyp = ctx.extra.get("hypothesis")
        if not hyp:
            return "No hypothesis provided."
        return (
            f"Execute the following hypothesis test plan.\n\n"
            f"Hypothesis: {hyp.get('attack_class')} on {hyp.get('target_asset')}\n"
            f"Endpoint: {hyp.get('target_endpoint', 'N/A')}\n"
            f"Precondition: {hyp.get('precondition')}\n"
            f"Test plan:\n{hyp.get('test_plan')}\n"
            f"Expected evidence: {hyp.get('expected_evidence')}\n"
            f"\nScope: domains={ctx.scope.domains}\n"
            f"Authorization: confirmed\n"
            f"\nExecute the test, capture evidence, report outcome.\n"
            f"DO NOT promote to a Finding. DO NOT exceed scope.\n"
            f"\nRespond with valid JSON matching the schema. No prose, no markdown fences.\n"
        )

    async def write_to_graph(  # type: ignore[override]
        self, output: ExploitOutput, ctx: SubagentContext
    ) -> int:
        n = 0
        now = datetime.now(UTC)
        for a in output.attempts:
            self._graph.upsert_exploit_attempt(
                ExploitAttempt(
                    id=a.id,
                    hypothesis_id=a.hypothesis_id,
                    tool=a.tool,
                    raw_output=a.raw_output_excerpt,
                    success=a.success,
                    evidence=a.evidence,
                    created_at=now,
                ),
                subagent_name=self.name,
            )
            self._graph.link_exploit_to_hypothesis(a.id, a.hypothesis_id)
            n += 1
        return n


# ============================================================================
# post-exploit
# ============================================================================


class PostExploitSubagent(Subagent):
    name = "post-exploit"
    description = "Construct exploit chains from confirmed findings"
    SYSTEM_PROMPT = POST_EXPLOIT_PROMPT
    OUTPUT_SCHEMA = PostExploitOutput

    def build_user_prompt(self, ctx: SubagentContext) -> str:
        findings = self._graph.query(
            "MATCH (f:Finding {status: 'confirmed'}) "
            "RETURN f.id, f.title, f.severity, f.attack_class"
        )
        return (
            f"Find exploit chains among the following confirmed findings.\n\n"
            f"Target: {ctx.target.name}\n"
            f"Confirmed findings ({len(findings)}):\n"
            + "\n".join(_format_rows(findings, max_rows=10))
            + "\n\nChains must:\n"
            "- Use only confirmed findings\n"
            "- Demonstrate COMPOUNDED impact (not just the sum of parts)\n"
            "- Not require out-of-scope actions\n"
            "\nRespond with valid JSON matching the schema. No prose, no markdown fences.\n"
        )

    async def write_to_graph(  # type: ignore[override]
        self, output: PostExploitOutput, ctx: SubagentContext
    ) -> int:
        n = 0
        now = datetime.now(UTC)
        for c in output.chains:
            self._graph.upsert_exploit_chain(
                ExploitChain(
                    id=c.id,
                    name=c.name,
                    finding_ids=c.finding_ids,
                    root_cause=c.root_cause,
                    impact=c.impact,
                    discovered_at=now,
                ),
                subagent_name=self.name,
            )
            n += 1
        return n


# ============================================================================
# verify (THE TRUST BOUNDARY)
# ============================================================================


class VerifySubagent(Subagent):
    name = "verify"
    description = "Verify exploit attempts and promote to Findings (or reject as false positives)"
    SYSTEM_PROMPT = VERIFY_PROMPT
    OUTPUT_SCHEMA = VerifyOutput

    def build_user_prompt(self, ctx: SubagentContext) -> str:
        attempt_id = ctx.extra.get("exploit_attempt_id")
        if not attempt_id:
            return "No exploit_attempt_id provided."

        attempts = self._graph.query(
            "MATCH (a:ExploitAttempt {id: $id}) "
            "RETURN a.id, a.hypothesis_id, a.tool, a.raw_output, a.success, a.evidence",
            {"id": attempt_id},
        )
        if not attempts:
            return f"ExploitAttempt {attempt_id} not found."

        attempt = attempts[0]
        hyp_id = attempt[1]
        hyps = self._graph.query(
            "MATCH (h:Hypothesis {id: $id}) "
            "RETURN h.id, h.target_id, h.attack_class, h.target_asset, "
            "h.target_endpoint, h.reasoning, h.test_plan, h.expected_evidence",
            {"id": hyp_id},
        )
        hyp = hyps[0] if hyps else None

        return (
            f"Verify the following exploit attempt.\n\n"
            f"Exploit attempt:\n"
            f"  ID: {attempt[0]}\n"
            f"  Tool: {attempt[2]}\n"
            f"  Success (claimed): {attempt[4]}\n"
            f"  Evidence (claimed): {attempt[5]}\n"
            f"\nHypothesis:\n"
            f"  ID: {hyp[0] if hyp else 'unknown'}\n"
            f"  Attack class: {hyp[2] if hyp else 'unknown'}\n"
            f"  Target asset: {hyp[3] if hyp else 'unknown'}\n"
            f"  Expected evidence: {hyp[7] if hyp else 'unknown'}\n"
            f"\nCRITICAL: Do NOT trust the claim. Reproduce 2+ times. Use a SECOND METHOD.\n"
            f"Check for false positives. Assign severity honestly.\n"
            f"\nRespond with valid JSON matching the schema. No prose, no markdown fences.\n"
        )

    async def write_to_graph(  # type: ignore[override]
        self, output: VerifyOutput, ctx: SubagentContext
    ) -> int:
        n = 0
        now = datetime.now(UTC)
        for v in output.verifications:
            if v.is_false_positive:
                # Update the hypothesis to rejected
                self._graph.update_hypothesis_status(
                    v.hypothesis_id,
                    "rejected",
                    subagent_name=self.name,
                    rejection_reason=v.rejection_reason,
                )
                continue
            # Promote to Finding
            finding = Finding(
                id=_gen_id("finding"),
                title=f"Verified {v.evidence[:50]}",
                severity=v.severity or "info",
                attack_class="verified",
                cwe=v.cwe,
                cvss=v.cvss,
                status="confirmed",
                confidence=0.95,
                affected_asset_id=v.hypothesis_id,
                evidence=v.evidence,
                reproduction_count=v.reproduction_count,
                created_at=now,
                confirmed_at=now,
            )
            self._graph.upsert_finding(finding, subagent_name=self.name)
            # Link finding to hypothesis
            self._graph.update_hypothesis_status(
                v.hypothesis_id,
                "confirmed",
                subagent_name=self.name,
                finding_id=finding.id,
            )
            n += 1
        return n


# ============================================================================
# blue-team
# ============================================================================


class BlueTeamSubagent(Subagent):
    name = "blue-team"
    description = "Generate Sigma rules + IR playbooks for findings"
    SYSTEM_PROMPT = BLUE_TEAM_PROMPT
    OUTPUT_SCHEMA = BlueTeamOutput

    def build_user_prompt(self, ctx: SubagentContext) -> str:
        findings = self._graph.query(
            "MATCH (f:Finding {status: 'confirmed'}) "
            "RETURN f.id, f.title, f.severity, f.attack_class, f.cwe"
        )
        return (
            f"Generate defensive artifacts for the following findings.\n\n"
            f"Target: {ctx.target.name}\n"
            f"Confirmed findings ({len(findings)}):\n"
            + "\n".join(_format_rows(findings, max_rows=10))
            + "\n\nFor EACH finding, generate:\n"
            "1. A Sigma rule (valid YAML) that detects the EXPLOIT\n"
            "2. An IR playbook (markdown) with trigger, triage, "
            "containment, eradication, recovery\n"
            "\nSigma rules must be VALID YAML.\n"
            "Playbooks must be SPECIFIC (not boilerplate).\n"
            "\nRespond with valid JSON matching the schema. No prose, no markdown fences.\n"
        )

    async def write_to_graph(  # type: ignore[override]
        self, output: BlueTeamOutput, ctx: SubagentContext
    ) -> int:
        n = 0
        now = datetime.now(UTC)
        for r in output.sigma_rules:
            self._graph.upsert_sigma_rule(
                SigmaRule(
                    id=r.id,
                    title=r.title,
                    yaml=r.yaml,
                    level=r.level,
                ),
                subagent_name=self.name,
            )
            n += 1
        for p in output.ir_playbooks:
            self._graph.upsert_ir_playbook(
                IRPlaybook(id=p.id, title=p.title, markdown=p.markdown),
                subagent_name=self.name,
            )
            n += 1
        for a in output.artifacts:
            artifact = DefensiveArtifact(
                id=_gen_id("artifact"),
                finding_id=a.get("finding_id", ""),
                sigma_rule_id=a.get("sigma_id", ""),
                ir_playbook_id=a.get("playbook_id", ""),
                generated_at=now,
            )
            self._graph.upsert_defensive_artifact(artifact, subagent_name=self.name)
            n += 1
        return n


# ============================================================================
# report
# ============================================================================


class ReportSubagent(Subagent):
    name = "report"
    description = "Render final report (writes to file system, not graph)"
    SYSTEM_PROMPT = REPORT_PROMPT
    OUTPUT_SCHEMA = ReportOutput

    def build_user_prompt(self, ctx: SubagentContext) -> str:
        findings = self._graph.query(
            "MATCH (f:Finding) RETURN f.id, f.title, f.severity, f.attack_class"
        )
        chains = self._graph.query("MATCH (c:ExploitChain) RETURN c.id, c.name, c.impact")
        artifacts = self._graph.query("MATCH (a:DefensiveArtifact) RETURN a.id, a.finding_id")
        return (
            f"Generate the final report.\n\n"
            f"Target: {ctx.target.name} ({ctx.target.slug})\n"
            f"Authorization: confirmed\n"
            f"Scope: domains={ctx.scope.domains}, ips={ctx.scope.ips}\n"
            f"\nFindings ({len(findings)}):\n"
            + "\n".join(_format_rows(findings, max_rows=10))
            + f"\n\nExploit chains ({len(chains)}):\n"
            + "\n".join(_format_rows(chains, max_rows=10))
            + f"\n\nDefensive artifacts ({len(artifacts)}):\n"
            + "\n".join(_format_rows(artifacts, max_rows=10))
            + "\n\nGenerate a professional report with executive summary + full sections.\n"
            "Use markdown for all body content.\n"
            "\nRespond with valid JSON matching the schema. No prose, no markdown fences.\n"
        )

    async def write_to_graph(  # type: ignore[override]
        self, output: ReportOutput, ctx: SubagentContext
    ) -> int:
        # Report subagent does NOT write to the graph.
        # Reports go to the file system (handled in File #12).
        return 0


__all__ = [
    "AnalysisHypothesisSubagent",
    "BlueTeamSubagent",
    "ExploitSubagent",
    "PostExploitSubagent",
    "ReconActiveSubagent",
    "ReconPassiveSubagent",
    "ReportSubagent",
    "VerifySubagent",
]
