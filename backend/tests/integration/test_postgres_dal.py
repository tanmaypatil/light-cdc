"""Integration tests for PostgresDAL — requires TEST_DATABASE_URL env var.

Run with:
    TEST_DATABASE_URL=postgresql://lightcdc:pass@localhost:5432/lightcdc_dev \
    pytest backend/tests/integration/
"""
import os
import pytest
from app.dal.postgres_dal import PostgresDAL

TEST_URL = os.environ.get("TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not TEST_URL, reason="TEST_DATABASE_URL not set"
)


@pytest.fixture(scope="module")
def dal():
    d = PostgresDAL(TEST_URL)
    yield d
    d.close()


def test_connection(dal):
    assert dal.test_connection() is True


def test_fetch_row_count(dal):
    count = dal.fetch_row_count("public", "accounts")
    assert isinstance(count, int)
    assert count >= 0


def test_fetch_table_returns_rows(dal):
    rows = dal.fetch_table("public", "accounts", [])
    assert isinstance(rows, list)
    if rows:
        assert "account_id" in rows[0]


def test_fetch_table_excludes_columns(dal):
    rows = dal.fetch_table("public", "accounts", ["updated_at"])
    if rows:
        assert "updated_at" not in rows[0]


def test_fetch_table_schema(dal):
    schema = dal.fetch_table_schema("public", "accounts")
    assert isinstance(schema, list)
    col_names = [c["column_name"] for c in schema]
    assert "account_id" in col_names
    assert "credit_limit" in col_names


def test_fetch_rows_limit(dal):
    rows = dal.fetch_rows("public", "accounts")
    assert len(rows) <= 100


def test_fetch_table_checksum_is_stable(dal):
    c1 = dal.fetch_table_checksum("public", "accounts", ["account_id"])
    c2 = dal.fetch_table_checksum("public", "accounts", ["account_id"])
    assert c1 == c2


def test_fetch_table_checksum_changes_on_update(dal):
    before = dal.fetch_table_checksum("public", "accounts", ["account_id"])
    dal.execute_dml(
        'UPDATE "public"."accounts" SET credit_limit = credit_limit + 1 WHERE account_id = 1',
        {}
    )
    after = dal.fetch_table_checksum("public", "accounts", ["account_id"])
    # Restore
    dal.execute_dml(
        'UPDATE "public"."accounts" SET credit_limit = credit_limit - 1 WHERE account_id = 1',
        {}
    )
    assert before != after


def test_fetch_table_since(dal):
    # Rows updated before epoch should return nothing
    rows = dal.fetch_table_since(
        "public", "accounts", [], "updated_at", "1970-01-01T00:00:00+00:00"
    )
    assert isinstance(rows, list)


def test_execute_dml_returns_row_count(dal):
    affected = dal.execute_dml(
        'UPDATE "public"."accounts" SET credit_limit = credit_limit WHERE account_id = 1',
        {}
    )
    assert affected == 1


def test_fetch_raw_select(dal):
    rows = dal.fetch_raw("SELECT 1 AS val")
    assert rows == [{"val": 1}]
