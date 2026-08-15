"""KùzuDB-backed knowledge graph for one target.

All write methods are SYNC (KùzuDB is sync). Subagents can wrap
calls in ``asyncio.to_thread`` if needed. The graph is per-target,
isolated at ``~/.kryon/targets/<slug>/graph/``.

Every ``upsert_*`` method takes ``subagent_name`` and checks
permissions BEFORE writing. Read methods have no permission check.

The schema (see ``SCHEMA_SQL``) creates 12 node tables and 14
relationship tables. The schema is created lazily on first write,
and is idempotent (``CREATE TABLE IF NOT EXISTS``).
"""

from __future__ import annotations

import contextlib
import json
import shutil
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import Any

import kuzu

from kryon.core.paths import kryon_target_graph_dir
from kryon.graph.models import (
    Asset,
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
from kryon.graph.permissions import check_write_permission
from kryon.targets.models import Target

# ============================================================================
# Schema
# ============================================================================


SCHEMA_SQL = """
CREATE NODE TABLE IF NOT EXISTS Asset (
    id STRING PRIMARY KEY,
    type STRING,
    value STRING,
    parent_id STRING,
    in_scope BOOLEAN,
    source STRING,
    discovered_at TIMESTAMP
);

CREATE NODE TABLE IF NOT EXISTS Endpoint (
    id STRING PRIMARY KEY,
    url STRING,
    method STRING,
    parameters STRING,
    auth_required BOOLEAN,
    source STRING,
    discovered_at TIMESTAMP
);

CREATE NODE TABLE IF NOT EXISTS Tech (
    id STRING PRIMARY KEY,
    name STRING,
    version STRING,
    category STRING
);

CREATE NODE TABLE IF NOT EXISTS Person (
    id STRING PRIMARY KEY,
    name STRING,
    email STRING,
    role STRING,
    source STRING,
    confidence DOUBLE,
    discovered_at TIMESTAMP
);

CREATE NODE TABLE IF NOT EXISTS Finding (
    id STRING PRIMARY KEY,
    title STRING,
    severity STRING,
    attack_class STRING,
    cwe STRING,
    cvss DOUBLE,
    status STRING,
    confidence DOUBLE,
    affected_asset_id STRING,
    found_by_endpoint_id STRING,
    evidence STRING,
    reproduction_count INT,
    created_at TIMESTAMP,
    confirmed_at TIMESTAMP
);

CREATE NODE TABLE IF NOT EXISTS Credential (
    id STRING PRIMARY KEY,
    type STRING,
    value STRING,
    source STRING,
    valid BOOLEAN,
    discovered_at TIMESTAMP
);

CREATE NODE TABLE IF NOT EXISTS Hypothesis (
    id STRING PRIMARY KEY,
    target_id STRING,
    attack_class STRING,
    target_asset STRING,
    target_endpoint STRING,
    precondition STRING,
    reasoning STRING,
    test_plan STRING,
    expected_evidence STRING,
    confidence_prior DOUBLE,
    status STRING,
    attempts INT,
    cost_spent DOUBLE,
    rejection_reason STRING,
    finding_id STRING,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    generated_by STRING
);

CREATE NODE TABLE IF NOT EXISTS ExploitAttempt (
    id STRING PRIMARY KEY,
    hypothesis_id STRING,
    tool STRING,
    raw_output STRING,
    success BOOLEAN,
    evidence STRING,
    created_at TIMESTAMP
);

CREATE NODE TABLE IF NOT EXISTS SigmaRule (
    id STRING PRIMARY KEY,
    title STRING,
    yaml STRING,
    level STRING,
    status STRING
);

CREATE NODE TABLE IF NOT EXISTS IRPlaybook (
    id STRING PRIMARY KEY,
    title STRING,
    markdown STRING
);

CREATE NODE TABLE IF NOT EXISTS DefensiveArtifact (
    id STRING PRIMARY KEY,
    finding_id STRING,
    sigma_rule_id STRING,
    ir_playbook_id STRING,
    mitre_techniques STRING,
    generated_at TIMESTAMP
);

CREATE NODE TABLE IF NOT EXISTS ExploitChain (
    id STRING PRIMARY KEY,
    name STRING,
    finding_ids STRING,
    root_cause STRING,
    impact STRING,
    discovered_at TIMESTAMP
);

CREATE REL TABLE IF NOT EXISTS OWNS (FROM Person TO Asset);
CREATE REL TABLE IF NOT EXISTS HAS_CREDENTIAL (FROM Person TO Credential);
CREATE REL TABLE IF NOT EXISTS HOSTS (FROM Asset TO Asset);
CREATE REL TABLE IF NOT EXISTS LINKED_TO (FROM Asset TO Asset);
CREATE REL TABLE IF NOT EXISTS EXPOSES (FROM Asset TO Endpoint);
CREATE REL TABLE IF NOT EXISTS USES (FROM Asset TO Tech);
CREATE REL TABLE IF NOT EXISTS PROTECTS (FROM Tech TO Asset);
CREATE REL TABLE IF NOT EXISTS FOUND_BY (FROM Finding TO Endpoint);
CREATE REL TABLE IF NOT EXISTS AFFECTS (FROM Finding TO Asset);
CREATE REL TABLE IF NOT EXISTS TARGETS_ASSET (FROM Hypothesis TO Asset);
CREATE REL TABLE IF NOT EXISTS TESTS (FROM ExploitAttempt TO Hypothesis);
CREATE REL TABLE IF NOT EXISTS PROMOTED_FROM (FROM Finding TO ExploitAttempt);
CREATE REL TABLE IF NOT EXISTS HAS_DEFENSE (FROM Finding TO DefensiveArtifact);
CREATE REL TABLE IF NOT EXISTS CHAIN (FROM ExploitChain TO Finding);
"""


# ============================================================================
# Helpers
# ============================================================================


def _iter_statements(schema: str) -> Iterator[str]:
    """Yield non-empty, stripped statements from a multi-statement script."""
    for raw in schema.split(";"):
        stmt = raw.strip()
        if stmt:
            yield stmt


def _drain(result: kuzu.QueryResult | list[kuzu.QueryResult]) -> list[list[Any]]:
    """Consume a Kùzu QueryResult (or list of them) into rows of cells.

    Kùzu's ``Connection.execute`` returns either a single ``QueryResult``
    or, for batch queries, a list of them. We accept both.
    """
    if isinstance(result, list):
        # Batch: concatenate the rows from all results
        rows: list[list[Any]] = []
        for r in result:
            while r.has_next():
                rows.append(list(r.get_next()))
            with contextlib.suppress(Exception):
                r.close()
        return rows
    rows = []
    while result.has_next():
        rows.append(list(result.get_next()))
    with contextlib.suppress(Exception):
        result.close()
    return rows


# ============================================================================
# GraphStore
# ============================================================================


class GraphStore:
    """KùzuDB-backed knowledge graph for one target.

    All write methods are sync. Permission check happens BEFORE the
    write — no bypass path. Read methods (get_*, query*) have no
    permission check.
    """

    def __init__(self, target: Target | str) -> None:
        slug = target.slug if isinstance(target, Target) else target
        self._target_slug = slug
        # kryon_target_graph_dir returns a directory path; KùzuDB wants a
        # non-existent FILE path that it then creates. We use a stable
        # filename inside the graph dir so multiple processes don't collide.
        self._graph_dir: Path = kryon_target_graph_dir(slug)
        self._graph_dir.mkdir(parents=True, exist_ok=True)
        self._db_path: Path = self._graph_dir / "kryon_graph.db"
        self._db = kuzu.Database(str(self._db_path))
        self._conn = kuzu.Connection(self._db)
        self._schema_initialized = False

    @property
    def target_slug(self) -> str:
        return self._target_slug

    @property
    def db_path(self) -> Path:
        return self._db_path

    def _ensure_schema(self) -> None:
        if self._schema_initialized:
            return
        for stmt in _iter_statements(SCHEMA_SQL):
            with contextlib.suppress(Exception):
                # IF NOT EXISTS makes this idempotent, but be defensive
                self._conn.execute(stmt)
        self._schema_initialized = True

    def close(self) -> None:
        """Release DB resources. Kùzu doesn't have an explicit close; drop refs."""
        self._conn = None  # type: ignore[assignment]
        self._db = None  # type: ignore[assignment]

    # ============================================================================
    # Asset
    # ============================================================================

    def upsert_asset(self, asset: Asset, *, subagent_name: str) -> None:
        check_write_permission(subagent_name, "Asset")
        self._ensure_schema()
        self._conn.execute(
            """
            MERGE (a:Asset {id: $id})
            SET a.type = $type,
                a.value = $value,
                a.parent_id = $parent_id,
                a.in_scope = $in_scope,
                a.source = $source,
                a.discovered_at = $discovered_at
            """,
            {
                "id": asset.id,
                "type": asset.type,
                "value": asset.value,
                "parent_id": asset.parent_id,
                "in_scope": asset.in_scope,
                "source": asset.source,
                "discovered_at": asset.discovered_at,
            },
        )

    def get_asset(self, asset_id: str) -> Asset | None:
        self._ensure_schema()
        rows = _drain(
            self._conn.execute(
                "MATCH (a:Asset {id: $id}) RETURN a.id, a.type, a.value, "
                "a.parent_id, a.in_scope, a.source, a.discovered_at",
                {"id": asset_id},
            )
        )
        if not rows:
            return None
        r = rows[0]
        return Asset(
            id=r[0],
            type=r[1],
            value=r[2],
            parent_id=r[3],
            in_scope=r[4],
            source=r[5],
            discovered_at=r[6],
        )

    # ============================================================================
    # Endpoint
    # ============================================================================

    def upsert_endpoint(self, endpoint: Endpoint, *, subagent_name: str) -> None:
        check_write_permission(subagent_name, "Endpoint")
        self._ensure_schema()
        self._conn.execute(
            """
            MERGE (e:Endpoint {id: $id})
            SET e.url = $url,
                e.method = $method,
                e.parameters = $parameters,
                e.auth_required = $auth_required,
                e.source = $source,
                e.discovered_at = $discovered_at
            """,
            {
                "id": endpoint.id,
                "url": endpoint.url,
                "method": endpoint.method,
                "parameters": json.dumps(endpoint.parameters),
                "auth_required": endpoint.auth_required,
                "source": endpoint.source,
                "discovered_at": endpoint.discovered_at,
            },
        )

    def get_endpoint(self, endpoint_id: str) -> Endpoint | None:
        self._ensure_schema()
        rows = _drain(
            self._conn.execute(
                "MATCH (e:Endpoint {id: $id}) RETURN e.id, e.url, e.method, "
                "e.parameters, e.auth_required, e.source, e.discovered_at",
                {"id": endpoint_id},
            )
        )
        if not rows:
            return None
        r = rows[0]
        params_raw = r[3]
        params: dict[str, Any] = {}
        if params_raw:
            with contextlib.suppress(json.JSONDecodeError, TypeError):
                params = json.loads(params_raw)
        return Endpoint(
            id=r[0],
            url=r[1],
            method=r[2],
            parameters=params,
            auth_required=r[4],
            source=r[5],
            discovered_at=r[6],
        )

    def link_endpoint_to_asset(self, endpoint_id: str, asset_id: str) -> None:
        self._ensure_schema()
        self._conn.execute(
            """
            MATCH (a:Asset {id: $asset_id}), (e:Endpoint {id: $endpoint_id})
            MERGE (a)-[r:EXPOSES]->(e)
            """,
            {"asset_id": asset_id, "endpoint_id": endpoint_id},
        )

    # ============================================================================
    # Tech
    # ============================================================================

    def upsert_tech(self, tech: Tech, *, subagent_name: str) -> None:
        check_write_permission(subagent_name, "Tech")
        self._ensure_schema()
        self._conn.execute(
            """
            MERGE (t:Tech {id: $id})
            SET t.name = $name,
                t.version = $version,
                t.category = $category
            """,
            {
                "id": tech.id,
                "name": tech.name,
                "version": tech.version,
                "category": tech.category,
            },
        )

    def get_tech(self, tech_id: str) -> Tech | None:
        self._ensure_schema()
        rows = _drain(
            self._conn.execute(
                "MATCH (t:Tech {id: $id}) RETURN t.id, t.name, t.version, t.category",
                {"id": tech_id},
            )
        )
        if not rows:
            return None
        r = rows[0]
        return Tech(id=r[0], name=r[1], version=r[2], category=r[3])

    def link_tech_to_asset(self, tech_id: str, asset_id: str) -> None:
        self._ensure_schema()
        self._conn.execute(
            """
            MATCH (a:Asset {id: $asset_id}), (t:Tech {id: $tech_id})
            MERGE (a)-[r:USES]->(t)
            """,
            {"asset_id": asset_id, "tech_id": tech_id},
        )

    # ============================================================================
    # Person
    # ============================================================================

    def upsert_person(self, person: Person, *, subagent_name: str) -> None:
        check_write_permission(subagent_name, "Person")
        self._ensure_schema()
        self._conn.execute(
            """
            MERGE (p:Person {id: $id})
            SET p.name = $name,
                p.email = $email,
                p.role = $role,
                p.source = $source,
                p.confidence = $confidence,
                p.discovered_at = $discovered_at
            """,
            {
                "id": person.id,
                "name": person.name,
                "email": person.email,
                "role": person.role,
                "source": person.source,
                "confidence": person.confidence,
                "discovered_at": person.discovered_at,
            },
        )

    # ============================================================================
    # Credential
    # ============================================================================

    def upsert_credential(self, cred: Any, *, subagent_name: str) -> None:
        check_write_permission(subagent_name, "Credential")
        self._ensure_schema()
        self._conn.execute(
            """
            MERGE (c:Credential {id: $id})
            SET c.type = $type,
                c.value = $value,
                c.source = $source,
                c.valid = $valid,
                c.discovered_at = $discovered_at
            """,
            {
                "id": cred.id,
                "type": cred.type,
                "value": cred.value,
                "source": cred.source,
                "valid": cred.valid,
                "discovered_at": cred.discovered_at,
            },
        )

    # ============================================================================
    # Hypothesis
    # ============================================================================

    def upsert_hypothesis(self, hyp: Hypothesis, *, subagent_name: str) -> None:
        check_write_permission(subagent_name, "Hypothesis")
        self._ensure_schema()
        self._conn.execute(
            """
            MERGE (h:Hypothesis {id: $id})
            SET h.target_id = $target_id,
                h.attack_class = $attack_class,
                h.target_asset = $target_asset,
                h.target_endpoint = $target_endpoint,
                h.precondition = $precondition,
                h.reasoning = $reasoning,
                h.test_plan = $test_plan,
                h.expected_evidence = $expected_evidence,
                h.confidence_prior = $confidence_prior,
                h.status = $status,
                h.attempts = $attempts,
                h.cost_spent = $cost_spent,
                h.rejection_reason = $rejection_reason,
                h.finding_id = $finding_id,
                h.created_at = $created_at,
                h.updated_at = $updated_at,
                h.generated_by = $generated_by
            """,
            {
                "id": hyp.id,
                "target_id": hyp.target_id,
                "attack_class": hyp.attack_class,
                "target_asset": hyp.target_asset,
                "target_endpoint": hyp.target_endpoint,
                "precondition": hyp.precondition,
                "reasoning": hyp.reasoning,
                "test_plan": hyp.test_plan,
                "expected_evidence": hyp.expected_evidence,
                "confidence_prior": hyp.confidence_prior,
                "status": hyp.status,
                "attempts": hyp.attempts,
                "cost_spent": hyp.cost_spent,
                "rejection_reason": hyp.rejection_reason,
                "finding_id": hyp.finding_id,
                "created_at": hyp.created_at,
                "updated_at": hyp.updated_at,
                "generated_by": hyp.generated_by,
            },
        )

    def get_hypothesis(self, hyp_id: str) -> Hypothesis | None:
        self._ensure_schema()
        rows = _drain(
            self._conn.execute(
                "MATCH (h:Hypothesis {id: $id}) RETURN h.*",
                {"id": hyp_id},
            )
        )
        if not rows:
            return None
        r = rows[0]
        return self._row_to_hypothesis(r)

    @staticmethod
    def _row_to_hypothesis(r: list[Any]) -> Hypothesis:
        """Build a Hypothesis from a RETURN h.* row (15 columns)."""
        return Hypothesis(
            id=r[0],
            target_id=r[1],
            attack_class=r[2],
            target_asset=r[3],
            target_endpoint=r[4],
            precondition=r[5],
            reasoning=r[6],
            test_plan=r[7],
            expected_evidence=r[8],
            confidence_prior=r[9],
            status=r[10],
            attempts=r[11],
            cost_spent=r[12],
            rejection_reason=r[13],
            finding_id=r[14],
            created_at=r[15],
            updated_at=r[16],
            generated_by=r[17],
        )

    def update_hypothesis_status(
        self,
        hyp_id: str,
        status: str,
        *,
        subagent_name: str,
        rejection_reason: str | None = None,
        finding_id: str | None = None,
    ) -> None:
        check_write_permission(subagent_name, "Hypothesis")
        self._ensure_schema()
        self._conn.execute(
            """
            MATCH (h:Hypothesis {id: $id})
            SET h.status = $status,
                h.rejection_reason = $rejection_reason,
                h.finding_id = $finding_id,
                h.updated_at = $updated_at
            """,
            {
                "id": hyp_id,
                "status": status,
                "rejection_reason": rejection_reason,
                "finding_id": finding_id,
                "updated_at": datetime.utcnow(),
            },
        )

    # ============================================================================
    # ExploitAttempt
    # ============================================================================

    def upsert_exploit_attempt(self, attempt: ExploitAttempt, *, subagent_name: str) -> None:
        check_write_permission(subagent_name, "ExploitAttempt")
        self._ensure_schema()
        self._conn.execute(
            """
            MERGE (e:ExploitAttempt {id: $id})
            SET e.hypothesis_id = $hypothesis_id,
                e.tool = $tool,
                e.raw_output = $raw_output,
                e.success = $success,
                e.evidence = $evidence,
                e.created_at = $created_at
            """,
            {
                "id": attempt.id,
                "hypothesis_id": attempt.hypothesis_id,
                "tool": attempt.tool,
                # Truncate noisy tool output so the graph doesn't bloat
                "raw_output": attempt.raw_output[:5000],
                "success": attempt.success,
                "evidence": attempt.evidence,
                "created_at": attempt.created_at,
            },
        )

    def link_exploit_to_hypothesis(self, attempt_id: str, hypothesis_id: str) -> None:
        self._ensure_schema()
        self._conn.execute(
            """
            MATCH (a:ExploitAttempt {id: $attempt_id}), (h:Hypothesis {id: $hypothesis_id})
            MERGE (a)-[r:TESTS]->(h)
            """,
            {"attempt_id": attempt_id, "hypothesis_id": hypothesis_id},
        )

    # ============================================================================
    # Finding (only verify can write)
    # ============================================================================

    def upsert_finding(self, finding: Finding, *, subagent_name: str) -> None:
        check_write_permission(subagent_name, "Finding")
        self._ensure_schema()
        self._conn.execute(
            """
            MERGE (f:Finding {id: $id})
            SET f.title = $title,
                f.severity = $severity,
                f.attack_class = $attack_class,
                f.cwe = $cwe,
                f.cvss = $cvss,
                f.status = $status,
                f.confidence = $confidence,
                f.affected_asset_id = $affected_asset_id,
                f.found_by_endpoint_id = $found_by_endpoint_id,
                f.evidence = $evidence,
                f.reproduction_count = $reproduction_count,
                f.created_at = $created_at,
                f.confirmed_at = $confirmed_at
            """,
            {
                "id": finding.id,
                "title": finding.title,
                "severity": finding.severity,
                "attack_class": finding.attack_class,
                "cwe": finding.cwe,
                "cvss": finding.cvss,
                "status": finding.status,
                "confidence": finding.confidence,
                "affected_asset_id": finding.affected_asset_id,
                "found_by_endpoint_id": finding.found_by_endpoint_id,
                "evidence": finding.evidence,
                "reproduction_count": finding.reproduction_count,
                "created_at": finding.created_at,
                "confirmed_at": finding.confirmed_at,
            },
        )

    def get_finding(self, finding_id: str) -> Finding | None:
        self._ensure_schema()
        rows = _drain(
            self._conn.execute(
                "MATCH (f:Finding {id: $id}) RETURN f.id, f.title, f.severity, "
                "f.attack_class, f.cwe, f.cvss, f.status, f.confidence, "
                "f.affected_asset_id, f.found_by_endpoint_id, f.evidence, "
                "f.reproduction_count, f.created_at, f.confirmed_at",
                {"id": finding_id},
            )
        )
        if not rows:
            return None
        r = rows[0]
        return Finding(
            id=r[0],
            title=r[1],
            severity=r[2],
            attack_class=r[3],
            cwe=r[4],
            cvss=r[5],
            status=r[6],
            confidence=r[7],
            affected_asset_id=r[8],
            found_by_endpoint_id=r[9],
            evidence=r[10],
            reproduction_count=r[11],
            created_at=r[12],
            confirmed_at=r[13],
        )

    # ============================================================================
    # Defensive artifacts (only blue-team can write)
    # ============================================================================

    def upsert_sigma_rule(self, rule: SigmaRule, *, subagent_name: str) -> None:
        check_write_permission(subagent_name, "SigmaRule")
        self._ensure_schema()
        self._conn.execute(
            """
            MERGE (r:SigmaRule {id: $id})
            SET r.title = $title,
                r.yaml = $yaml,
                r.level = $level,
                r.status = $status
            """,
            {
                "id": rule.id,
                "title": rule.title,
                "yaml": rule.yaml,
                "level": rule.level,
                "status": rule.status,
            },
        )

    def upsert_ir_playbook(self, playbook: IRPlaybook, *, subagent_name: str) -> None:
        check_write_permission(subagent_name, "IRPlaybook")
        self._ensure_schema()
        self._conn.execute(
            """
            MERGE (p:IRPlaybook {id: $id})
            SET p.title = $title,
                p.markdown = $markdown
            """,
            {
                "id": playbook.id,
                "title": playbook.title,
                "markdown": playbook.markdown,
            },
        )

    def upsert_defensive_artifact(self, artifact: DefensiveArtifact, *, subagent_name: str) -> None:
        check_write_permission(subagent_name, "DefensiveArtifact")
        self._ensure_schema()
        self._conn.execute(
            """
            MERGE (d:DefensiveArtifact {id: $id})
            SET d.finding_id = $finding_id,
                d.sigma_rule_id = $sigma_rule_id,
                d.ir_playbook_id = $ir_playbook_id,
                d.mitre_techniques = $mitre_techniques,
                d.generated_at = $generated_at
            """,
            {
                "id": artifact.id,
                "finding_id": artifact.finding_id,
                "sigma_rule_id": artifact.sigma_rule_id,
                "ir_playbook_id": artifact.ir_playbook_id,
                "mitre_techniques": json.dumps(artifact.mitre_techniques),
                "generated_at": artifact.generated_at,
            },
        )

    # ============================================================================
    # ExploitChain (only post-exploit can write)
    # ============================================================================

    def upsert_exploit_chain(self, chain: ExploitChain, *, subagent_name: str) -> None:
        check_write_permission(subagent_name, "ExploitChain")
        self._ensure_schema()
        self._conn.execute(
            """
            MERGE (c:ExploitChain {id: $id})
            SET c.name = $name,
                c.finding_ids = $finding_ids,
                c.root_cause = $root_cause,
                c.impact = $impact,
                c.discovered_at = $discovered_at
            """,
            {
                "id": chain.id,
                "name": chain.name,
                "finding_ids": json.dumps(chain.finding_ids),
                "root_cause": chain.root_cause,
                "impact": chain.impact,
                "discovered_at": chain.discovered_at,
            },
        )

    # ============================================================================
    # Generic query interface
    # ============================================================================

    def query(self, cypher: str, params: dict[str, Any] | None = None) -> list[list[Any]]:
        """Run a Cypher query. Returns rows as a list of lists.

        Use the typed helpers (get_in_scope_assets, etc.) for common
        queries. Use this for custom queries.
        """
        self._ensure_schema()
        result = self._conn.execute(cypher, params or {})
        return _drain(result)

    def query_one(self, cypher: str, params: dict[str, Any] | None = None) -> list[Any] | None:
        """Run a Cypher query and return the first row, or None."""
        rows = self.query(cypher, params)
        return rows[0] if rows else None


# ============================================================================
# Singleton registry (one GraphStore per target)
# ============================================================================


_stores: dict[str, GraphStore] = {}


def get_graph_store(target: Target | str) -> GraphStore:
    """Get the ``GraphStore`` instance for a specific target.

    Same target always returns the same instance (within a process).
    Use ``reset_graph_store`` to clear the registry in tests.
    """
    slug = target.slug if isinstance(target, Target) else target
    cached = _stores.get(slug)
    if cached is not None:
        return cached
    fresh = GraphStore(slug)
    _stores[slug] = fresh
    return fresh


def reset_graph_store(slug: str | None = None) -> None:
    """Reset the GraphStore registry.

    If ``slug`` is given, only that target's store is removed.
    If ``None``, the entire registry is cleared. Closes any open
    stores first.
    """
    global _stores
    if slug is None:
        for store in list(_stores.values()):
            store.close()
        _stores = {}
    elif slug in _stores:
        _stores[slug].close()
        del _stores[slug]


def remove_graph_dir(slug: str) -> None:
    """Delete the on-disk graph directory for a target.

    Used by ``TargetManager.delete()`` to ensure a full target delete
    also wipes the per-target KùzuDB files. Best-effort; ignored if
    the directory doesn't exist.
    """
    path = kryon_target_graph_dir(slug)
    if path.exists():
        shutil.rmtree(path, ignore_errors=True)


__all__ = [
    "SCHEMA_SQL",
    "GraphStore",
    "get_graph_store",
    "remove_graph_dir",
    "reset_graph_store",
]
