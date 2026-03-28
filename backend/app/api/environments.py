from __future__ import annotations

from fastapi import APIRouter

from app.config import settings
from app.db.sqlite_engine import get_connection, get_db_path
from app.models.watch_config import WatchConfig

router = APIRouter()


@router.get("/environments")
def list_environments():
    watch_config = WatchConfig.load(settings.watch_config_path)
    result = []
    for env in watch_config.environments:
        db_path = get_db_path(settings.sqlite_data_dir, env.name)
        last_poll = None
        if db_path.exists():
            with get_connection(db_path) as conn:
                row = conn.execute(
                    "SELECT started_at, status, changes_found FROM poll_runs "
                    "ORDER BY started_at DESC LIMIT 1"
                ).fetchone()
                if row:
                    last_poll = dict(row)
        result.append({
            "name": env.name,
            "db_type": env.db_type,
            "poll_interval_seconds": env.poll_interval_seconds,
            "tables": [t.table for t in env.enabled_tables()],
            "last_poll": last_poll,
        })
    return {"data": result}
