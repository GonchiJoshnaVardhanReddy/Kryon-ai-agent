"""Pydantic models for all knowledge graph node types.

The knowledge graph is the substrate of structured autonomy. Every
piece of recon, every hypothesis, every exploit attempt, every finding
is a typed node. The schema forces the LLM to think in a structured
way (claim, reasoning, test plan, expected evidence) instead of
free-form text.

Node types fall into three buckets:

1. **Core entities** — passive/active recon output (Asset, Endpoint,
   Tech, Person, Credential). Read by all subagents.
2. **Findings** — confirmed vulnerabilities. ONLY the ``verify``
   subagent can write these. This is the trust model.
3. **Working types** — hypotheses, exploit attempts, defensive
   artifacts, exploit chains. Created and updated during the loop.

Every node has a unique string ``id`` (e.g., ``"asset:example.com"``)
so lookups are O(1) without a separate index.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

# ============================================================================
# Core entities
# ============================================================================


class Asset(BaseModel):
    """A network asset (domain, subdomain, IP, repo, etc.)."""

    id: str
    type: Literal["domain", "subdomain", "ip", "repo", "service", "url", "certificate"]
    value: str
    parent_id: str | None = None
    in_scope: bool = True
    source: str
    discovered_at: datetime


class Endpoint(BaseModel):
    """A URL or service endpoint."""

    id: str
    url: str
    method: Literal["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS", "*"]
    parameters: dict[str, Any] = Field(default_factory=dict)
    auth_required: bool = False
    source: str
    discovered_at: datetime


class Tech(BaseModel):
    """A technology (framework, language, WAF, CDN, etc.)."""

    id: str
    name: str
    version: str | None = None
    category: Literal["framework", "language", "waf", "cdn", "db", "server", "os", "other"]


class Person(BaseModel):
    """A human identity (researcher, admin, employee, etc.)."""

    id: str
    name: str
    email: str | None = None
    role: str | None = None
    source: str
    confidence: float = 1.0
    discovered_at: datetime


class Finding(BaseModel):
    """A confirmed vulnerability. Only ``verify`` subagent can write these.

    The trust model hinges on this. An exploit subagent can write
    ``ExploitAttempt`` nodes, but a Finding (which goes into the
    customer report) can only be written by the ``verify`` subagent
    that confirms reproduction.
    """

    id: str
    title: str
    severity: Literal["critical", "high", "medium", "low", "info"]
    attack_class: str
    cwe: str | None = None
    cvss: float | None = None
    status: Literal["confirmed", "false_positive", "wont_fix"] = "confirmed"
    confidence: float = 1.0
    affected_asset_id: str
    found_by_endpoint_id: str | None = None
    evidence: str
    reproduction_count: int = 0
    created_at: datetime
    confirmed_at: datetime


class Credential(BaseModel):
    """A credential (leaked, found, etc.). SENSITIVE — never log without redaction."""

    id: str
    type: Literal["password", "api_key", "token", "session", "cookie"]
    value: str
    source: str
    valid: bool = True
    discovered_at: datetime


# ============================================================================
# Working types (created during an engagement)
# ============================================================================


class Hypothesis(BaseModel):
    """A testable vulnerability hypothesis with provenance.

    This is the core innovation. Every vulnerability attempt is backed
    by a typed Hypothesis. The schema forces the LLM to think like a
    senior pentester (claim, reasoning, test plan, expected evidence)
    instead of a junior "spray and pray" agent.
    """

    id: str
    target_id: str
    attack_class: str
    target_asset: str
    target_endpoint: str | None
    precondition: str
    reasoning: str
    test_plan: str
    expected_evidence: str
    confidence_prior: float
    status: Literal["pending", "testing", "verifying", "confirmed", "rejected", "exhausted"] = (
        "pending"
    )
    attempts: int = 0
    cost_spent: float = 0.0
    rejection_reason: str | None = None
    finding_id: str | None = None
    created_at: datetime
    updated_at: datetime
    generated_by: str = "analysis-hypothesis"


class ExploitAttempt(BaseModel):
    """A single execution of an exploit. Not a Finding until verified."""

    id: str
    hypothesis_id: str
    tool: str
    raw_output: str
    success: bool
    evidence: str
    created_at: datetime


class SigmaRule(BaseModel):
    """A Sigma detection rule (YAML format)."""

    id: str
    title: str
    yaml: str
    level: Literal["critical", "high", "medium", "low", "informational"]
    status: str = "experimental"


class IRPlaybook(BaseModel):
    """An incident-response playbook (Markdown)."""

    id: str
    title: str
    markdown: str


class DefensiveArtifact(BaseModel):
    """A paired defensive artifact (Sigma rule + IR playbook) for a Finding.

    Only ``blue-team`` subagent can write these. This is what makes
    Kryon's output "paired offensive and defensive".
    """

    id: str
    finding_id: str
    sigma_rule_id: str
    ir_playbook_id: str
    mitre_techniques: list[str] = Field(default_factory=list)
    generated_at: datetime


class ExploitChain(BaseModel):
    """A multi-step exploit chain (re-exploitation, privilege escalation)."""

    id: str
    name: str
    finding_ids: list[str]
    root_cause: str
    impact: str
    discovered_at: datetime


__all__ = [
    "Asset",
    "Credential",
    "DefensiveArtifact",
    "Endpoint",
    "ExploitAttempt",
    "ExploitChain",
    "Finding",
    "Hypothesis",
    "IRPlaybook",
    "Person",
    "SigmaRule",
    "Tech",
]
