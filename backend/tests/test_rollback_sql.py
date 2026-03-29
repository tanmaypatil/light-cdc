"""Unit tests for rollback SQL generation — no database needed."""
import json
import pytest
from app.core.rollback_engine import RollbackEngine


def make_event(change_type, pk, before=None, after=None):
    """Build a minimal change_event dict as returned from SQLite."""
    return {
        "id": 1,
        "table_name": "accounts",
        "pk_value": json.dumps(pk, sort_keys=True),
        "change_type": change_type,
        "before_data": json.dumps(before) if before else None,
        "after_data": json.dumps(after) if after else None,
        "rolled_back": 0,
    }


# We test _build_rollback_sql directly — it's pure given an event dict.
def build_sql(event):
    engine = RollbackEngine.__new__(RollbackEngine)
    return engine._build_rollback_sql(event)


# ---------------------------------------------------------------------------
# UPDATE rollback
# ---------------------------------------------------------------------------

def test_update_rollback_sql():
    event = make_event(
        "UPDATE",
        pk={"account_id": 1},
        before={"account_id": 1, "credit_limit": 5000, "status": "ACTIVE"},
    )
    sql, params = build_sql(event)
    assert "UPDATE" in sql
    assert '"accounts"' in sql
    assert "SET" in sql
    assert "WHERE" in sql
    assert params["set_credit_limit"] == 5000
    assert params["set_status"] == "ACTIVE"
    assert params["pk_account_id"] == 1


def test_update_rollback_excludes_pk_from_set():
    event = make_event(
        "UPDATE",
        pk={"account_id": 1},
        before={"account_id": 1, "credit_limit": 5000},
    )
    sql, params = build_sql(event)
    assert '"account_id"' not in sql.split("SET")[1].split("WHERE")[0]


# ---------------------------------------------------------------------------
# INSERT rollback
# ---------------------------------------------------------------------------

def test_insert_rollback_sql():
    event = make_event("INSERT", pk={"account_id": 5})
    sql, params = build_sql(event)
    assert "DELETE FROM" in sql
    assert '"accounts"' in sql
    assert "WHERE" in sql
    assert params["pk_account_id"] == 5


# ---------------------------------------------------------------------------
# DELETE rollback
# ---------------------------------------------------------------------------

def test_delete_rollback_sql():
    event = make_event(
        "DELETE",
        pk={"account_id": 3},
        before={"account_id": 3, "account_name": "Apex", "credit_limit": 1000},
    )
    sql, params = build_sql(event)
    assert "INSERT INTO" in sql
    assert '"accounts"' in sql
    assert "VALUES" in sql
    assert params["col_account_id"] == 3
    assert params["col_account_name"] == "Apex"
    assert params["col_credit_limit"] == 1000


# ---------------------------------------------------------------------------
# Composite PK
# ---------------------------------------------------------------------------

def test_composite_pk_update_rollback():
    event = make_event(
        "UPDATE",
        pk={"customer_id": 1, "program_code": "GOLD"},
        before={"customer_id": 1, "program_code": "GOLD", "points": 100},
    )
    event["table_name"] = "memberships"
    sql, params = build_sql(event)
    assert "pk_customer_id" in params
    assert "pk_program_code" in params
    assert params["pk_customer_id"] == 1


def test_unknown_change_type_raises():
    event = make_event("TRUNCATE", pk={"account_id": 1})
    with pytest.raises(ValueError, match="Unknown change_type"):
        build_sql(event)
