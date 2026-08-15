"""Tests for GraphStore — schema init, upsert, query, close."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from kryon.core.exceptions import GraphError
from kryon.core.paths import reset_kryon_home, set_kryon_home
from kryon.graph.models import (
    Asset,
    Endpoint,
    Finding,
    Tech,
)
from kryon.graph.store import GraphStore, reset_graph_store


@pytest.fixture
def store(tmp_path: Path) -> GraphStore:
    set_kryon_home(tmp_path / "kryon")
    reset_graph_store()
    s = GraphStore("example")
    yield s
    s.close()
    reset_graph_store()
    reset_kryon_home()


def test_db_path_isolation(tmp_path: Path) -> None:
    """Each target has its own graph file under ~/.kryon/targets/<slug>/graph/."""
    set_kryon_home(tmp_path / "kryon")
    reset_graph_store()
    s = GraphStore("example")
    assert s.db_path == tmp_path / "kryon" / "targets" / "example" / "graph" / "kryon_graph.db"
    s.close()
    reset_graph_store()
    reset_kryon_home()


def test_upsert_and_get_asset(store: GraphStore) -> None:
    asset = Asset(
        id="asset:example.com",
        type="domain",
        value="example.com",
        source="subfinder",
        discovered_at=datetime.now(timezone.utc),
    )
    store.upsert_asset(asset, subagent_name="recon-passive")
    loaded = store.get_asset("asset:example.com")
    assert loaded is not None
    assert loaded.id == "asset:example.com"
    assert loaded.value == "example.com"
    assert loaded.type == "domain"
    assert loaded.source == "subfinder"


def test_get_nonexistent_asset_returns_none(store: GraphStore) -> None:
    assert store.get_asset("nope") is None


def test_upsert_idempotent(store: GraphStore) -> None:
    """Upserting the same asset twice must NOT create a duplicate."""
    asset = Asset(
        id="asset:example.com",
        type="domain",
        value="example.com",
        source="subfinder",
        discovered_at=datetime.now(timezone.utc),
    )
    store.upsert_asset(asset, subagent_name="recon-passive")
    store.upsert_asset(asset, subagent_name="recon-passive")
    rows = store.query(
        "MATCH (a:Asset {id: 'asset:example.com'}) RETURN count(a)"
    )
    assert rows[0][0] == 1


def test_upsert_updates_existing(store: GraphStore) -> None:
    """Upserting the same id with a new field value updates in place."""
    now = datetime.now(timezone.utc)
    store.upsert_asset(
        Asset(
            id="asset:example.com",
            type="domain",
            value="example.com",
            source="subfinder",
            discovered_at=now,
        ),
        subagent_name="recon-passive",
    )
    store.upsert_asset(
        Asset(
            id="asset:example.com",
            type="domain",
            value="example.com",
            source="amass",  # changed
            discovered_at=now,
        ),
        subagent_name="recon-passive",
    )
    loaded = store.get_asset("asset:example.com")
    assert loaded is not None
    assert loaded.source == "amass"


def test_upsert_endpoint_and_link(store: GraphStore) -> None:
    asset = Asset(
        id="asset:example.com",
        type="domain",
        value="example.com",
        source="subfinder",
        discovered_at=datetime.now(timezone.utc),
    )
    store.upsert_asset(asset, subagent_name="recon-passive")
    endpoint = Endpoint(
        id="endpoint:1",
        url="https://example.com/",
        method="GET",
        parameters={},
        source="httpx",
        discovered_at=datetime.now(timezone.utc),
    )
    store.upsert_endpoint(endpoint, subagent_name="recon-active")
    store.link_endpoint_to_asset("endpoint:1", "asset:example.com")
    rows = store.query(
        "MATCH (a:Asset {id: 'asset:example.com'})-[:EXPOSES]->(e:Endpoint) RETURN e.id"
    )
    assert len(rows) == 1
    assert rows[0][0] == "endpoint:1"


def test_endpoint_roundtrip_preserves_parameters(store: GraphStore) -> None:
    """Endpoint.parameters (dict) is JSON-encoded in DB, decoded on read."""
    now = datetime.now(timezone.utc)
    ep = Endpoint(
        id="endpoint:1",
        url="https://example.com/api",
        method="POST",
        parameters={"user_id": "int", "name": "str"},
        source="katana",
        discovered_at=now,
    )
    store.upsert_endpoint(ep, subagent_name="recon-active")
    loaded = store.get_endpoint("endpoint:1")
    assert loaded is not None
    assert loaded.parameters == {"user_id": "int", "name": "str"}


def test_upsert_tech_and_link(store: GraphStore) -> None:
    asset = Asset(
        id="asset:example.com",
        type="domain",
        value="example.com",
        source="subfinder",
        discovered_at=datetime.now(timezone.utc),
    )
    store.upsert_asset(asset, subagent_name="recon-passive")
    tech = Tech(id="tech:cloudflare", name="Cloudflare", category="waf")
    store.upsert_tech(tech, subagent_name="recon-passive")
    store.link_tech_to_asset("tech:cloudflare", "asset:example.com")
    rows = store.query(
        "MATCH (a:Asset {id: 'asset:example.com'})-[:USES]->(t:Tech) RETURN t.id"
    )
    assert len(rows) == 1
    assert rows[0][0] == "tech:cloudflare"


def test_upsert_finding_as_verify(store: GraphStore) -> None:
    """verify subagent CAN write Finding."""
    f = Finding(
        id="finding:1",
        title="IDOR",
        severity="high",
        attack_class="idor",
        affected_asset_id="asset:1",
        evidence="test",
        created_at=datetime.now(timezone.utc),
        confirmed_at=datetime.now(timezone.utc),
    )
    store.upsert_finding(f, subagent_name="verify")
    loaded = store.get_finding("finding:1")
    assert loaded is not None
    assert loaded.title == "IDOR"
    assert loaded.severity == "high"


def test_get_finding_nonexistent(store: GraphStore) -> None:
    assert store.get_finding("nope") is None


def test_query_returns_rows(store: GraphStore) -> None:
    asset = Asset(
        id="asset:example.com",
        type="domain",
        value="example.com",
        in_scope=True,
        source="x",
        discovered_at=datetime.now(timezone.utc),
    )
    store.upsert_asset(asset, subagent_name="recon-passive")
    rows = store.query("MATCH (a:Asset {in_scope: true}) RETURN a.id")
    assert len(rows) == 1
    assert rows[0][0] == "asset:example.com"


def test_query_one_returns_first_row(store: GraphStore) -> None:
    asset = Asset(
        id="asset:example.com",
        type="domain",
        value="example.com",
        in_scope=True,
        source="x",
        discovered_at=datetime.now(timezone.utc),
    )
    store.upsert_asset(asset, subagent_name="recon-passive")
    row = store.query_one("MATCH (a:Asset {in_scope: true}) RETURN a.id")
    assert row is not None
    assert row[0] == "asset:example.com"


def test_query_one_returns_none_when_empty(store: GraphStore) -> None:
    row = store.query_one("MATCH (a:Asset {id: 'nonexistent'}) RETURN a")
    assert row is None


def test_get_graph_store_singleton(tmp_path: Path) -> None:
    set_kryon_home(tmp_path / "kryon")
    reset_graph_store()
    from kryon.graph.store import get_graph_store

    a = get_graph_store("example")
    b = get_graph_store("example")
    assert a is b
    c = get_graph_store("other")
    assert c is not a
    a.close()
    b.close()
    c.close()
    reset_graph_store()
    reset_kryon_home()


def test_schema_idempotent(store: GraphStore) -> None:
    """Calling _ensure_schema multiple times must not error."""
    store._ensure_schema()
    store._ensure_schema()
    store._ensure_schema()
    # Should be able to write and read after repeated init
    asset = Asset(
        id="asset:x",
        type="domain",
        value="x.com",
        source="x",
        discovered_at=datetime.now(timezone.utc),
    )
    store.upsert_asset(asset, subagent_name="recon-passive")
    assert store.get_asset("asset:x") is not None
