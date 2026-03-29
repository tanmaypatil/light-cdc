from __future__ import annotations

import psycopg2
import psycopg2.extras

from app.dal.base import BaseDAL


class PostgresDAL(BaseDAL):
    def __init__(self, connection_url: str) -> None:
        self._url = connection_url
        self._conn = psycopg2.connect(connection_url)
        self._conn.autocommit = False

    def fetch_table(
        self,
        schema: str,
        table: str,
        exclude_columns: list[str],
    ) -> list[dict]:
        with self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(f'SELECT * FROM "{schema}"."{table}"')
            rows = cur.fetchall()

        if not exclude_columns:
            return [dict(row) for row in rows]

        exclude_set = set(exclude_columns)
        return [{k: v for k, v in row.items() if k not in exclude_set} for row in rows]

    def fetch_table_since(
        self,
        schema: str,
        table: str,
        exclude_columns: list[str],
        updated_at_col: str,
        since: str,
    ) -> list[dict]:
        with self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                f'SELECT * FROM "{schema}"."{table}" WHERE "{updated_at_col}" > %s',
                (since,),
            )
            rows = cur.fetchall()
        if not exclude_columns:
            return [dict(row) for row in rows]
        exclude_set = set(exclude_columns)
        return [{k: v for k, v in row.items() if k not in exclude_set} for row in rows]

    def fetch_row_count(self, schema: str, table: str) -> int:
        with self._conn.cursor() as cur:
            cur.execute(f'SELECT COUNT(*) FROM "{schema}"."{table}"')
            return cur.fetchone()[0]

    def fetch_table_checksum(self, schema: str, table: str, primary_key: list[str]) -> str:
        # XOR-aggregate of full-row hashes; stable across row order, sensitive to any column change
        with self._conn.cursor() as cur:
            cur.execute(
                f"""SELECT COALESCE(
                      CAST(BIT_XOR(HASHTEXT(ROW(t.*)::TEXT)::BIT(32)) AS TEXT),
                      '0'
                    )
                    FROM "{schema}"."{table}" t""",
            )
            return cur.fetchone()[0]

    def fetch_table_schema(self, schema: str, table: str) -> list[dict]:
        with self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """SELECT column_name, data_type, is_nullable, column_default
                   FROM information_schema.columns
                   WHERE table_schema = %s AND table_name = %s
                   ORDER BY ordinal_position""",
                (schema, table),
            )
            return [dict(row) for row in cur.fetchall()]

    def fetch_rows(self, schema: str, table: str) -> list[dict]:
        with self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(f'SELECT * FROM "{schema}"."{table}" LIMIT 100')
            return [dict(row) for row in cur.fetchall()]

    def fetch_raw(self, sql: str) -> list[dict]:
        with self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql)
            return [dict(row) for row in cur.fetchall()]

    def execute_dml(self, sql: str, params: dict) -> int:
        with self._conn.cursor() as cur:
            cur.execute(sql, params or None)
            affected = cur.rowcount
        self._conn.commit()
        return affected

    def test_connection(self) -> bool:
        try:
            with self._conn.cursor() as cur:
                cur.execute("SELECT 1")
            return True
        except Exception:
            return False

    def close(self) -> None:
        if self._conn and not self._conn.closed:
            self._conn.close()
