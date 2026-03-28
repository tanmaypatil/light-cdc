from __future__ import annotations

import logging
import os

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
                    rows = dal.fetch_table(
                        table_cfg.schema_name,
                        table_cfg.table,
                        table_cfg.exclude_columns,
                    )
                    current_snapshots = rows_to_snapshots(rows, table_cfg.primary_key)
                    previous_snapshots = store.get_latest_snapshots(table_cfg.table)

                    events = compute_diff(table_cfg.table, previous_snapshots, current_snapshots)

                    store.write_snapshots(poll_run_id, table_cfg.table, current_snapshots)
                    if events:
                        store.write_change_events(poll_run_id, events)
                        logger.info(
                            "env=%s table=%s changes=%d", env.name, table_cfg.table, len(events)
                        )

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
