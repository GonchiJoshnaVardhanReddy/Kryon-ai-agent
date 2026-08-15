"""Graph write permissions — enforced at the GraphStore layer.

The knowledge graph is a safety mechanism, not just a data structure.
The permission matrix ensures that:

- Only ``verify`` can promote an exploit to a ``Finding``
- Only ``blue-team`` can generate defensive artifacts
- Subagents cannot modify nodes they didn't create

This is Layer 1 of the trust model: even if a subagent is buggy or
malicious, it cannot corrupt the graph beyond its allowed write set.

Every ``GraphStore.upsert_*`` method calls ``check_write_permission``
BEFORE the write. There is no bypass. A buggy or compromised
``exploit`` subagent literally cannot write a ``Finding`` — the
permission check is a hard error.
"""

from __future__ import annotations

from kryon.core.exceptions import GraphError

# Subagent → allowed write node types
GRAPH_WRITE_PERMISSIONS: dict[str, set[str]] = {
    "recon-passive": {"Asset", "Tech", "Person", "Credential"},
    "recon-active": {"Asset", "Endpoint", "Tech", "Person", "Credential"},
    "analysis-hypothesis": {"Hypothesis"},
    "exploit": {"ExploitAttempt"},
    "post-exploit": {"ExploitChain"},
    "verify": {
        "Finding",
        "Hypothesis",  # verify transitions hypothesis to confirmed/rejected
    },
    "blue-team": {"DefensiveArtifact", "SigmaRule", "IRPlaybook"},
    "report": set(),  # no graph writes (reports go to file system)
}


def check_write_permission(subagent_name: str, node_type: str) -> None:
    """Raise ``GraphError`` if subagent cannot write this node type.

    Called by ``GraphStore.upsert_*`` methods BEFORE writing.
    Unknown subagents are denied by default.
    """
    allowed = GRAPH_WRITE_PERMISSIONS.get(subagent_name, set())
    if node_type not in allowed:
        raise GraphError(
            f"Subagent {subagent_name!r} cannot write {node_type!r} nodes",
            details={
                "subagent": subagent_name,
                "node_type": node_type,
                "allowed_node_types": sorted(allowed),
            },
        )


__all__ = [
    "GRAPH_WRITE_PERMISSIONS",
    "check_write_permission",
]
