from __future__ import annotations

"""Oracle DAL stub — not yet implemented.

Key Oracle differences to handle when implementing:
  - Import:      pip install oracledb  (thin mode, no Oracle Client needed)
  - Param style: :name  (not %(name)s like psycopg2)
  - Schema:      owner.table  (schema_name = Oracle username / owner)
  - Introspection: ALL_TAB_COLUMNS / ALL_TAB_COLS  (not information_schema)
  - Row limit:   FETCH FIRST n ROWS ONLY  (12c+), or ROWNUM for 11g
  - Checksum:    ORA_HASH(expr) — single-column; for multi-col use
                 ORA_HASH(col1 || '|' || col2 ...)
  - No BIT_XOR:  use SUM(ORA_HASH(...)) with MOD to keep it bounded
  - Autocommit:  oracledb connections default to manual commit
  - Timestamps:  Oracle returns datetime objects; convert to ISO-8601 for storage
"""

from app.dal.base import BaseDAL


class OracleDAL(BaseDAL):
    def __init__(self, connection_url: str) -> None:
        raise NotImplementedError(
            "OracleDAL is not yet implemented. "
            "Install oracledb and implement this class following the notes above."
        )

    def fetch_table(self, schema, table, exclude_columns):
        raise NotImplementedError

    def fetch_table_since(self, schema, table, exclude_columns, updated_at_col, since):
        raise NotImplementedError

    def fetch_row_count(self, schema, table):
        raise NotImplementedError

    def fetch_table_checksum(self, schema, table, primary_key):
        raise NotImplementedError

    def fetch_table_schema(self, schema, table):
        raise NotImplementedError

    def fetch_rows(self, schema, table):
        raise NotImplementedError

    def fetch_raw(self, sql):
        raise NotImplementedError

    def execute_dml(self, sql, params):
        raise NotImplementedError

    def test_connection(self):
        raise NotImplementedError

    def close(self):
        raise NotImplementedError
