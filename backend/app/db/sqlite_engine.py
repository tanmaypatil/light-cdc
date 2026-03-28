from __future__ import annotations

import sqlite3
from pathlib import Path


def get_db_path(data_dir: str, env_name: str) -> Path:
    return Path(data_dir) / f"{env_name}.db"


def get_connection(db_path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(db_path: str | Path) -> None:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    migrations_dir = Path(__file__).parent / "migrations"
    with get_connection(db_path) as conn:
        for migration_file in sorted(migrations_dir.glob("*.sql")):
            sql = migration_file.read_text()
            conn.executescript(sql)
