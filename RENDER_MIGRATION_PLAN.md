# Render Migration Plan: SQLite → PostgreSQL

## Overview

Current: SQLite (`aiosqlite`, local file `data/app.db`)
Target:  Render Web Service (FastAPI) + Render Managed Postgres

No Supabase was ever used — the code is already using a custom `Database` class over SQLite. We replace the SQLite driver with `asyncpg` and deploy to Render.

---

## Files to Change

| File | Change |
|------|--------|
| `backend/requirements.txt` | Remove `aiosqlite`, add `asyncpg` |
| `backend/app/config.py` | Replace `DATABASE_PATH` with `DATABASE_URL` |
| `backend/app/database.py` | Rewrite internals from `aiosqlite` → `asyncpg` (schema, connection, queries) |
| `backend/Dockerfile` | Use `$PORT` env var instead of hardcoded `8000` |
| `backend/.env` | Switch from `DATABASE_PATH` to `DATABASE_URL` |
| `docker-compose.yml` | Add Postgres service for local dev |
| `backend/render.yaml` (new) | Render Blueprint defining Web Service + Postgres DB |

---

## Step-by-Step

### Step 1 — `requirements.txt`
- Remove line: `aiosqlite>=0.20.0`
- Add line: `asyncpg>=0.29.0`

### Step 2 — `config.py`
- `DATABASE_PATH: str = "data/app.db"` → `DATABASE_URL: str = ""`
- On Render, `DATABASE_URL` is auto-injected by the Postgres add-on.
- Locally, user sets it manually in `.env` or uses docker-compose.

### Step 3 — `database.py` (largest change)
- Replace `import aiosqlite` → `import asyncpg`
- Replace `aiosqlite.Connection` → `asyncpg.Pool` (pool-based)
- `__init__` takes `dsn: str` instead of `db_path: str`
- `connect()` creates a pool via `asyncpg.create_pool(dsn)`
- `close()` closes the pool
- Schema SQL changes for PostgreSQL compatibility:
  - `AUTOINCREMENT` → `SERIAL`
  - `datetime('now')` → `NOW()`
- All placeholders change: `?` → `$1, $2, ...` (asyncpg uses `$N`)
- `INSERT ... RETURNING *` replaces separate `get_by_id` call
- All query methods use `pool.fetch()` / `pool.fetchrow()` / `pool.execute()`

### Step 4 — `Dockerfile`
- Change `CMD` to read port from Render-injected env var:
  ```
  CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
  ```

### Step 5 — `docker-compose.yml`
- Add `db` service (Postgres 16) so local dev matches production.
- Backend `DATABASE_URL` points to `postgres://user:pass@db:5432/incidents`.
- Backend depends on `db`.

### Step 6 — `render.yaml`
- **type:** `web` service (build from `./backend`, start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`)
- **type:** `postgres` database (free tier, `DATABASE_URL` env auto-injected)

### Step 7 — Deploy
- Push to GitHub
- Connect repo to Render
- Render auto-detects `render.yaml`, creates Postgres DB + Web Service
- Web Service gets `DATABASE_URL` env var automatically
- On first request, schema auto-creates tables (same as current SQLite behavior)

---

## SQLite → PostgreSQL Schema Diffs

| SQLite | PostgreSQL |
|--------|------------|
| `id TEXT PRIMARY KEY` | `id TEXT PRIMARY KEY` (unchanged — we use UUIDs) |
| `INTEGER PRIMARY KEY AUTOINCREMENT` | `SERIAL PRIMARY KEY` |
| `datetime('now')` | `NOW()` |
| `?` placeholder | `$1, $2, ...` |
| `last_insert_rowid()` | `RETURNING *` |
| `CHECK` constraints | Same — both support |
| `TEXT` for JSON | Same — both support |

No data migration needed (no production data exists).

---

## Local Dev After Migration

```bash
# Start postgres + backend
docker-compose up --build

# Or run Postgres locally and set DATABASE_URL in .env:
# DATABASE_URL=postgres://postgres:postgres@localhost:5432/incidents
cd backend
uvicorn app.main:app --reload
```

---

## Files NOT Changing

- `backend/app/main.py` — lifespan, middleware, routers all stay
- `backend/app/models.py` — Pydantic models are DB-agnostic
- `backend/app/services/*.py` — parser, embeddings, anomaly are pure logic
- `backend/app/api/v1/routes/*.py` — route handlers call `get_db()` which stays same
- All frontend code

---

## Order of Implementation

1. `requirements.txt`
2. `config.py`
3. `database.py` (rewrite)
4. `Dockerfile`
5. `docker-compose.yml`
6. `.env`
7. `render.yaml`
8. Test locally with `docker-compose up --build`
9. Git init + push → deploy on Render
