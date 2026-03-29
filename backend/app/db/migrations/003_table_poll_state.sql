-- Per-table polling state: tracks last successful poll time and checksum
-- Used by the large-table optimisation (incremental fetch + checksum gate)
CREATE TABLE IF NOT EXISTS table_poll_state (
    table_name      TEXT PRIMARY KEY,
    last_polled_at  TEXT NOT NULL,   -- ISO-8601; used as 'since' for updated_at incremental fetch
    last_checksum   TEXT,            -- last known table checksum; NULL means no prior checksum
    last_row_count  INTEGER          -- last known row count; used for delete sentinel
);
