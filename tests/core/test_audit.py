"""Tests for the append-only audit log (Layer 8 of the security model).

These tests verify:
1. Basic log + query works
2. UPDATE is blocked at the DB level (not just in Python) — the
   most important security property
3. DELETE is blocked at the DB level
4. Schema is idempotent
5. Audit log persists across instantiations
6. Query filters work (subagent, action, since_id)
7. Secret redaction in details
8. Invalid target_id is rejected
"""
from __future__ import annotations

from pathlib import Path

import aiosqlite
import pytest

from kryon.core.audit import (
    AuditLog,
    get_audit_log,
    redact_secrets,
    reset_audit_log,
)
from kryon.core.exceptions import AuditError
from kryon.core.paths import reset_kryon_home, set_kryon_home


@pytest.mark.asyncio
async def test_log_returns_row_id(tmp_path: Path) -> None:
    set_kryon_home(tmp_path / "kryon")
    reset_audit_log()
    audit = AuditLog("test")
    row_id = await audit.log(action="subagent_start", subagent="recon-passive")
    assert row_id > 0
    reset_kryon_home()


@pytest.mark.asyncio
async def test_log_persists_basic(tmp_path: Path) -> None:
    set_kryon_home(tmp_path / "kryon")
    reset_audit_log()
    audit = AuditLog("test")
    await audit.log(
        action="state_transition",
        subagent="loop",
        state_from="INIT",
        state_to="RECON_PASSIVE",
        reasoning="authorization confirmed",
    )
    entries = await audit.query()
    assert len(entries) == 1
    e = entries[0]
    assert e["action"] == "state_transition"
    assert e["subagent"] == "loop"
    assert e["state_from"] == "INIT"
    assert e["state_to"] == "RECON_PASSIVE"
    assert e["reasoning"] == "authorization confirmed"
    assert e["target_id"] == "test"
    reset_kryon_home()


@pytest.mark.asyncio
async def test_persists_across_instantiations(tmp_path: Path) -> None:
    """The audit log must survive process restarts."""
    set_kryon_home(tmp_path / "kryon")
    reset_audit_log()
    audit1 = AuditLog("example")
    await audit1.log(action="a1")
    await audit1.log(action="a2")
    # Fresh instance — same path, same DB
    audit2 = AuditLog("example")
    entries = await audit2.query()
    assert len(entries) == 2
    actions = [e["action"] for e in entries]
    assert actions == ["a2", "a1"]  # newest first
    reset_kryon_home()


@pytest.mark.asyncio
async def test_update_is_blocked_by_trigger(tmp_path: Path) -> None:
    """CRITICAL: the audit log must be append-only. UPDATE must fail at the DB level."""
    set_kryon_home(tmp_path / "kryon")
    reset_audit_log()
    audit = AuditLog("test")
    await audit.log(action="original")
    # Try to update via raw SQL — must be blocked by the trigger
    with pytest.raises(aiosqlite.IntegrityError, match="append-only"):
        async with aiosqlite.connect(audit.path) as conn:
            await conn.execute("UPDATE audit_log SET action = 'modified' WHERE id = 1")
            await conn.commit()
    # Verify the original is unchanged
    entries = await audit.query()
    assert entries[0]["action"] == "original"
    reset_kryon_home()


@pytest.mark.asyncio
async def test_delete_is_blocked_by_trigger(tmp_path: Path) -> None:
    """CRITICAL: DELETE must fail at the DB level."""
    set_kryon_home(tmp_path / "kryon")
    reset_audit_log()
    audit = AuditLog("test")
    await audit.log(action="keep_me")
    with pytest.raises(aiosqlite.IntegrityError, match="append-only"):
        async with aiosqlite.connect(audit.path) as conn:
            await conn.execute("DELETE FROM audit_log WHERE id = 1")
            await conn.commit()
    # Verify still there
    assert await audit.count() == 1
    reset_kryon_home()


@pytest.mark.asyncio
async def test_query_with_filters(tmp_path: Path) -> None:
    set_kryon_home(tmp_path / "kryon")
    reset_audit_log()
    audit = AuditLog("test")
    await audit.log(action="a1", subagent="recon")
    await audit.log(action="a2", subagent="exploit")
    await audit.log(action="a3", subagent="recon")
    recon = await audit.query(subagent="recon")
    assert len(recon) == 2
    a1 = await audit.query(action="a1")
    assert len(a1) == 1
    entries = await audit.query()
    last_id = entries[0]["id"]
    newer = await audit.query(since_id=last_id)
    assert len(newer) == 0
    reset_kryon_home()


@pytest.mark.asyncio
async def test_secret_redaction_in_details(tmp_path: Path) -> None:
    set_kryon_home(tmp_path / "kryon")
    reset_audit_log()
    audit = AuditLog("test")
    await audit.log(
        action="tool_call",
        details={
            "tool": "sqlmap",
            "args": {"url": "http://target.com", "api_key": "sk-secret-value"},
            "user_token": "bearer-secret",
            "nested": {"password": "hunter2", "ok_field": "visible"},
        },
    )
    entries = await audit.query()
    details = entries[0]["details"]
    # Redacted keys
    assert details["args"]["api_key"] == "***REDACTED***"
    assert details["user_token"] == "***REDACTED***"
    assert details["nested"]["password"] == "***REDACTED***"
    # Non-redacted keys pass through
    assert details["tool"] == "sqlmap"
    assert details["args"]["url"] == "http://target.com"
    assert details["nested"]["ok_field"] == "visible"
    reset_kryon_home()


@pytest.mark.asyncio
async def test_count(tmp_path: Path) -> None:
    set_kryon_home(tmp_path / "kryon")
    reset_audit_log()
    audit = AuditLog("test")
    assert await audit.count() == 0
    for i in range(5):
        await audit.log(action=f"a{i}")
    assert await audit.count() == 5
    reset_kryon_home()


@pytest.mark.asyncio
async def test_query_newest_first(tmp_path: Path) -> None:
    set_kryon_home(tmp_path / "kryon")
    reset_audit_log()
    audit = AuditLog("test")
    await audit.log(action="first")
    await audit.log(action="second")
    await audit.log(action="third")
    entries = await audit.query()
    assert [e["action"] for e in entries] == ["third", "second", "first"]
    reset_kryon_home()


@pytest.mark.asyncio
async def test_details_parsed_back_to_dict(tmp_path: Path) -> None:
    set_kryon_home(tmp_path / "kryon")
    reset_audit_log()
    audit = AuditLog("test")
    # NOTE: field names must not contain secret substrings
    # (key/token/password/etc.) because the audit log redacts them.
    await audit.log(action="x", details={"name": "value", "count": 42})
    entries = await audit.query()
    assert isinstance(entries[0]["details"], dict)
    assert entries[0]["details"]["name"] == "value"
    assert entries[0]["details"]["count"] == 42
    reset_kryon_home()


@pytest.mark.asyncio
async def test_audit_log_file_location(tmp_path: Path) -> None:
    """Verify the file is at the expected path."""
    set_kryon_home(tmp_path / "kryon")
    reset_audit_log()
    audit = AuditLog("example")
    assert audit.path == tmp_path / "kryon" / "targets" / "example" / "audit.db"
    await audit.log(action="test")
    assert audit.path.exists()
    reset_kryon_home()


def test_invalid_target_id_rejected(tmp_path: Path) -> None:
    set_kryon_home(tmp_path / "kryon")
    reset_audit_log()
    with pytest.raises(AuditError):
        AuditLog("../etc")
    with pytest.raises(AuditError):
        AuditLog("name with spaces")
    with pytest.raises(AuditError):
        AuditLog("")
    with pytest.raises(AuditError):
        AuditLog("foo;rm -rf /")
    reset_kryon_home()


@pytest.mark.asyncio
async def test_get_audit_log_singleton(tmp_path: Path) -> None:
    set_kryon_home(tmp_path / "kryon")
    reset_audit_log()
    a1 = get_audit_log("example")
    a2 = get_audit_log("example")
    assert a1 is a2
    a3 = get_audit_log("other")
    assert a3 is not a1
    reset_audit_log()


def test_redact_secrets_helper() -> None:
    """Direct test of the redaction function."""
    obj = {
        "api_key": "secret",
        "nested": {"password": "also_secret", "ok": "fine"},
        "list": [{"token": "list_secret"}, "plain"],
        "OK": "untouched",
    }
    redacted = redact_secrets(obj)
    assert redacted["api_key"] == "***REDACTED***"
    assert redacted["nested"]["password"] == "***REDACTED***"
    assert redacted["nested"]["ok"] == "fine"
    assert redacted["list"][0]["token"] == "***REDACTED***"
    assert redacted["list"][1] == "plain"
    assert redacted["OK"] == "untouched"


@pytest.mark.asyncio
async def test_schema_is_idempotent(tmp_path: Path) -> None:
    """Calling log() multiple times must not break the schema."""
    set_kryon_home(tmp_path / "kryon")
    reset_audit_log()
    audit = AuditLog("test")
    await audit.log(action="first")
    await audit.log(action="second")
    await audit.log(action="third")
    assert await audit.count() == 3
    reset_kryon_home()


@pytest.mark.asyncio
async def test_empty_action_rejected(tmp_path: Path) -> None:
    set_kryon_home(tmp_path / "kryon")
    reset_audit_log()
    audit = AuditLog("test")
    with pytest.raises(AuditError):
        await audit.log(action="")
    reset_kryon_home()


@pytest.mark.asyncio
async def test_per_target_isolation(tmp_path: Path) -> None:
    """Different targets have independent audit logs."""
    set_kryon_home(tmp_path / "kryon")
    reset_audit_log()
    a = AuditLog("target-a")
    b = AuditLog("target-b")
    await a.log(action="from-a")
    await b.log(action="from-b")
    await b.log(action="from-b-2")
    a_entries = await a.query()
    b_entries = await b.query()
    assert len(a_entries) == 1
    assert len(b_entries) == 2
    assert a_entries[0]["action"] == "from-a"
    reset_kryon_home()


@pytest.mark.asyncio
async def test_query_limit(tmp_path: Path) -> None:
    set_kryon_home(tmp_path / "kryon")
    reset_audit_log()
    audit = AuditLog("test")
    for i in range(10):
        await audit.log(action=f"a{i}")
    entries = await audit.query(limit=3)
    assert len(entries) == 3
    reset_kryon_home()


@pytest.mark.asyncio
async def test_cost_field(tmp_path: Path) -> None:
    set_kryon_home(tmp_path / "kryon")
    reset_audit_log()
    audit = AuditLog("test")
    await audit.log(action="llm_call", cost_usd=0.005)
    entries = await audit.query()
    assert entries[0]["cost_usd"] == pytest.approx(0.005)
    reset_kryon_home()
