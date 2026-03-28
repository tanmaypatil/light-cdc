from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.config import settings
from app.db.sqlite_engine import get_connection, get_db_path

router = APIRouter()


def _get_db(env: str):
    db_path = get_db_path(settings.sqlite_data_dir, env)
    if not db_path.exists():
        raise HTTPException(status_code=404, detail=f"Environment '{env}' has no data yet")
    return db_path


@router.get("/environments/{env}/changes")
def list_changes(
    env: str,
    table: Optional[str] = None,
    change_type: Optional[str] = Query(default=None, alias="type"),
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    page: int = 1,
    page_size: int = 50,
):
    db_path = _get_db(env)
    filters, params = [], []

    if table:
        filters.append("table_name = ?")
        params.append(table)
    if change_type:
        filters.append("change_type = ?")
        params.append(change_type.upper())
    if from_date:
        filters.append("detected_at >= ?")
        params.append(from_date)
    if to_date:
        filters.append("detected_at <= ?")
        params.append(to_date)

    where = ("WHERE " + " AND ".join(filters)) if filters else ""
    offset = (page - 1) * page_size

    with get_connection(db_path) as conn:
        total = conn.execute(f"SELECT COUNT(*) FROM change_events {where}", params).fetchone()[0]
        rows = conn.execute(
            f"SELECT * FROM change_events {where} ORDER BY detected_at DESC LIMIT ? OFFSET ?",
            params + [page_size, offset],
        ).fetchall()

    return {
        "data": [dict(r) for r in rows],
        "meta": {"page": page, "page_size": page_size, "total": total, "environment": env},
    }


@router.get("/environments/{env}/changes/{change_id}")
def get_change(env: str, change_id: int):
    db_path = _get_db(env)
    with get_connection(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM change_events WHERE id = ?", (change_id,)
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Change event {change_id} not found")
    return dict(row)
