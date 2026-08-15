"""Common queries the agent uses against the knowledge graph.

These are convenience wrappers around ``GraphStore.query()`` for the
patterns the subagents and loop use over and over. New helpers here
should be the result of seeing the same Cypher pattern appear 3+
times in different subagents.
"""

from __future__ import annotations

from typing import Any

from kryon.graph.store import GraphStore


def get_in_scope_assets(store: GraphStore) -> list[list[Any]]:
    """Get all in-scope assets (domains, subdomains, IPs)."""
    return store.query("MATCH (a:Asset {in_scope: true}) RETURN a.*")


def get_endpoints_for_asset(store: GraphStore, asset_id: str) -> list[list[Any]]:
    """Get all endpoints exposed by an asset (via EXPOSES edge)."""
    return store.query(
        "MATCH (a:Asset {id: $id})-[:EXPOSES]->(e:Endpoint) RETURN e.*",
        {"id": asset_id},
    )


def get_tech_for_asset(store: GraphStore, asset_id: str) -> list[list[Any]]:
    """Get all tech used by an asset (via USES edge)."""
    return store.query(
        "MATCH (a:Asset {id: $id})-[:USES]->(t:Tech) RETURN t.*",
        {"id": asset_id},
    )


def get_user_input_endpoints(store: GraphStore) -> list[list[Any]]:
    """Get endpoints that take user input (parameters dict not empty)."""
    return store.query("MATCH (e:Endpoint) WHERE e.parameters <> '{}' RETURN e.*")


def get_endpoints_using_db(store: GraphStore) -> list[list[Any]]:
    """Get endpoints whose assets use a database tech (likely SQLi candidates)."""
    return store.query(
        """
        MATCH (a:Asset)-[:USES]->(t:Tech {category: 'db'})
        MATCH (a)-[:EXPOSES]->(e:Endpoint)
        RETURN DISTINCT e.*
        """
    )


def get_all_findings(store: GraphStore) -> list[list[Any]]:
    """Get all findings."""
    return store.query("MATCH (f:Finding) RETURN f.*")


def get_findings_without_defense(store: GraphStore) -> list[list[Any]]:
    """Get confirmed findings that have no defensive artifact yet."""
    return store.query(
        """
        MATCH (f:Finding {status: 'confirmed'})
        WHERE NOT (f)-[:HAS_DEFENSE]->(:DefensiveArtifact)
        RETURN f.*
        """
    )


def get_subdomains(store: GraphStore, root_domain: str) -> list[list[Any]]:
    """Get all subdomains of a root domain via HOSTS edges (1-3 hops)."""
    return store.query(
        """
        MATCH (root:Asset {value: $root})-[:HOSTS*1..3]->(sub:Asset)
        RETURN sub.*
        """,
        {"root": root_domain},
    )


def get_existing_hypotheses(store: GraphStore, status: str | None = None) -> list[list[Any]]:
    """Get existing hypotheses, optionally filtered by status."""
    if status is not None:
        return store.query(
            "MATCH (h:Hypothesis {status: $status}) RETURN h.*",
            {"status": status},
        )
    return store.query("MATCH (h:Hypothesis) RETURN h.*")


def count_findings(store: GraphStore) -> int:
    """Count all findings."""
    row = store.query_one("MATCH (f:Finding) RETURN count(f)")
    return int(row[0]) if row else 0


def count_hypotheses(store: GraphStore, status: str | None = None) -> int:
    """Count hypotheses, optionally filtered by status."""
    if status is not None:
        row = store.query_one(
            "MATCH (h:Hypothesis {status: $status}) RETURN count(h)",
            {"status": status},
        )
    else:
        row = store.query_one("MATCH (h:Hypothesis) RETURN count(h)")
    return int(row[0]) if row else 0


__all__ = [
    "count_findings",
    "count_hypotheses",
    "get_all_findings",
    "get_endpoints_for_asset",
    "get_endpoints_using_db",
    "get_existing_hypotheses",
    "get_findings_without_defense",
    "get_in_scope_assets",
    "get_subdomains",
    "get_tech_for_asset",
    "get_user_input_endpoints",
]
