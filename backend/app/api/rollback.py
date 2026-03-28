from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException

from app.config import settings
from app.core.rollback_engine import RollbackEngine
from app.dal.base import BaseDAL
from app.db.sqlite_engine import get_connection, get_db_path
from app.models.watch_config import WatchConfig

router = APIRouter()


@router.post("/environments/{env}/changes/{change_id}/rollback")
def rollback_change(env: str, change_id: int):
    watch_config = WatchConfig.load(settings.watch_config_path)
    env_config = watch_config.get_environment(env)
    if not env_config:
        raise HTTPException(status_code=404, detail=f"Environment '{env}' not found in watch.json")

    connection_url = os.environ.get(env_config.connection_env_var)
    if not connection_url:
        raise HTTPException(
            status_code=500,
            detail=f"Connection env var '{env_config.connection_env_var}' is not set",
        )

    engine = RollbackEngine(settings.sqlite_data_dir, env)
    dal = BaseDAL.from_config(env_config, connection_url)
    try:
        rollback_event_id = engine.rollback(change_id, dal)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        dal.close()

    db_path = get_db_path(settings.sqlite_data_dir, env)
    with get_connection(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM rollback_events WHERE id = ?", (rollback_event_id,)
        ).fetchone()

    return {"message": "Rollback applied successfully", "rollback_event": dict(row)}


@router.get("/environments/{env}/rollbacks")
def list_rollbacks(env: str, page: int = 1, page_size: int = 20):
    db_path = get_db_path(settings.sqlite_data_dir, env)
    if not db_path.exists():
        raise HTTPException(status_code=404, detail=f"Environment '{env}' has no data yet")

    offset = (page - 1) * page_size
    with get_connection(db_path) as conn:
        total = conn.execute("SELECT COUNT(*) FROM rollback_events").fetchone()[0]
        rows = conn.execute(
            "SELECT * FROM rollback_events ORDER BY executed_at DESC LIMIT ? OFFSET ?",
            (page_size, offset),
        ).fetchall()

    return {
        "data": [dict(r) for r in rows],
        "meta": {"page": page, "page_size": page_size, "total": total, "environment": env},
    }
