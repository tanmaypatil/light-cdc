export interface Environment {
  name: string;
  db_type: string;
  poll_interval_seconds: number;
  tables: string[];
  last_poll: {
    started_at: string;
    status: string;
    changes_found: number;
  } | null;
}

export interface PollRun {
  id: number;
  environment: string;
  started_at: string;
  finished_at: string | null;
  status: "running" | "success" | "error";
  error_message: string | null;
  tables_polled: number;
  changes_found: number;
}

export interface ChangeEvent {
  id: number;
  poll_run_id: number;
  table_name: string;
  pk_value: string;
  change_type: "INSERT" | "UPDATE" | "DELETE";
  before_data: string | null;
  after_data: string | null;
  diff_columns: string;
  detected_at: string;
  rolled_back: number;
  rollback_event_id: number | null;
}

export interface RollbackEvent {
  id: number;
  change_event_id: number;
  table_name: string;
  pk_value: string;
  rollback_sql: string;
  executed_at: string;
  status: "success" | "error";
  error_message: string | null;
}

export interface HistoryStats {
  environment: string;
  db_size_mb: number;
  counts: {
    poll_runs: number;
    row_snapshots: number;
    change_events: number;
    rollback_events: number;
  };
  oldest_event: string | null;
  newest_event: string | null;
}

export interface PagedResponse<T> {
  data: T[];
  meta: {
    page: number;
    page_size: number;
    total: number;
    environment: string;
  };
}
