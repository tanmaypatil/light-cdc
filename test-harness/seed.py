"""
One-time seed script. Runs at docker-compose startup via the 'seed' service.
Idempotent — truncates tables and re-inserts from JSON files each run.
"""
import json
import os
import time
from pathlib import Path

import psycopg2
import psycopg2.extras

DATABASE_URL = os.environ["DATABASE_URL"]
SEED_DIR = Path(__file__).parent / "seed_data"
SCHEMA_FILE = Path(__file__).parent / "init_schema.sql"

# Insertion order matters due to FK constraints
TABLES = ["accounts", "customers", "rules", "memberships"]


def wait_for_postgres(url: str, retries: int = 20, delay: float = 2.0) -> psycopg2.extensions.connection:
    for attempt in range(1, retries + 1):
        try:
            conn = psycopg2.connect(url)
            print(f"Connected to Postgres (attempt {attempt})")
            return conn
        except psycopg2.OperationalError as e:
            print(f"Waiting for Postgres... ({attempt}/{retries}): {e}")
            time.sleep(delay)
    raise RuntimeError("Could not connect to Postgres after retries")


def create_schema(conn):
    sql = SCHEMA_FILE.read_text()
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()
    print("Schema created / verified")


def seed_table(conn, table: str):
    data = json.loads((SEED_DIR / f"{table}.json").read_text())
    if not data:
        return

    with conn.cursor() as cur:
        # Truncate in reverse FK order to avoid constraint violations
        cur.execute(f'TRUNCATE TABLE "{table}" RESTART IDENTITY CASCADE')

        cols = list(data[0].keys())
        col_str = ", ".join(f'"{c}"' for c in cols)
        val_str = ", ".join(f"%({c})s" for c in cols)
        sql = f'INSERT INTO "{table}" ({col_str}) VALUES ({val_str})'
        psycopg2.extras.execute_batch(cur, sql, data)

    conn.commit()
    print(f"  {table}: {len(data)} rows inserted")


def main():
    conn = wait_for_postgres(DATABASE_URL)
    try:
        create_schema(conn)
        print("Seeding tables:")
        for table in TABLES:
            seed_table(conn, table)
        print("Seed complete.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
