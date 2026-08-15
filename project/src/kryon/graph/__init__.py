"""Kryon knowledge graph — KùzuDB-backed per-target graph store.

The graph is the substrate of structured autonomy. Subagents read
typed entities (Asset, Endpoint, Tech, Person, Finding, ...) and
write new ones — but only within their allowed write set, enforced
by ``GRAPH_WRITE_PERMISSIONS`` and ``check_write_permission()``.

Quickstart::

    from kryon.graph import GraphStore, Asset

    store = GraphStore("example")  # or GraphStore(target_obj)
    asset = Asset(
        id="asset:example.com",
        type="domain",
        value="example.com",
        source="subfinder",
        discovered_at=datetime.now(UTC),
    )
    store.upsert_asset(asset, subagent_name="recon-passive")
    rows = store.query("MATCH (a:Asset {in_scope: true}) RETURN a.*")
    store.close()
"""

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
from kryon.graph.permissions import (
    GRAPH_WRITE_PERMISSIONS,
    check_write_permission,
)
from kryon.graph.queries import (
    count_findings,
    count_hypotheses,
    get_all_findings,
    get_endpoints_for_asset,
    get_endpoints_using_db,
    get_existing_hypotheses,
    get_findings_without_defense,
    get_in_scope_assets,
    get_subdomains,
    get_tech_for_asset,
    get_user_input_endpoints,
)
from kryon.graph.store import (
    SCHEMA_SQL,
    GraphStore,
    get_graph_store,
    remove_graph_dir,
    reset_graph_store,
)

__all__ = [  # noqa: RUF022 — sorted by category not alphabetical
    # Models
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
    # Store
    "GraphStore",
    "SCHEMA_SQL",
    "get_graph_store",
    "remove_graph_dir",
    "reset_graph_store",
    # Permissions
    "GRAPH_WRITE_PERMISSIONS",
    "check_write_permission",
    # Queries
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
