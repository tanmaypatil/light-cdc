from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from app.db.sqlite_engine import get_connection, get_db_path
from app.core.diff_engine import ChangeEvent, RowSnapshot


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SnapshotStore:
    def __init__(self, data_dir: str, env_name: str) -> None:
        self._db_path = get_db_path(data_dir, env_name)
        self._env = env_name

    # ------------------------------------------------------------------
    # Poll runs
    # ------------------------------------------------------------------

    def start_poll_run(self) -> int:
        with get_connection(self._db_path) as conn:
            cur = conn.execute(
                "INSERT INTO poll_runs (environment, started_at, status) VALUES (?, ?, 'running')",
                (self._env, _now()),
            )
            return cur.lastrowid

    def finish_poll_run(
        self,
        poll_run_id: int,
        tables_polled: int,
        changes_found: int,
        error: str | None = None,
    ) -> None:
        status = "error" if error else "success"
        with get_connection(self._db_path) as conn:
            conn.execute(
                """UPDATE poll_runs
                   SET finished_at=?, status=?, tables_polled=?, changes_found=?, error_message=?
                   WHERE id=?""",
                (_now(), status, tables_polled, changes_found, error, poll_run_id),
            )

    # ------------------------------------------------------------------
    # Snapshots
    # ------------------------------------------------------------------

    def write_snapshots(
        self,
        poll_run_id: int,
        table_name: str,
        snapshots: list[RowSnapshot],
    ) -> None:
        now = _now()
        rows = [
            (poll_run_id, table_name, s.pk_value, s.row_data, s.row_hash, now)
            for s in snapshots
        ]
        with get_connection(self._db_path) as conn:
            conn.executemany(
                "INSERT INTO row_snapshots (poll_run_id, table_name, pk_value, row_data, row_hash, captured_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                rows,
            )

    def get_latest_snapshots(self, table_name: str) -> list[RowSnapshot]:
        """Return the most recent snapshot set for the given table."""
        with get_connection(self._db_path) as conn:
            # Find the latest successful poll run that has snapshots for this table
            row = conn.execute(
                """SELECT rs.poll_run_id
                   FROM row_snapshots rs
                   JOIN poll_runs pr ON pr.id = rs.poll_run_id
                   WHERE rs.table_name = ? AND pr.status = 'success'
                   ORDER BY pr.started_at DESC
                   LIMIT 1""",
                (table_name,),
            ).fetchone()

            if not row:
                return []

            poll_run_id = row["poll_run_id"]
            rows = conn.execute(
                "SELECT pk_value, row_data, row_hash FROM row_snapshots WHERE poll_run_id=? AND table_name=?",
                (poll_run_id, table_name),
            ).fetchall()

        return [
            RowSnapshot(pk_value=r["pk_value"], row_data=r["row_data"], row_hash=r["row_hash"])
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Per-table poll state  (large-table optimisation)
    # ------------------------------------------------------------------

    def get_table_poll_state(self, table_name: str) -> dict | None:
        """Return {last_polled_at, last_checksum, last_row_count} or None if first poll."""
        with get_connection(self._db_path) as conn:
            row = conn.execute(
                "SELECT last_polled_at, last_checksum, last_row_count FROM table_poll_state WHERE table_name=?",
                (table_name,),
            ).fetchone()
        return dict(row) if row else None

    def save_table_poll_state(
        self,
        table_name: str,
        last_polled_at: str,
        last_checksum: str | None,
        last_row_count: int,
    ) -> None:
        with get_connection(self._db_path) as conn:
            conn.execute(
                """INSERT INTO table_poll_state (table_name, last_polled_at, last_checksum, last_row_count)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(table_name) DO UPDATE SET
                     last_polled_at=excluded.last_polled_at,
                     last_checksum=excluded.last_checksum,
                     last_row_count=excluded.last_row_count""",
                (table_name, last_polled_at, last_checksum, last_row_count),
            )

    # ------------------------------------------------------------------
    # Change events
    # ------------------------------------------------------------------

    def write_change_events(
        self,
        poll_run_id: int,
        events: list[ChangeEvent],
    ) -> None:
        now = _now()
        rows = [
            (
                poll_run_id,
                e.table_name,
                e.pk_value,
                e.change_type,
                e.before_data,
                e.after_data,
                json.dumps(e.diff_columns),
                now,
            )
            for e in events
        ]
        with get_connection(self._db_path) as conn:
            conn.executemany(
                """INSERT INTO change_events
                   (poll_run_id, table_name, pk_value, change_type, before_data, after_data, diff_columns, detected_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                rows,
            )
