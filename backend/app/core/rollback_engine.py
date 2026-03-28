from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from app.dal.base import BaseDAL
from app.db.sqlite_engine import get_connection, get_db_path

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class RollbackEngine:
    def __init__(self, data_dir: str, env_name: str) -> None:
        self._db_path = get_db_path(data_dir, env_name)
        self._env = env_name

    def rollback(self, change_event_id: int, dal: BaseDAL) -> int:
        """
        Execute rollback for a change event. Returns the rollback_event id.
        Raises ValueError if the event doesn't exist or was already rolled back.
        """
        event = self._load_event(change_event_id)

        if event["rolled_back"]:
            raise ValueError(f"Change event {change_event_id} has already been rolled back")

        sql, params = self._build_rollback_sql(event)
        logger.info("Rolling back change_event=%d sql=%s", change_event_id, sql)

        try:
            dal.execute_dml(sql, params)
            status, error = "success", None
        except Exception as e:
            status, error = "error", str(e)
            logger.exception("Rollback failed for change_event=%d", change_event_id)

        rollback_event_id = self._record_rollback(change_event_id, event, sql, params, status, error)

        if status == "success":
            self._mark_rolled_back(change_event_id, rollback_event_id)
        else:
            raise RuntimeError(f"Rollback execution failed: {error}")

        return rollback_event_id

    def _load_event(self, change_event_id: int) -> dict:
        with get_connection(self._db_path) as conn:
            row = conn.execute(
                "SELECT * FROM change_events WHERE id = ?", (change_event_id,)
            ).fetchone()
        if not row:
            raise ValueError(f"Change event {change_event_id} not found")
        return dict(row)

    def _build_rollback_sql(self, event: dict) -> tuple[str, dict]:
        table = event["table_name"]
        pk_dict: dict = json.loads(event["pk_value"])
        change_type = event["change_type"]

        # Derive schema from table name — stored as plain table name in change_events.
        # schema is not stored in change_events, default to public.
        schema = "public"

        if change_type == "UPDATE":
            before: dict = json.loads(event["before_data"])
            # Restore all before values except the PK columns
            set_cols = {k: v for k, v in before.items() if k not in pk_dict}
            set_clause = ", ".join(f'"{col}" = %(set_{col})s' for col in set_cols)
            where_clause = " AND ".join(f'"{col}" = %(pk_{col})s' for col in pk_dict)
            sql = f'UPDATE "{schema}"."{table}" SET {set_clause} WHERE {where_clause}'
            params = {f"set_{k}": v for k, v in set_cols.items()}
            params.update({f"pk_{k}": v for k, v in pk_dict.items()})

        elif change_type == "INSERT":
            # Rollback of an INSERT = DELETE the row
            where_clause = " AND ".join(f'"{col}" = %(pk_{col})s' for col in pk_dict)
            sql = f'DELETE FROM "{schema}"."{table}" WHERE {where_clause}'
            params = {f"pk_{k}": v for k, v in pk_dict.items()}

        elif change_type == "DELETE":
            # Rollback of a DELETE = re-INSERT the row
            before = json.loads(event["before_data"])
            cols = ", ".join(f'"{col}"' for col in before)
            placeholders = ", ".join(f"%(col_{col})s" for col in before)
            sql = f'INSERT INTO "{schema}"."{table}" ({cols}) VALUES ({placeholders})'
            params = {f"col_{k}": v for k, v in before.items()}

        else:
            raise ValueError(f"Unknown change_type: {change_type}")

        return sql, params

    def _record_rollback(
        self,
        change_event_id: int,
        event: dict,
        sql: str,
        params: dict,
        status: str,
        error: str | None,
    ) -> int:
        sql_repr = f"{sql} -- params: {json.dumps(params, default=str)}"
        with get_connection(self._db_path) as conn:
            cur = conn.execute(
                """INSERT INTO rollback_events
                   (change_event_id, table_name, pk_value, rollback_sql, executed_at, status, error_message)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    change_event_id,
                    event["table_name"],
                    event["pk_value"],
                    sql_repr,
                    _now(),
                    status,
                    error,
                ),
            )
            return cur.lastrowid

    def _mark_rolled_back(self, change_event_id: int, rollback_event_id: int) -> None:
        with get_connection(self._db_path) as conn:
            conn.execute(
                "UPDATE change_events SET rolled_back=1, rollback_event_id=? WHERE id=?",
                (rollback_event_id, change_event_id),
            )
