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

    def execute_dml(self, sql: str, params: dict) -> None:
        with self._conn.cursor() as cur:
            cur.execute(sql, params)
        self._conn.commit()

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
