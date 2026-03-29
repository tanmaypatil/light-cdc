"""E2E tests — requires docker-compose stack running on localhost:8000.

Run with:
    pytest backend/tests/e2e/

All tests use the 'dev' environment and clean up after themselves.
"""
import time
import pytest
import requests

BASE = "http://localhost:8000/api/v1"
ENV = "dev"


def poll():
    r = requests.post(f"{BASE}/environments/{ENV}/poll-runs/trigger")
    assert r.status_code == 202
    time.sleep(4)  # wait for poll to complete


def execute(sql):
    r = requests.post(
        f"{BASE}/environments/{ENV}/playground/execute",
        json={"sql": sql},
    )
    assert r.status_code == 200, r.text
    return r.json()


def latest_changes(table=None):
    params = {"page": 1}
    if table:
        params["table"] = table
    r = requests.get(f"{BASE}/environments/{ENV}/changes", params=params)
    assert r.status_code == 200
    return r.json()["data"]


@pytest.fixture(autouse=True)
def baseline_poll():
    """Ensure a clean baseline snapshot before each test."""
    poll()
    yield


# ---------------------------------------------------------------------------
# Scenario 1: Detect INSERT
# ---------------------------------------------------------------------------

def test_detect_insert():
    execute(
        "INSERT INTO accounts (account_code, account_name, status, credit_limit, account_type) "
        "VALUES ('E2E-INS', 'E2E Insert Test', 'ACTIVE', 1, 'STANDARD')"
    )
    poll()

    changes = latest_changes("accounts")
    inserts = [c for c in changes if c["change_type"] == "INSERT" and "E2E-INS" in (c.get("after_data") or "")]
    assert len(inserts) >= 1

    # Cleanup
    execute("DELETE FROM accounts WHERE account_code = 'E2E-INS'")
    poll()


# ---------------------------------------------------------------------------
# Scenario 2: Detect UPDATE and diff_columns
# ---------------------------------------------------------------------------

def test_detect_update():
    # Use account_id=1 which always exists from seed
    original = execute("SELECT credit_limit FROM accounts WHERE account_id = 1")
    orig_limit = original["rows"][0]["credit_limit"]

    execute("UPDATE accounts SET credit_limit = 777777 WHERE account_id = 1")
    poll()

    changes = latest_changes("accounts")
    updates = [
        c for c in changes
        if c["change_type"] == "UPDATE" and '"account_id": 1' in c["pk_value"]
    ]
    assert len(updates) >= 1
    assert "credit_limit" in updates[0]["diff_columns"]

    # Restore
    execute(f"UPDATE accounts SET credit_limit = {orig_limit} WHERE account_id = 1")
    poll()


# ---------------------------------------------------------------------------
# Scenario 3: Detect DELETE
# ---------------------------------------------------------------------------

def test_detect_delete():
    execute(
        "INSERT INTO accounts (account_code, account_name, status, credit_limit, account_type) "
        "VALUES ('E2E-DEL', 'E2E Delete Test', 'ACTIVE', 1, 'STANDARD')"
    )
    poll()

    execute("DELETE FROM accounts WHERE account_code = 'E2E-DEL'")
    poll()

    changes = latest_changes("accounts")
    deletes = [c for c in changes if c["change_type"] == "DELETE"]
    assert len(deletes) >= 1


# ---------------------------------------------------------------------------
# Scenario 4: Rollback an UPDATE
# ---------------------------------------------------------------------------

def test_rollback_update():
    original = execute("SELECT credit_limit FROM accounts WHERE account_id = 2")
    orig_limit = original["rows"][0]["credit_limit"]

    execute("UPDATE accounts SET credit_limit = 888888 WHERE account_id = 2")
    poll()

    changes = latest_changes("accounts")
    update = next(
        (c for c in changes if c["change_type"] == "UPDATE" and '"account_id": 2' in c["pk_value"]),
        None,
    )
    assert update is not None, "UPDATE change event not found"

    r = requests.post(f"{BASE}/environments/{ENV}/changes/{update['id']}/rollback")
    assert r.status_code == 200

    result = execute("SELECT credit_limit FROM accounts WHERE account_id = 2")
    assert result["rows"][0]["credit_limit"] == orig_limit


# ---------------------------------------------------------------------------
# Scenario 5: Incremental strategy picks up single change
# ---------------------------------------------------------------------------

def test_incremental_strategy_detects_one_change():
    # Ensure accounts exceeds threshold by checking count
    count = execute("SELECT COUNT(*) AS cnt FROM accounts")["rows"][0]["cnt"]
    if count <= 25:
        pytest.skip(f"accounts only has {count} rows — below threshold for incremental strategy")

    execute("UPDATE accounts SET credit_limit = 123456 WHERE account_id = 1")
    poll()

    changes = latest_changes("accounts")
    updates = [
        c for c in changes
        if c["change_type"] == "UPDATE" and '"account_id": 1' in c["pk_value"]
    ]
    assert len(updates) >= 1
    assert "credit_limit" in updates[0]["diff_columns"]

    # Restore
    execute("UPDATE accounts SET credit_limit = 50000 WHERE account_id = 1")
    poll()
