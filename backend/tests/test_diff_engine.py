"""Unit tests for diff_engine.py — no database, no I/O."""
import pytest
from app.core.diff_engine import compute_diff, rows_to_snapshots, make_snapshot


def snapshots(rows, pk):
    return rows_to_snapshots(rows, pk)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ACCOUNTS_PK = ["account_id"]

def account(id, credit_limit=5000, status="ACTIVE"):
    return {"account_id": id, "account_name": f"Acct {id}", "credit_limit": credit_limit, "status": status}


# ---------------------------------------------------------------------------
# Basic change types
# ---------------------------------------------------------------------------

def test_no_changes():
    rows = [account(1), account(2)]
    prev = snapshots(rows, ACCOUNTS_PK)
    curr = snapshots(rows, ACCOUNTS_PK)
    assert compute_diff("accounts", prev, curr) == []


def test_detect_insert():
    prev = snapshots([account(1)], ACCOUNTS_PK)
    curr = snapshots([account(1), account(2)], ACCOUNTS_PK)
    events = compute_diff("accounts", prev, curr)
    assert len(events) == 1
    assert events[0].change_type == "INSERT"
    assert events[0].pk_value == '{"account_id": 2}'


def test_detect_delete():
    prev = snapshots([account(1), account(2)], ACCOUNTS_PK)
    curr = snapshots([account(1)], ACCOUNTS_PK)
    events = compute_diff("accounts", prev, curr)
    assert len(events) == 1
    assert events[0].change_type == "DELETE"
    assert events[0].pk_value == '{"account_id": 2}'


def test_detect_update():
    prev = snapshots([account(1, credit_limit=5000)], ACCOUNTS_PK)
    curr = snapshots([account(1, credit_limit=9999)], ACCOUNTS_PK)
    events = compute_diff("accounts", prev, curr)
    assert len(events) == 1
    assert events[0].change_type == "UPDATE"
    assert "credit_limit" in events[0].diff_columns


# ---------------------------------------------------------------------------
# Multiple changes in one poll
# ---------------------------------------------------------------------------

def test_multiple_changes():
    prev = snapshots([account(1), account(2), account(3)], ACCOUNTS_PK)
    curr = snapshots([account(1, status="SUSPENDED"), account(3), account(4)], ACCOUNTS_PK)
    events = compute_diff("accounts", prev, curr)

    types = {e.change_type for e in events}
    assert types == {"UPDATE", "DELETE", "INSERT"}
    assert len(events) == 3


# ---------------------------------------------------------------------------
# First poll (no previous snapshot)
# ---------------------------------------------------------------------------

def test_first_poll_all_inserts():
    curr = snapshots([account(1), account(2)], ACCOUNTS_PK)
    events = compute_diff("accounts", [], curr)
    assert len(events) == 2
    assert all(e.change_type == "INSERT" for e in events)


def test_empty_table_no_events():
    assert compute_diff("accounts", [], []) == []


# ---------------------------------------------------------------------------
# UPDATE diff_columns accuracy
# ---------------------------------------------------------------------------

def test_update_diff_columns_only_changed():
    prev = snapshots([account(1, credit_limit=1000, status="ACTIVE")], ACCOUNTS_PK)
    curr = snapshots([account(1, credit_limit=9999, status="ACTIVE")], ACCOUNTS_PK)
    events = compute_diff("accounts", prev, curr)
    assert events[0].diff_columns == ["credit_limit"]


def test_update_multiple_diff_columns():
    prev = snapshots([account(1, credit_limit=1000, status="ACTIVE")], ACCOUNTS_PK)
    curr = snapshots([account(1, credit_limit=9999, status="SUSPENDED")], ACCOUNTS_PK)
    events = compute_diff("accounts", prev, curr)
    assert set(events[0].diff_columns) == {"credit_limit", "status"}


# ---------------------------------------------------------------------------
# before_data / after_data
# ---------------------------------------------------------------------------

def test_insert_has_no_before_data():
    prev = snapshots([], ACCOUNTS_PK)
    curr = snapshots([account(1)], ACCOUNTS_PK)
    events = compute_diff("accounts", prev, curr)
    assert events[0].before_data is None
    assert events[0].after_data is not None


def test_delete_has_no_after_data():
    prev = snapshots([account(1)], ACCOUNTS_PK)
    curr = snapshots([], ACCOUNTS_PK)
    events = compute_diff("accounts", prev, curr)
    assert events[0].after_data is None
    assert events[0].before_data is not None


def test_update_has_both_before_and_after():
    prev = snapshots([account(1, credit_limit=1000)], ACCOUNTS_PK)
    curr = snapshots([account(1, credit_limit=9999)], ACCOUNTS_PK)
    events = compute_diff("accounts", prev, curr)
    assert events[0].before_data is not None
    assert events[0].after_data is not None


# ---------------------------------------------------------------------------
# Composite primary key
# ---------------------------------------------------------------------------

def test_composite_pk():
    pk = ["customer_id", "program_code"]
    prev = rows_to_snapshots(
        [{"customer_id": 1, "program_code": "GOLD", "points": 100}], pk
    )
    curr = rows_to_snapshots(
        [{"customer_id": 1, "program_code": "GOLD", "points": 200}], pk
    )
    events = compute_diff("memberships", prev, curr)
    assert len(events) == 1
    assert events[0].change_type == "UPDATE"
    assert "points" in events[0].diff_columns
