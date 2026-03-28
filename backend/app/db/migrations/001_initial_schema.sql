-- Poll run tracking: one record per polling cycle
CREATE TABLE IF NOT EXISTS poll_runs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    environment   TEXT NOT NULL,
    started_at    TEXT NOT NULL,
    finished_at   TEXT,
    status        TEXT NOT NULL CHECK (status IN ('running', 'success', 'error')),
    error_message TEXT,
    tables_polled INTEGER DEFAULT 0,
    changes_found INTEGER DEFAULT 0
);

-- Full row snapshot captured during each poll
CREATE TABLE IF NOT EXISTS row_snapshots (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    poll_run_id INTEGER NOT NULL REFERENCES poll_runs(id),
    table_name  TEXT NOT NULL,
    pk_value    TEXT NOT NULL,  -- JSON dict: {"account_id": 1}
    row_data    TEXT NOT NULL,  -- JSON full row (exclude_columns already stripped)
    row_hash    TEXT NOT NULL,  -- SHA-256 of sorted row_data for fast diff
    captured_at TEXT NOT NULL
);

-- One record per detected change (insert / update / delete)
CREATE TABLE IF NOT EXISTS change_events (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    poll_run_id       INTEGER NOT NULL REFERENCES poll_runs(id),
    table_name        TEXT NOT NULL,
    pk_value          TEXT NOT NULL,
    change_type       TEXT NOT NULL CHECK (change_type IN ('INSERT', 'UPDATE', 'DELETE')),
    before_data       TEXT,           -- NULL for INSERT
    after_data        TEXT,           -- NULL for DELETE
    diff_columns      TEXT NOT NULL,  -- JSON array of column names that changed
    detected_at       TEXT NOT NULL,
    rolled_back       INTEGER NOT NULL DEFAULT 0,
    rollback_event_id INTEGER REFERENCES rollback_events(id)
);

-- Audit trail for rollback operations
CREATE TABLE IF NOT EXISTS rollback_events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    change_event_id INTEGER NOT NULL,
    table_name      TEXT NOT NULL,
    pk_value        TEXT NOT NULL,
    rollback_sql    TEXT NOT NULL,  -- exact SQL executed
    executed_at     TEXT NOT NULL,
    status          TEXT NOT NULL CHECK (status IN ('success', 'error')),
    error_message   TEXT
);
