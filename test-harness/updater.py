"""
APScheduler-based mutation runner for CDC testing.
Cycles through MUTATIONS list on a configurable interval.
"""
import logging
import os
import time

import psycopg2
from apscheduler.schedulers.blocking import BlockingScheduler

from mutations import MUTATIONS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s — %(message)s",
)
logger = logging.getLogger(__name__)

DATABASE_URL = os.environ["DATABASE_URL"]
INTERVAL_SECONDS = int(os.environ.get("UPDATE_INTERVAL_SECONDS", "120"))

# Mutable index — cycles through MUTATIONS indefinitely
_state = {"index": 0}


def wait_for_postgres(url: str, retries: int = 20, delay: float = 2.0):
    for attempt in range(1, retries + 1):
        try:
            conn = psycopg2.connect(url)
            conn.close()
            logger.info("Postgres is ready (attempt %d)", attempt)
            return
        except psycopg2.OperationalError:
            logger.info("Waiting for Postgres... (%d/%d)", attempt, retries)
            time.sleep(delay)
    raise RuntimeError("Could not connect to Postgres after retries")


def apply_next_mutation():
    mutation = MUTATIONS[_state["index"] % len(MUTATIONS)]
    _state["index"] += 1

    logger.info(
        "[mutation %d/%d] %s",
        mutation["id"],
        len(MUTATIONS),
        mutation["description"],
    )

    try:
        conn = psycopg2.connect(DATABASE_URL)
        with conn.cursor() as cur:
            cur.execute(mutation["sql"], mutation["params"])
        conn.commit()
        conn.close()
        logger.info("  Applied: %s %s params=%s", mutation["operation"], mutation["table"], mutation["params"])
    except Exception as e:
        logger.exception("  Failed to apply mutation %d: %s", mutation["id"], e)


def main():
    wait_for_postgres(DATABASE_URL)
    logger.info("Updater starting — interval=%ds, %d mutations in cycle", INTERVAL_SECONDS, len(MUTATIONS))

    scheduler = BlockingScheduler()
    # Fire immediately on start, then every INTERVAL_SECONDS
    scheduler.add_job(apply_next_mutation, id="mutation_job_initial")
    scheduler.add_job(
        apply_next_mutation,
        trigger="interval",
        seconds=INTERVAL_SECONDS,
        id="mutation_job",
    )

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Updater stopped")


if __name__ == "__main__":
    main()
