from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler

from app.core.diff_engine import compute_diff, rows_to_snapshots
from app.core.retention_manager import RetentionManager
from app.core.snapshot_store import SnapshotStore
from app.dal.base import BaseDAL
from app.db.sqlite_engine import init_db, get_db_path
from app.models.watch_config import EnvironmentConfig, WatchConfig

logger = logging.getLogger(__name__)


class Poller:
    def __init__(self, watch_config: WatchConfig, data_dir: str) -> None:
        self._config = watch_config
        self._data_dir = data_dir
        self._retention = RetentionManager(data_dir)
        self._scheduler = BackgroundScheduler()

    def start(self) -> None:
        for env in self._config.environments:
            # Initialise SQLite DB for this environment
            db_path = get_db_path(self._data_dir, env.name)
            init_db(db_path)
            logger.info(
                "Registered poller for env '%s' every %ds", env.name, env.poll_interval_seconds
            )
            self._scheduler.add_job(
                self._poll_environment,
                trigger="interval",
                seconds=env.poll_interval_seconds,
                args=[env],
                id=f"poll_{env.name}",
                next_run_time=None,  # don't fire immediately on startup
                replace_existing=True,
            )
            # Run first poll immediately in a separate job so startup is non-blocking
            self._scheduler.add_job(
                self._poll_environment,
                args=[env],
                id=f"poll_{env.name}_initial",
                replace_existing=True,
            )

        self._scheduler.start()
        logger.info("Scheduler started with %d environment(s)", len(self._config.environments))

    def stop(self) -> None:
        self._scheduler.shutdown(wait=False)

    def trigger_now(self, env_name: str) -> None:
        env = self._config.get_environment(env_name)
        if not env:
            raise ValueError(f"Environment '{env_name}' not found in watch.json")
        self._scheduler.add_job(
            self._poll_environment,
            args=[env],
            id=f"poll_{env_name}_manual",
            replace_existing=True,
        )

    def _poll_environment(self, env: EnvironmentConfig) -> None:
        logger.info("Polling environment '%s'", env.name)
        store = SnapshotStore(self._data_dir, env.name)
        poll_run_id = store.start_poll_run()

        connection_url = os.environ.get(env.connection_env_var)
        if not connection_url:
            msg = f"Env var '{env.connection_env_var}' is not set"
            logger.error(msg)
            store.finish_poll_run(poll_run_id, 0, 0, error=msg)
            return

        dal: BaseDAL | None = None
        total_changes = 0
        tables_polled = 0

        try:
            dal = BaseDAL.from_config(env, connection_url)

            for table_cfg in env.enabled_tables():
                try:
                    events = self._poll_table(dal, store, poll_run_id, env, table_cfg)
                    total_changes += len(events)
                    tables_polled += 1
                except Exception as e:
                    logger.exception("Error polling table '%s': %s", table_cfg.table, e)

            store.finish_poll_run(poll_run_id, tables_polled, total_changes)
            self._retention.enforce(env)
            logger.info(
                "Poll complete: env=%s tables=%d changes=%d", env.name, tables_polled, total_changes
            )

        except Exception as e:
            logger.exception("Poll failed for env '%s': %s", env.name, e)
            store.finish_poll_run(poll_run_id, tables_polled, total_changes, error=str(e))
        finally:
            if dal:
                dal.close()

    def _poll_table(
        self,
        dal: BaseDAL,
        store: SnapshotStore,
        poll_run_id: int,
        env: EnvironmentConfig,
        table_cfg,
    ) -> list:
        from app.models.watch_config import TableConfig
        table_cfg: TableConfig

        threshold = table_cfg.large_table_threshold if table_cfg.large_table_threshold is not None \
            else env.large_table_threshold

        row_count = dal.fetch_row_count(table_cfg.schema_name, table_cfg.table)
        is_large = row_count > threshold
        poll_state = store.get_table_poll_state(table_cfg.table)
        now = datetime.now(timezone.utc).isoformat()

        # ----------------------------------------------------------------
        # Strategy selection
        # ----------------------------------------------------------------
        if not is_large:
            # Small table — full scan (original path)
            logger.debug("table=%s strategy=full_scan rows=%d", table_cfg.table, row_count)
            rows = dal.fetch_table(table_cfg.schema_name, table_cfg.table, table_cfg.exclude_columns)
            return self._diff_and_store(dal, store, poll_run_id, table_cfg, rows, now, row_count)

        if table_cfg.updated_at_column:
            # Large table with updated_at — incremental fetch
            since = poll_state["last_polled_at"] if poll_state else "1970-01-01T00:00:00+00:00"
            logger.debug("table=%s strategy=incremental since=%s rows=%d", table_cfg.table, since, row_count)

            changed_rows = dal.fetch_table_since(
                table_cfg.schema_name,
                table_cfg.table,
                table_cfg.exclude_columns,
                table_cfg.updated_at_column,
                since,
            )

            # Delete sentinel: if row count dropped, run a full scan to find deleted PKs
            last_count = poll_state["last_row_count"] if poll_state else None
            if last_count is not None and row_count < last_count:
                logger.info(
                    "table=%s row count dropped %d→%d, running full scan to detect deletes",
                    table_cfg.table, last_count, row_count,
                )
                all_rows = dal.fetch_table(table_cfg.schema_name, table_cfg.table, table_cfg.exclude_columns)
                return self._diff_and_store(dal, store, poll_run_id, table_cfg, all_rows, now, row_count)

            # No deletes detected — merge changed rows into previous snapshot
            events = self._apply_incremental(store, poll_run_id, table_cfg, changed_rows, now, row_count)
            store.save_table_poll_state(table_cfg.table, now, None, row_count)
            return events

        else:
            # Large table without updated_at — checksum gate
            current_checksum = dal.fetch_table_checksum(
                table_cfg.schema_name, table_cfg.table, table_cfg.primary_key
            )
            last_checksum = poll_state["last_checksum"] if poll_state else None

            if last_checksum is not None and current_checksum == last_checksum:
                logger.debug("table=%s strategy=checksum_gate SKIP (unchanged)", table_cfg.table)
                store.save_table_poll_state(table_cfg.table, now, current_checksum, row_count)
                return []

            logger.debug(
                "table=%s strategy=checksum_gate CHANGED checksum=%s→%s",
                table_cfg.table, last_checksum, current_checksum,
            )
            rows = dal.fetch_table(table_cfg.schema_name, table_cfg.table, table_cfg.exclude_columns)
            return self._diff_and_store(dal, store, poll_run_id, table_cfg, rows, now, row_count,
                                        checksum=current_checksum)

    def _diff_and_store(
        self,
        dal: BaseDAL,
        store: SnapshotStore,
        poll_run_id: int,
        table_cfg,
        rows: list[dict],
        now: str,
        row_count: int,
        checksum: str | None = None,
    ) -> list:
        current_snapshots = rows_to_snapshots(rows, table_cfg.primary_key)
        previous_snapshots = store.get_latest_snapshots(table_cfg.table)
        events = compute_diff(table_cfg.table, previous_snapshots, current_snapshots)
        store.write_snapshots(poll_run_id, table_cfg.table, current_snapshots)
        if events:
            store.write_change_events(poll_run_id, events)
            logger.info("env table=%s changes=%d", table_cfg.table, len(events))
        store.save_table_poll_state(table_cfg.table, now, checksum, row_count)
        return events

    def _apply_incremental(
        self,
        store: SnapshotStore,
        poll_run_id: int,
        table_cfg,
        changed_rows: list[dict],
        now: str,
        row_count: int,
    ) -> list:
        """Merge changed_rows into the previous snapshot and diff only those PKs."""
        if not changed_rows:
            return []

        previous_snapshots = store.get_latest_snapshots(table_cfg.table)
        prev_by_pk = {s.pk_value: s for s in previous_snapshots}

        new_snapshots = rows_to_snapshots(changed_rows, table_cfg.primary_key)
        for snap in new_snapshots:
            prev_by_pk[snap.pk_value] = snap

        merged = list(prev_by_pk.values())
        events = compute_diff(table_cfg.table, previous_snapshots, merged)
        store.write_snapshots(poll_run_id, table_cfg.table, merged)
        if events:
            store.write_change_events(poll_run_id, events)
            logger.info("table=%s incremental changes=%d", table_cfg.table, len(events))
        return events
