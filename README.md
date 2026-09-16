# 🚨 AI Incident Copilot

> **Intelligent incident management for small software teams**  
> Log analysis, anomaly detection, semantic search, and automated security scans

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Next.js 14](https://img.shields.io/badge/Next.js-14-black)](https://nextjs.org/)

---

## 🎯 What This Project Does

AI Incident Copilot is an incident-management platform for small engineering
teams:

- ✅ **Log ingestion & parsing** — upload log files; Drain3 extracts templates
- ✅ **Anomaly detection** — Isolation Forest (PyOD) over time windows finds
  error spikes and unusual patterns
- ✅ **Semantic log search** — OpenAI embeddings + cosine similarity
- ✅ **Incident tracking** — create, filter, update, and resolve incidents
- ✅ **Security Scan** — submit a GitHub/GitLab/Bitbucket repo URL and get a
  scored (0–100 + letter grade) vulnerability report from a rules engine plus
  an optional LLM deep-review

---

## 🧱 Architecture

```
Next.js frontend (:3000)  →  FastAPI backend (:8000)  →  PostgreSQL 16
   /dashboard /incidents        /api/v1/* routes              (asyncpg)
   /logs /scans /analytics      background scan jobs
```

- The frontend proxies `/api/*` to the backend via `next.config.mjs` rewrites
  (dev default: `http://localhost:8000`; point it at the deployed backend in
  production).
- The backend persists to PostgreSQL using **asyncpg** (schema auto-created at
  connect time — see `backend/app/database.py` and `DATABASE_SCHEMA.md`).
- Long-running security scans run as FastAPI background tasks with an
  in-process semaphore.

## 🛠️ Technology Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Frontend** | Next.js 14 (App Router), TypeScript, Tailwind CSS, React Query, recharts, lucide-react | UI |
| **Backend** | FastAPI, Python 3.11+ | REST API |
| **Database** | PostgreSQL 16 via asyncpg | Persistence (TEXT-id runtime schema) |
| **Log Parsing** | Drain3 | Log template extraction |
| **Anomaly Detection** | PyOD (Isolation Forest) | Unusual-window detection |
| **Embeddings / Search** | OpenAI `text-embedding-3-small` | Semantic log search |
| **LLM** | OpenAI (Structured Outputs, e.g. `gpt-4o-mini`) | Scan deep-review (optional) |

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- Git (for the Security Scan feature)
- PostgreSQL 16 (local via Docker Compose, or a managed instance)
- OpenAI API key (optional — the scanner runs in rules-only mode without it)

### 1. Backend (FastAPI)

```powershell
cd backend

# Create and activate a virtual environment (already present as backend/venv)
python -m venv venv
.\venv\Scripts\Activate.ps1        # Windows
# source venv/bin/activate         # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Copy and edit environment variables (example file lives in backend/)
Copy-Item .env.example .env        # Windows PowerShell
# cp .env.example .env             # macOS/Linux

# Start the API
uvicorn app.main:app --reload
```

- Backend API: http://localhost:8000
- Interactive docs: http://localhost:8000/docs
- Health check: http://localhost:8000/health

> The backend does **not** need a database to boot in development — startup
> logs a warning and continues, and `/health` reports `degraded` until the
> database is reachable. In production, startup fails fast without a database.

### 2. Frontend (Next.js)

```powershell
cd frontend
npm install
npm run dev
```

- Frontend: http://localhost:3000

### 3. Local Database

```powershell
docker-compose up -d
# PostgreSQL on localhost:5432 (user/password/db: incidents/incidents/incidents)
```

The backend reads `DATABASE_URL` from `backend/.env` (default expected value:
`postgresql://incidents:incidents@localhost:5432/incidents`).

### 4. Try It

```powershell
# Upload sample logs
curl -X POST http://localhost:8000/api/v1/logs/upload -F "file=@sample-logs.txt"

# Detect anomalies
curl "http://localhost:8000/api/v1/anomalies/detect?window_minutes=5"

# List incidents
curl http://localhost:8000/api/v1/incidents
```

---

## 🔒 Security Scan Feature

Submit a public repository URL; the backend clones it into a temp dir, runs a
20-rule heuristic engine, optionally performs an LLM deep-review, and produces
a scored report. Critical/high findings automatically create incidents.

### Allowed hosts
`github.com`, `gitlab.com`, `bitbucket.org` (exact match — configurable via
`SCAN_ALLOWED_HOSTS`). Only `https` URLs without embedded credentials are
accepted.

### Using the API

```powershell
# 1. Submit a scan (returns a queued run)
curl -X POST http://localhost:8000/api/v1/scans `
  -H "Content-Type: application/json" `
  -d '{"repo_url": "https://github.com/octocat/Hello-World"}'

# 2. Poll until status is "completed" or "failed"
curl http://localhost:8000/api/v1/scans/<scan-id>

# 3. Promote a finding to an incident (manual path; critical/high are auto)
curl -X POST http://localhost:8000/api/v1/scans/<scan-id>/findings/<finding-id>/incident
```

### What a completed scan contains
- `score` — 0–100 (100 = no findings; 4+ critical findings floor at 0)
- `grade` — A/B/C/D/F (A ≥90, B ≥75, C ≥50, D ≥25, F <25)
- `summary` — one-line finding count
- `metadata.sub_scores` — `secrets_score`, `code_score`, `config_score`
- `findings` — severity, category, `file:line`, masked evidence, description,
  remediation

### LLM behavior
- When `OPENAI_API_KEY` is set, up to `MAX_LLM_FILES` files are sent for
  deep-review using OpenAI Structured Outputs.
- When the key is missing/empty, or the LLM refuses/errors/exceeds budgets, the
  scan **degrades to rules-only mode** (`metadata.llm_status` = `rules_only`) —
  it never hard-fails.

### UI
The frontend `/scans` page (sidebar → "Security Scans") has a submit form, a
polled history list, and a detail view with findings, sub-scores, and a
promote-to-incident button.

---

## 📄 API Overview

| Group | Routes |
|-------|--------|
| Health | `GET /health` |
| Logs | `GET /api/v1/logs`, `POST /api/v1/logs/upload`, `POST /api/v1/logs/batch`, `GET /api/v1/logs/{id}` |
| Incidents | `POST /api/v1/incidents`, `GET /api/v1/incidents`, `GET/PATCH /api/v1/incidents/{id}` |
| Anomalies | `GET|POST /api/v1/anomalies/detect` |
| Search | `POST /api/v1/search`, `POST /api/v1/search/backfill` |
| Scans | `POST /api/v1/scans`, `GET /api/v1/scans`, `GET /api/v1/scans/{id}`, `POST /api/v1/scans/{id}/findings/{fid}/incident` |

Full interactive reference: http://localhost:8000/docs

---

## 🌐 Production Deployment

### Topology

Frontend and backend deploy as **separate services**.

```
Next.js (Vercel or any Node host)  →  FastAPI (Render)  →  PostgreSQL (managed)
        :3000                              :8000
```

### Backend — Render

`render.yaml` at the repo root defines a web service (`rootDir: backend`) plus
a managed PostgreSQL database:

1. Push the repository to GitHub and create a Render Blueprint from it.
2. Render provisions the database, sets `DATABASE_URL`, installs
   `backend/requirements.txt`, and starts
   `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
3. Set `ENVIRONMENT=production` (defaults to production in render.yaml).
4. Optionally set `OPENAI_API_KEY` for LLM deep-review.

> Note: production workers must not have short gunicorn-style timeouts — a scan
> can legitimately run longer than 30s. The render.yaml start command uses
> uvicorn directly (no timeout-kill).

### Frontend — Vercel (or any Node host)

The Next.js app lives in `frontend/`, so the Vercel project must be pointed at
that directory (Vercel's `vercel.json` schema rejects a `rootDirectory` key;
use the project setting instead):

1. Import the repository root.
2. In the Vercel project: **Settings → General → Root Directory = `frontend`**
   (framework auto-detects Next.js).
3. Add a `BACKEND_URL` environment variable in the Vercel project settings set
   to the deployed backend URL (e.g. `https://ai-incident-copilot.onrender.com`).
   `next.config.mjs` proxies `/api/*` and `/health` there; locally it defaults
   to `http://localhost:8000`.
4. Deploy.

> The backend is a long-running service (background scan tasks, in-process
> concurrency, startup sweep) — deploy it on Render (above), not on Vercel
> serverless functions.

### Required Environment Variables (backend/.env)

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `ENVIRONMENT` | No | `development` / `staging` / `production` (default `development`) |
| `LOG_LEVEL` | No | `INFO` / `DEBUG` / `ERROR` |
| `OPENAI_API_KEY` | No | LLM deep-review + embeddings; scanner degrades to rules-only without it |
| `CORS_ORIGINS` | No | Comma-separated origins; default `*` (credentials disabled while `*`) |

Scan feature knobs (all optional with defaults — see `backend/app/config.py`):
`LLM_MODEL`, `SCAN_TMP_DIR`, `MAX_REPO_SIZE_MB`, `MAX_SCAN_FILES`,
`MAX_LLM_FILES`, `MAX_LLM_FILE_CHARS`, `MAX_LLM_INPUT_CHARS`,
`SCAN_ALLOWED_HOSTS`, `SCAN_MAX_CONCURRENT`.

---

## 🔒 Security

### Authentication Status (known limitation)

The MVP has **no authentication**. This is documented, not accidental — the
application assumes a **trusted single-team environment** protected by the
surrounding infrastructure:

- The API must **not** be exposed directly to the public internet.
- Production deployments should sit behind a **VPN, SSO, or an
  OAuth2/OIDC reverse proxy**.
- Authentication/authorization and rate limiting are future roadmap items.

### Hardening Already In Place

- **Security headers** on every response: `X-Content-Type-Options: nosniff`,
  `Referrer-Policy: strict-origin-when-cross-origin`, `X-Frame-Options: DENY`.
- **CORS:** wildcard origins never allow credentials; set `CORS_ORIGINS` to
  explicit origins to enable credentialed requests (a production warning is
  logged when `*` is used with `ENVIRONMENT=production`).
- **Input bounds:** anomaly parameters validated (`window_minutes` 1–1440,
  `contamination` 0.01–0.5) → HTTP 422 out of range.
- **Startup resilience:** dev continues without a database (health reports
  disconnected); production fails fast with a clear error.
- **Scanner hardening:** https-only + host allowlist, credential-smuggling and
  path-traversal rejection, list-arg git clone with `--` separator,
  protocol.ext/file disabled, size/file-count caps, evidence truncation +
  masking, temp-dir cleanup in `finally` with retry.
- **Orphan recovery:** on startup, scans stuck in `queued`/`running` are marked
  `failed` with `server restarted mid-scan`.

---

## 🧪 Testing

```powershell
# Backend (159 tests) — run from backend/ with the venv active
cd backend
.\venv\Scripts\Activate.ps1
python -m pytest -q

# Frontend — typecheck, lint, build (no JS test framework configured yet)
cd frontend
npx tsc --noEmit
npm run lint
npm run build
```

---

## 📚 Documentation

- **[Quick Start Guide](QUICK_START_GUIDE.md)** — fast setup reference
- **[Database Schema](DATABASE_SCHEMA.md)** — schema documentation
- **[Architecture Notes](ARCHITECT.md)** — reference design for the UI
  (note: the implemented UI is light-themed; ARCHITECT.md documents the
  original dark-theme reference design)
- **[API Docs](http://localhost:8000/docs)** — interactive (when running)

---

## 🚧 Roadmap (Post-MVP)

- Authentication & authorization, rate limiting
- Real-time log streaming
- Slack/Discord integration
- Deployment webhook correlation
- Custom alert rules

---

## 🤝 Contributing

```powershell
# Backend
cd backend
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

See **AGENTS.md** for coding conventions and development commands.

---

## 🙏 Acknowledgments

Built with:
- [Drain3](https://github.com/logpai/Drain3) - Log parsing
- [PyOD](https://github.com/yzhao062/pyod) - Anomaly detection
- [FastAPI](https://fastapi.tiangolo.com/) - Backend framework
- [Next.js](https://nextjs.org/) - Frontend framework
- [PostgreSQL](https://www.postgresql.org/) - Database
