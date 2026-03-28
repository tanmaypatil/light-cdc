CREATE INDEX IF NOT EXISTS idx_row_snapshots_poll_run    ON row_snapshots(poll_run_id);
CREATE INDEX IF NOT EXISTS idx_row_snapshots_table_pk    ON row_snapshots(table_name, pk_value);
CREATE INDEX IF NOT EXISTS idx_change_events_poll_run    ON change_events(poll_run_id);
CREATE INDEX IF NOT EXISTS idx_change_events_table       ON change_events(table_name);
CREATE INDEX IF NOT EXISTS idx_change_events_detected_at ON change_events(detected_at);
CREATE INDEX IF NOT EXISTS idx_poll_runs_environment     ON poll_runs(environment);
CREATE INDEX IF NOT EXISTS idx_poll_runs_started_at      ON poll_runs(started_at);
