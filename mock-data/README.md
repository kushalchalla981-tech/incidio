# Incident Manager Mock Data

Realistic demo data for the Incident Manager, loaded through the real API so
timelines, severity, status, and dashboard KPIs all behave like production data.

## Files

| File                  | Purpose                                                        |
| --------------------- | -------------------------------------------------------------- |
| `incidents.seed.json` | 19 fictional incidents (full status x severity grid + edge cases) |
| `load_mock_data.py`   | Resets and seeds the database through the running backend API    |

## Dataset shape

- **Status x severity grid (16):** one incident for every combination of
  `open / investigating / resolved / closed` with `low / medium / high / critical`.
- **Edge cases (3):**
  - `Stale API keys in rotation` - an incident **open for ~90 days** (shows how the
    dashboard handles a very old, still-unresolved item).
  - `Background job crashed and recovered` - **no description** and
    **empty `affected_services`** (null-description rendering).
  - `Upload service disk full` - **resolved today** (drives the "Resolved Today" KPI).
- **Timelines:** created through staged `PATCH` calls, so the API records real
  `status_changed` events (`open -> investigating -> resolved -> closed`).
- **Dashboards:** with this set, KPIs render as Active 9, Critical 2,
  Resolved Today 6, spread across all severities/statuses.

## Prerequisites

1. PostgreSQL running (e.g. `docker-compose up -d` or local).
2. Backend running with `backend/.env` set (the loader reads `DATABASE_URL`
   from `backend/.env` for the reset step):
   ```bash
   cd backend
   uvicorn app.main:app --reload          # http://127.0.0.1:8000
   ```

## Load the data

Run from anywhere with the backend venv activated:

```bash
cd backend
../venv/bin/python ../mock-data/load_mock_data.py
# or from project root:
./backend/venv/bin/python mock-data/load_mock_data.py
```

The loader:
1. Truncates the `incidents` table (reset - safe to re-run anytime).
2. POSTs each incident via `POST /api/v1/incidents`.
3. PATCHes the status chain via `PATCH /api/v1/incidents/{id}`.
4. Verifies by listing `GET /api/v1/incidents`.

Options:

```bash
python mock-data/load_mock_data.py --no-reset     # don't truncate first
python mock-data/load_mock_data.py --base http://127.0.0.1:8000
python mock-data/load_mock_data.py --seed mock-data/incidents.seed.json
```

## Run the frontend

```bash
cd frontend
npm run start        # production build, http://localhost:3000
```

The frontend proxies `/api/*` to `http://localhost:8000` (see
`next.config.mjs`), so the browser never needs to reach the backend directly.

## Demo day checklist

- Re-run the loader **the same day as the demo/snapshots** so the "Resolved
  Today" KPI is correct (the API stamps `updated_at` with load time on PATCH).
- Open `/incidents/dashboard` first (KPI cards), then `/incidents` (filters),
  then a resolved and a closed incident detail page (timelines).
- Leave the backend and frontend servers running; take snapshots directly from
  `http://localhost:3000`.

## Verification

Behind the scenes, the loader prints a summary after seeding. You can also
check by hand:

```bash
curl -s http://localhost:8000/api/v1/incidents | python -m json.tool
```

Expected counts: `closed=4, investigating=4, open=5, resolved=6`
and severities `critical=4, high=5, low=5, medium=5` (19 total).