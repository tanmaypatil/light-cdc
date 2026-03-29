# light-cdc Architecture

## Overview

light-cdc is a Change Data Capture agent that monitors low-volume business tables in dev/qa environments, detects row-level changes at periodic intervals, and allows users to review and roll back individual changes.

---

## System Components

```
┌─────────────────────────────────────────────────────────────┐
│                        Browser                               │
│   Dashboard | Snapshots | Playground | History               │
│                    React + Vite UI                           │
└──────────────────────┬──────────────────────────────────────┘
                       │ HTTP /api/v1
┌──────────────────────▼──────────────────────────────────────┐
│                   FastAPI Backend                            │
│                                                              │
│  ┌────────────┐  ┌─────────────┐  ┌──────────────────────┐  │
│  │  Poller    │  │  REST API   │  │   Rollback Engine    │  │
│  │ APScheduler│  │  (routers)  │  │   (SQL generation)   │  │
│  └─────┬──────┘  └──────┬──────┘  └──────────┬───────────┘  │
│        │                │                     │              │
│  ┌─────▼────────────────▼─────────────────────▼───────────┐  │
│  │               Snapshot Store (SQLite)                   │  │
│  │   poll_runs | row_snapshots | change_events             │  │
│  │   rollback_events | table_poll_state                    │  │
│  └─────────────────────────────────────────────────────────┘  │
│        │                                                     │
│  ┌─────▼──────────────────────────────┐                      │
│  │         DAL (Base → Postgres/Oracle)│                      │
│  └─────┬──────────────────────────────┘                      │
└────────┼────────────────────────────────────────────────────┘
         │ psycopg2 / oracledb (future)
┌────────▼──────────────────────┐
│     Target Database           │
│  Postgres (PoC) / Oracle (prod)│
│  accounts, customers, rules,  │
│  memberships, ...             │
└───────────────────────────────┘
```

---

## Directory Structure

```
light-cdc/
├── watch.json                   # Primary config — environments, tables, PKs
├── docker-compose.yml           # Local dev orchestration
├── .env.example
├── backend/
│   └── app/
│       ├── main.py              # FastAPI entry point + lifespan (starts Poller)
│       ├── config.py            # Pydantic settings (data_dir, watch_config_path)
│       ├── models/
│       │   └── watch_config.py  # Pydantic models for watch.json
│       ├── api/                 # FastAPI routers
│       │   ├── environments.py
│       │   ├── poll_runs.py
│       │   ├── changes.py
│       │   ├── rollback.py
│       │   ├── history.py
│       │   └── playground.py
│       ├── core/
│       │   ├── poller.py        # APScheduler poll loop + strategy routing
│       │   ├── diff_engine.py   # Pure function row diff (no I/O)
│       │   ├── snapshot_store.py# SQLite read/write
│       │   ├── rollback_engine.py# SQL generation from before_data
│       │   └── retention_manager.py
│       ├── dal/
│       │   ├── base.py          # Abstract DAL + factory
│       │   ├── postgres_dal.py  # psycopg2 implementation
│       │   └── oracle_dal.py    # Stub — NotImplementedError with notes
│       └── db/
│           ├── sqlite_engine.py
│           └── migrations/      # Auto-applied in order on init_db()
├── ui/
│   └── src/
│       ├── api/client.ts        # Axios wrapper for all API calls
│       ├── pages/               # Dashboard, Snapshots, Playground, History
│       └── components/          # ChangeBadge, DiffViewer, RollbackModal, etc.
└── test-harness/
    ├── init_schema.sql          # Creates tables + updated_at trigger
    ├── seed.py                  # Truncates + bulk inserts from JSON
    ├── updater.py               # APScheduler: cycles 5 mutations every N seconds
    └── mutations.py             # 5 controlled mutations (INSERT/UPDATE/DELETE)
```

---

## Key Design Decisions

### watch.json is the single source of truth
All environments, tables, PKs, exclusions, and polling strategy config live here. The UI, poller, DAL, and playground all read from it. Adding a new environment or table requires only a watch.json change.

### DAL abstraction isolates all DB differences
`BaseDAL` defines the interface. `PostgresDAL` implements it. `OracleDAL` is a stub ready for implementation. The poller, diff engine, rollback engine, and API never import DB-specific code — they only call DAL methods. Switching to Oracle = implement `OracleDAL` + change `db_type` in watch.json.

### Diff engine is a pure function
`compute_diff(table, previous, current) → [ChangeEvent]` has no I/O, no side effects. Easy to unit test in isolation. SHA-256 row hashing enables O(1) per-row change detection before deserialising JSON.

### Large-table polling strategy (auto-selected per poll)
| Condition | Strategy |
|---|---|
| rows ≤ threshold | Full scan |
| rows > threshold + `updated_at_column` | Incremental fetch (`WHERE updated_at > last_poll`) |
| rows > threshold, no `updated_at_column` | Checksum gate (skip if unchanged) |

Delete sentinel: if row count drops, incremental path falls back to full scan automatically.

### Rollback is SQL-based with audit trail
`rollback_engine.py` generates ANSI SQL from `before_data` stored in `change_events`. The exact SQL executed is stored in `rollback_events` for audit. UPDATE→restore, INSERT→DELETE, DELETE→re-INSERT.

### Credentials via environment variables
`connection_env_var` in watch.json names the env var holding the connection URL. The app never holds credentials in code or config files. On AKS, secrets are injected by Azure Key Vault CSI driver — the app sees a plain env var either way.

---

## SQLite Schema

```
poll_runs          — one record per polling cycle (status, timing, counts)
row_snapshots      — full row state captured each poll (pk_value, row_data, row_hash)
change_events      — detected changes (INSERT/UPDATE/DELETE, before/after data, diff_columns)
rollback_events    — audit trail for rollbacks (exact SQL, status, timestamp)
table_poll_state   — per-table last_polled_at, last_checksum, last_row_count
```

One SQLite file per environment: `data/dev.db`, `data/qa.db`.

---

## Data Flow

### Poll cycle
```
Scheduler fires
  → fetch_row_count()
  → select strategy (full / incremental / checksum gate)
  → fetch rows from target DB via DAL
  → rows_to_snapshots() — hash each row
  → compute_diff() — compare to previous snapshots
  → write_snapshots() — persist current state
  → write_change_events() — persist detected changes
  → save_table_poll_state() — update last_polled_at / checksum / count
  → finish_poll_run() — mark success/error
  → retention_manager.enforce() — purge old data if needed
```

### Rollback
```
User clicks Rollback
  → POST /changes/{id}/rollback
  → load change_event (before_data, change_type)
  → rollback_engine.generate_sql() — ANSI SQL from before_data
  → dal.execute_dml() — run against target DB
  → write rollback_event (SQL, status, timestamp)
  → mark change_event.rolled_back = 1
  → trigger new poll — captures the rollback as a new change_event
```

---

## Deployment

### Local (docker-compose)
```
postgres → seed (exits) → updater (loops) → backend :8000
                                          → ui :5173 (or Vite dev server)
```

### AKS (target)
```
Azure Container Registry
  → backend Deployment (1 replica — SQLite is single-writer)
  → ui Deployment (nginx)
  → Azure Disk PVC for SQLite data volume
  → watch.json as ConfigMap
  → DB credentials from Azure Key Vault CSI driver
  → Kustomize overlays per namespace (dev / qa)
```

CI/CD: GitHub Actions — lint + test on PR, build + push ACR + kubectl apply on merge to main.

---

## Agentic Layer (planned — Phases 7–9)

Sits on top of CDC infrastructure. Uses Claude API (`claude-sonnet-4-6`).

| Phase | Capability |
|---|---|
| 7 | Change summarisation per poll run + risk scoring (LOW/MEDIUM/HIGH) |
| 8 | Rollback recommendations + natural language query |
| 9 | Autonomous rollback for pre-configured high-risk patterns (optional) |

Agent code will live in `backend/app/agent/`. No new infrastructure needed — runs against the same docker-compose stack locally.

---

## Testing Strategy

### Unit Tests

Scope: pure logic with no external dependencies.

| Module | What to test |
|---|---|
| `diff_engine.py` | INSERT/UPDATE/DELETE detection, hash comparison, column diff, empty tables, no changes |
| `rollback_engine.py` | SQL generation for each change type (UPDATE/INSERT/DELETE), composite PKs |
| `watch_config.py` | Valid and invalid watch.json parsing, defaults, missing fields |
| `retention_manager.py` | Age calculation, size threshold logic |

These tests need no database, no filesystem — just Python objects.

```
backend/tests/
├── test_diff_engine.py
├── test_rollback_engine.py
├── test_watch_config.py
└── test_retention_manager.py
```

Run with: `pytest backend/tests/`

### Integration Tests

Scope: DAL + real Postgres (CI uses a Postgres service container).

| What to test |
|---|
| `fetch_table` returns correct rows |
| `fetch_table_since` filters by updated_at correctly |
| `fetch_row_count` matches actual count |
| `fetch_table_checksum` changes when a row changes |
| `execute_dml` commits and rollback_engine SQL applies cleanly |
| Full poll cycle: seed → poll → assert change_events written to SQLite |

```
backend/tests/
└── integration/
    ├── test_postgres_dal.py
    └── test_poll_cycle.py
```

Run with: `pytest backend/tests/integration/` (requires `TEST_DATABASE_URL` env var)

### E2E Tests

Scope: full stack via the REST API. Runs against docker-compose.

Keep it simple — 5 scenarios:

| Scenario | Steps |
|---|---|
| Detect INSERT | Insert row via playground API → trigger poll → assert change_event with type=INSERT |
| Detect UPDATE | Update row → trigger poll → assert change_event with correct diff_columns |
| Detect DELETE | Delete row → trigger poll → assert change_event with type=DELETE |
| Rollback UPDATE | Roll back an UPDATE change_event → query DB → assert row reverted |
| Incremental strategy | Bulk insert to exceed threshold → update one row → poll → assert only 1 change |

```
backend/tests/
└── e2e/
    └── test_cdc_scenarios.py
```

Run with: `pytest backend/tests/e2e/` (requires full docker-compose stack running)

---

## What is NOT tested (intentionally)

- The UI — no component tests; the playground and dashboard are thin wrappers over the API
- OracleDAL — tested when Oracle Cloud instance is available
- Retention purge destructive paths — verified manually
