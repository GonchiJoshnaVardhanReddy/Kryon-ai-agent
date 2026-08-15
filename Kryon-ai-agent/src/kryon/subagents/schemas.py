"""Output schemas for all 8 subagents (Pydantic v2).

These are the JSON shapes the LLM must produce. The base class validates
against them via ``model_validate_json``.

The schemas are the contract that constrains the LLM. The system prompt
(File #5 prompts) describes the shape in prose; the Pydantic schema
enforces it. A response that doesn't match the schema triggers a
parse error → up to 2 retries → FAIL.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

# ============================================================================
# recon-passive
# ============================================================================


class DiscoveredAsset(BaseModel):
    id: str
    type: Literal["domain", "subdomain", "ip", "repo", "certificate", "service", "url"]
    value: str
    parent_id: str | None = None
    source: str
    notes: str | None = None


class DiscoveredTech(BaseModel):
    id: str
    name: str
    version: str | None = None
    category: Literal["framework", "language", "waf", "cdn", "db", "server", "os", "other"]


class DiscoveredPerson(BaseModel):
    id: str
    name: str
    email: str | None = None
    role: str | None = None
    source: str
    confidence: float = 1.0


class DiscoveredCredential(BaseModel):
    id: str
    type: Literal["password", "api_key", "token", "session", "cookie"]
    value: str
    source: str
    notes: str | None = None


class ReconPassiveOutput(BaseModel):
    summary: str
    assets: list[DiscoveredAsset] = Field(default_factory=list)
    tech: list[DiscoveredTech] = Field(default_factory=list)
    people: list[DiscoveredPerson] = Field(default_factory=list)
    credentials: list[DiscoveredCredential] = Field(default_factory=list)
    cost_estimate_usd: float = 0.0


# ============================================================================
# recon-active
# ============================================================================


class DiscoveredEndpoint(BaseModel):
    id: str
    url: str
    method: Literal["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS", "*"]
    parameters: dict[str, Any] = Field(default_factory=dict)
    auth_required: bool = False
    source: str
    notes: str | None = None


class ReconActiveOutput(BaseModel):
    summary: str
    assets: list[DiscoveredAsset] = Field(default_factory=list)
    endpoints: list[DiscoveredEndpoint] = Field(default_factory=list)
    tech: list[DiscoveredTech] = Field(default_factory=list)
    people: list[DiscoveredPerson] = Field(default_factory=list)
    credentials: list[DiscoveredCredential] = Field(default_factory=list)
    cost_estimate_usd: float = 0.0


# ============================================================================
# analysis-hypothesis (the core innovation)
# ============================================================================


class HypothesisProposal(BaseModel):
    id: str
    # The 15 attack classes the analysis-hypothesis subagent is allowed to propose.
    # Restricted so the LLM can't invent weird classes that downstream code doesn't know.
    attack_class: Literal[
        "sqli",
        "xss",
        "idor",
        "ssrf",
        "rce",
        "lfi",
        "rfi",
        "xxe",
        "auth_bypass",
        "csrf",
        "race_condition",
        "deserialization",
        "open_redirect",
        "business_logic",
        "other",
    ]
    target_asset: str
    target_endpoint: str | None = None
    precondition: str
    reasoning: str
    test_plan: str
    expected_evidence: str
    confidence_prior: float = Field(ge=0.0, le=1.0)


class AnalysisHypothesisOutput(BaseModel):
    summary: str
    hypotheses: list[HypothesisProposal]
    cost_estimate_usd: float = 0.0


# ============================================================================
# exploit
# ============================================================================


class ExploitAttemptRecord(BaseModel):
    id: str
    hypothesis_id: str
    tool: str
    command: str
    raw_output_excerpt: str
    success: bool
    evidence: str
    duration_s: float
    notes: str | None = None


class ExploitOutput(BaseModel):
    summary: str
    attempts: list[ExploitAttemptRecord]
    cost_estimate_usd: float = 0.0


# ============================================================================
# post-exploit
# ============================================================================


class ExploitChainProposal(BaseModel):
    id: str
    name: str
    finding_ids: list[str]
    root_cause: str
    impact: str
    prerequisites: list[str] = Field(default_factory=list)
    steps: list[str]
    cost_estimate_usd: float = 0.0


class PostExploitOutput(BaseModel):
    summary: str
    chains: list[ExploitChainProposal]
    pivots: list[str] = Field(default_factory=list)
    cost_estimate_usd: float = 0.0


# ============================================================================
# verify (THE TRUST BOUNDARY)
# ============================================================================


class VerificationRecord(BaseModel):
    id: str
    hypothesis_id: str
    exploit_attempt_id: str
    reproduction_count: int
    independent_method: str
    is_false_positive: bool
    rejection_reason: str | None = None
    evidence: str
    cvss: float | None = None
    cwe: str | None = None
    severity: Literal["critical", "high", "medium", "low", "info"] | None = None


class VerifyOutput(BaseModel):
    summary: str
    verifications: list[VerificationRecord]
    cost_estimate_usd: float = 0.0


# ============================================================================
# blue-team
# ============================================================================


class SigmaRuleProposal(BaseModel):
    id: str
    title: str
    yaml: str
    level: Literal["critical", "high", "medium", "low", "informational"]
    mitre_techniques: list[str] = Field(default_factory=list)


class IRPlaybookProposal(BaseModel):
    id: str
    title: str
    markdown: str
    mitre_techniques: list[str] = Field(default_factory=list)


class BlueTeamOutput(BaseModel):
    summary: str
    sigma_rules: list[SigmaRuleProposal] = Field(default_factory=list)
    ir_playbooks: list[IRPlaybookProposal] = Field(default_factory=list)
    artifacts: list[dict[str, str]] = Field(default_factory=list)
    cost_estimate_usd: float = 0.0


# ============================================================================
# report
# ============================================================================


class ReportSection(BaseModel):
    title: str
    markdown: str


class ReportOutput(BaseModel):
    summary: str
    sections: list[ReportSection]
    executive_summary: str
    total_findings: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    info_count: int
    cost_estimate_usd: float = 0.0


__all__ = [
    "AnalysisHypothesisOutput",
    "BlueTeamOutput",
    "DiscoveredAsset",
    "DiscoveredCredential",
    "DiscoveredEndpoint",
    "DiscoveredPerson",
    "DiscoveredTech",
    "ExploitAttemptRecord",
    "ExploitChainProposal",
    "ExploitOutput",
    "HypothesisProposal",
    "IRPlaybookProposal",
    "PostExploitOutput",
    "ReconActiveOutput",
    "ReconPassiveOutput",
    "ReportOutput",
    "ReportSection",
    "SigmaRuleProposal",
    "VerificationRecord",
    "VerifyOutput",
]
