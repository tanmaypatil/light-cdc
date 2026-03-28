from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException, Query

from app.config import settings
from app.core.retention_manager import RetentionManager
from app.db.sqlite_engine import get_connection, get_db_path
from app.models.watch_config import WatchConfig

router = APIRouter()


def _require_env(env: str):
    watch_config = WatchConfig.load(settings.watch_config_path)
    env_config = watch_config.get_environment(env)
    if not env_config:
        raise HTTPException(status_code=404, detail=f"Environment '{env}' not found in watch.json")
    return env_config


@router.get("/environments/{env}/history/stats")
def history_stats(env: str):
    _require_env(env)
    db_path = get_db_path(settings.sqlite_data_dir, env)
    if not db_path.exists():
        return {"environment": env, "db_size_mb": 0, "counts": {}, "oldest_event": None, "newest_event": None}

    size_mb = round(db_path.stat().st_size / (1024 * 1024), 3)
    with get_connection(db_path) as conn:
        counts = {
            "poll_runs": conn.execute("SELECT COUNT(*) FROM poll_runs").fetchone()[0],
            "row_snapshots": conn.execute("SELECT COUNT(*) FROM row_snapshots").fetchone()[0],
            "change_events": conn.execute("SELECT COUNT(*) FROM change_events").fetchone()[0],
            "rollback_events": conn.execute("SELECT COUNT(*) FROM rollback_events").fetchone()[0],
        }
        oldest = conn.execute("SELECT MIN(detected_at) FROM change_events").fetchone()[0]
        newest = conn.execute("SELECT MAX(detected_at) FROM change_events").fetchone()[0]

    return {
        "environment": env,
        "db_size_mb": size_mb,
        "counts": counts,
        "oldest_event": oldest,
        "newest_event": newest,
    }


@router.delete("/environments/{env}/history")
def purge_by_age(env: str, older_than_days: int = Query(..., gt=0)):
    env_config = _require_env(env)
    env_config.retention.max_days = older_than_days
    RetentionManager(settings.sqlite_data_dir).enforce(env_config)
    return {"message": f"Purged records older than {older_than_days} days for environment '{env}'"}


@router.delete("/environments/{env}/history/all")
def purge_all(env: str):
    _require_env(env)
    RetentionManager(settings.sqlite_data_dir).purge_all(env)
    return {"message": f"All history purged for environment '{env}'"}
