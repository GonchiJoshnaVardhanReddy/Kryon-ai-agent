"""Tests for the common query helpers."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from kryon.core.paths import reset_kryon_home, set_kryon_home
from kryon.graph.models import (
    Asset,
    Endpoint,
    Hypothesis,
    Tech,
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
from kryon.graph.store import GraphStore, reset_graph_store


@pytest.fixture
def store(tmp_path: Path) -> GraphStore:
    set_kryon_home(tmp_path / "kryon")
    reset_graph_store()
    s = GraphStore("example")
    now = datetime.now(timezone.utc)
    # Seed: 1 root asset, 1 subdomain
    s.upsert_asset(
        Asset(
            id="asset:example.com",
            type="domain",
            value="example.com",
            source="x",
            discovered_at=now,
        ),
        subagent_name="recon-passive",
    )
    s.upsert_asset(
        Asset(
            id="asset:api.example.com",
            type="subdomain",
            value="api.example.com",
            parent_id="asset:example.com",
            source="x",
            discovered_at=now,
        ),
        subagent_name="recon-passive",
    )
    # HOSTS relationship
    s._conn.execute(  # noqa: SLF001 — direct SQL for test setup
        "MATCH (root:Asset {id: 'asset:example.com'}), "
        "(sub:Asset {id: 'asset:api.example.com'}) "
        "MERGE (root)-[:HOSTS]->(sub)"
    )
    # 1 endpoint with user input, on the subdomain
    s.upsert_endpoint(
        Endpoint(
            id="endpoint:1",
            url="https://api.example.com/",
            method="GET",
            parameters={"q": "str"},
            source="katana",
            discovered_at=now,
        ),
        subagent_name="recon-active",
    )
    s.link_endpoint_to_asset("endpoint:1", "asset:api.example.com")
    yield s
    s.close()
    reset_graph_store()
    reset_kryon_home()


def test_get_in_scope_assets(store: GraphStore) -> None:
    rows = get_in_scope_assets(store)
    assert len(rows) == 2


def test_get_endpoints_for_asset(store: GraphStore) -> None:
    rows = get_endpoints_for_asset(store, "asset:api.example.com")
    assert len(rows) == 1


def test_get_tech_for_asset_empty(store: GraphStore) -> None:
    rows = get_tech_for_asset(store, "asset:example.com")
    assert len(rows) == 0


def test_get_user_input_endpoints(store: GraphStore) -> None:
    rows = get_user_input_endpoints(store)
    assert len(rows) == 1
    # The endpoint has parameters, so should be included
    # 7-column RETURN e.* → endpoint id is column 0
    assert "endpoint:1" in [r[0] for r in rows]


def test_get_endpoints_using_db_empty(store: GraphStore) -> None:
    rows = get_endpoints_using_db(store)
    assert len(rows) == 0


def test_get_all_findings_empty(store: GraphStore) -> None:
    rows = get_all_findings(store)
    assert len(rows) == 0


def test_get_findings_without_defense_empty(store: GraphStore) -> None:
    rows = get_findings_without_defense(store)
    assert len(rows) == 0


def test_get_subdomains(store: GraphStore) -> None:
    rows = get_subdomains(store, "example.com")
    # Should find the api.example.com subdomain via HOSTS
    assert len(rows) == 1


def test_get_existing_hypotheses_empty(store: GraphStore) -> None:
    rows = get_existing_hypotheses(store)
    assert len(rows) == 0


def test_get_existing_hypotheses_by_status(store: GraphStore) -> None:
    now = datetime.now(timezone.utc)
    hyp = Hypothesis(
        id="hyp:1",
        target_id="t:1",
        attack_class="sqli",
        target_asset="asset:1",
        target_endpoint="endpoint:1",
        precondition="x",
        reasoning="x",
        test_plan="x",
        expected_evidence="x",
        confidence_prior=0.5,
        status="pending",
        created_at=now,
        updated_at=now,
    )
    store.upsert_hypothesis(hyp, subagent_name="analysis-hypothesis")
    rows = get_existing_hypotheses(store, status="pending")
    assert len(rows) == 1
    rows = get_existing_hypotheses(store, status="confirmed")
    assert len(rows) == 0


def test_count_findings_empty(store: GraphStore) -> None:
    assert count_findings(store) == 0


def test_count_hypotheses_empty(store: GraphStore) -> None:
    assert count_hypotheses(store) == 0


def test_count_hypotheses_with_status(store: GraphStore) -> None:
    now = datetime.now(timezone.utc)
    store.upsert_hypothesis(
        Hypothesis(
            id="hyp:1",
            target_id="t:1",
            attack_class="sqli",
            target_asset="a",
            target_endpoint=None,
            precondition="x",
            reasoning="x",
            test_plan="x",
            expected_evidence="x",
            confidence_prior=0.5,
            created_at=now,
            updated_at=now,
        ),
        subagent_name="analysis-hypothesis",
    )
    store.upsert_hypothesis(
        Hypothesis(
            id="hyp:2",
            target_id="t:1",
            attack_class="xss",
            target_asset="a",
            target_endpoint=None,
            precondition="x",
            reasoning="x",
            test_plan="x",
            expected_evidence="x",
            confidence_prior=0.5,
            status="rejected",
            created_at=now,
            updated_at=now,
        ),
        subagent_name="analysis-hypothesis",
    )
    assert count_hypotheses(store) == 2
    assert count_hypotheses(store, status="pending") == 1
    assert count_hypotheses(store, status="rejected") == 1


def test_get_endpoints_using_db_with_match(store: GraphStore) -> None:
    """Seed a Tech with category='db' linked to an asset with an endpoint."""
    now = datetime.now(timezone.utc)
    store.upsert_tech(
        Tech(id="tech:mysql", name="MySQL", version="5.7", category="db"),
        subagent_name="recon-passive",
    )
    store.link_tech_to_asset("tech:mysql", "asset:api.example.com")
    rows = get_endpoints_using_db(store)
    assert len(rows) == 1
