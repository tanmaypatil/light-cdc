from __future__ import annotations

import logging
import os
from pathlib import Path

from app.db.sqlite_engine import get_connection, get_db_path
from app.models.watch_config import EnvironmentConfig

logger = logging.getLogger(__name__)


class RetentionManager:
    def __init__(self, data_dir: str) -> None:
        self._data_dir = data_dir

    def enforce(self, env_config: EnvironmentConfig) -> None:
        db_path = get_db_path(self._data_dir, env_config.name)
        if not db_path.exists():
            return
        self._purge_by_age(db_path, env_config.retention.max_days)
        self._purge_by_size(db_path, env_config.retention.max_size_mb)

    def purge_all(self, env_name: str) -> None:
        db_path = get_db_path(self._data_dir, env_name)
        if not db_path.exists():
            return
        with get_connection(db_path) as conn:
            conn.execute("DELETE FROM rollback_events")
            conn.execute("DELETE FROM change_events")
            conn.execute("DELETE FROM row_snapshots")
            conn.execute("DELETE FROM poll_runs")
            conn.execute("VACUUM")
        logger.info("Full purge completed for environment '%s'", env_name)

    def _purge_by_age(self, db_path: Path, max_days: int) -> None:
        with get_connection(db_path) as conn:
            old_runs = conn.execute(
                "SELECT id FROM poll_runs WHERE started_at < datetime('now', ?)",
                (f"-{max_days} days",),
            ).fetchall()

            if not old_runs:
                return

            ids = [r["id"] for r in old_runs]
            self._delete_poll_runs(conn, ids)
            logger.info("Age purge: removed %d poll runs older than %d days", len(ids), max_days)

    def _purge_by_size(self, db_path: Path, max_size_mb: int) -> None:
        max_bytes = max_size_mb * 1024 * 1024
        batch_size = 10

        while db_path.stat().st_size > max_bytes:
            with get_connection(db_path) as conn:
                old_runs = conn.execute(
                    "SELECT id FROM poll_runs ORDER BY started_at ASC LIMIT ?",
                    (batch_size,),
                ).fetchall()

                if not old_runs:
                    break

                ids = [r["id"] for r in old_runs]
                self._delete_poll_runs(conn, ids)
                conn.execute("VACUUM")

            logger.info(
                "Size purge: removed %d poll runs, db size now %.1f MB",
                len(ids),
                db_path.stat().st_size / (1024 * 1024),
            )

    def _delete_poll_runs(self, conn, ids: list[int]) -> None:
        placeholders = ",".join("?" * len(ids))
        conn.execute(f"DELETE FROM row_snapshots WHERE poll_run_id IN ({placeholders})", ids)
        conn.execute(f"DELETE FROM change_events WHERE poll_run_id IN ({placeholders})", ids)
        conn.execute(f"DELETE FROM poll_runs WHERE id IN ({placeholders})", ids)
