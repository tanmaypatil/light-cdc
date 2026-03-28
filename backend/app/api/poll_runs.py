from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.config import settings
from app.db.sqlite_engine import get_connection, get_db_path

router = APIRouter()


def _get_db(env: str):
    db_path = get_db_path(settings.sqlite_data_dir, env)
    if not db_path.exists():
        raise HTTPException(status_code=404, detail=f"Environment '{env}' has no data yet")
    return db_path


@router.get("/environments/{env}/poll-runs")
def list_poll_runs(env: str, page: int = 1, page_size: int = 20):
    db_path = _get_db(env)
    offset = (page - 1) * page_size
    with get_connection(db_path) as conn:
        total = conn.execute("SELECT COUNT(*) FROM poll_runs").fetchone()[0]
        rows = conn.execute(
            "SELECT * FROM poll_runs ORDER BY started_at DESC LIMIT ? OFFSET ?",
            (page_size, offset),
        ).fetchall()
    return {
        "data": [dict(r) for r in rows],
        "meta": {"page": page, "page_size": page_size, "total": total, "environment": env},
    }


@router.get("/environments/{env}/poll-runs/{run_id}")
def get_poll_run(env: str, run_id: int):
    db_path = _get_db(env)
    with get_connection(db_path) as conn:
        row = conn.execute("SELECT * FROM poll_runs WHERE id = ?", (run_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Poll run {run_id} not found")
    return dict(row)


@router.post("/environments/{env}/poll-runs/trigger", status_code=202)
def trigger_poll(env: str):
    from app.main import get_poller
    try:
        get_poller().trigger_now(env)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"message": f"Poll triggered for environment '{env}'"}
