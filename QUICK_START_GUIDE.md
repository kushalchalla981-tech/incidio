# AI Incident Copilot — Quick Start Guide

**Goal:** Get the project running locally in a few minutes: backend, frontend, and PostgreSQL.

---

## 📚 Key Documents

1. **README.md** — overview, architecture, deployment, security notes
2. **QUICK_START_GUIDE.md** — this file (fast setup reference)
3. **DATABASE_SCHEMA.md** — schema documentation
4. **AGENTS.md** — development commands and coding conventions

---

## 🛠️ Tech Stack at a Glance

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Frontend** | Next.js 14 + TypeScript + Tailwind | Dashboard, incidents, logs, security scans |
| **Backend** | FastAPI + Python 3.11+ | REST API, processing pipeline, scan engine |
| **Database** | PostgreSQL 16 (asyncpg) | Logs, incidents, scan runs/findings |
| **Log Parsing** | Drain3 | Extract templates from unstructured logs |
| **Anomaly Detection** | PyOD (Isolation Forest) | Detect unusual log windows |
| **Search** | OpenAI embeddings + cosine similarity | Semantic log search |
| **LLM** | OpenAI (Structured Outputs) | Scan deep-review (optional) |

---

## 🚀 Development Setup (5 Minutes)

### Prerequisites

- Python 3.11+ and Node.js 18+
- Git (required for the Security Scan feature)
- PostgreSQL 16 (via Docker Compose, or a managed instance)

### Step 1 — Database (optional for boot, required for real data)

```powershell
docker-compose up -d
# PostgreSQL at localhost:5432 — incidents/incidents/incidents
```

### Step 2 — Backend

> The environment file and dependency manifest live in `backend/` — do **not**
> copy anything from the repository root.

```powershell
cd backend

# Create and activate a virtual environment (backend/venv already exists)
python -m venv venv
.\venv\Scripts\Activate.ps1        # Windows
# source venv/bin/activate         # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Create backend/.env from the example in the same directory
Copy-Item .env.example .env        # Windows PowerShell
# cp .env.example .env             # macOS/Linux

# Required: set DATABASE_URL in backend/.env
# e.g. postgresql://incidents:incidents@localhost:5432/incidents
# Optional: set OPENAI_API_KEY for scan deep-review (rules-only otherwise)

# Start the API
uvicorn app.main:app --reload
```

- Backend API: http://localhost:8000
- API docs: http://localhost:8000/docs
- Health: http://localhost:8000/health

> Dev-mode startup does not require the database — it logs a warning and
> continues; `/health` reports `degraded` until PostgreSQL is reachable.

### Step 3 — Frontend

```powershell
cd frontend
npm install
npm run dev
```

- Frontend: http://localhost:3000
- The dev proxy rewrites `/api/*` → `http://localhost:8000/api/*`
  (see `frontend/next.config.mjs`)

### Access

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| API Docs | http://localhost:8000/docs |

---

## 🔍 Try It Out

```powershell
# 1. Upload sample logs (sample-logs.txt at the repo root)
curl -X POST http://localhost:8000/api/v1/logs/upload -F "file=@sample-logs.txt"

# 2. Detect anomalies
curl "http://localhost:8000/api/v1/anomalies/detect?window_minutes=5"

# 3. Run a security scan on a public repo
curl -X POST http://localhost:8000/api/v1/scans `
  -H "Content-Type: application/json" `
  -d '{"repo_url": "https://github.com/octocat/Hello-World"}'

# 4. Poll the scan until it completes
curl http://localhost:8000/api/v1/scans/<scan-id>

# 5. Or use the UI: open http://localhost:3000/scans and submit a URL
```

---

## 🧪 Running Tests / Validation

```powershell
# Backend — run from backend/ with the venv active
cd backend
.\venv\Scripts\Activate.ps1
python -m pytest -q          # 159 tests

# Frontend — run from frontend/
cd frontend
npx tsc --noEmit
npm run lint
npm run build
```

---

## ☁️ Production Deploy

- **Backend:** Render Blueprint — `render.yaml` at the repo root defines the
  backend service (`rootDir: backend`) and a managed PostgreSQL database.
- **Frontend:** Vercel (or any Node host) — import the repo root and set the
  Vercel project setting **Root Directory = `frontend`** (Vercel's
  `vercel.json` schema does not accept a `rootDirectory` key), then set the
  `BACKEND_URL` env var in Vercel to the deployed backend URL.

See **README.md → Production Deployment** for details.

---

## ⚠️ Common Pitfalls

| Problem | Solution |
|---------|----------|
| `cp .env.example .env` at repo root fails | The env example is `backend/.env.example` → `backend/.env` |
| Backend can't reach the database | Start `docker-compose up -d`, check `DATABASE_URL` in `backend/.env` |
| Scan fails with "git executable not found" | Install git and ensure it's on PATH |
| Scan rejects a URL | Only `https://` on `github.com` / `gitlab.com` / `bitbucket.org`, no credentials in URL |
| No OpenAI key | Scans still work — rules-only mode (`metadata.llm_status: "rules_only"`) |
| Scan stuck "running" forever | The server was likely restarted mid-scan; startup sweep marks it `failed` |

---

## 📈 Success Metrics (Targets)

| Metric | Target |
|--------|--------|
| **MTTD** (Mean Time to Detect) | <5 min |
| **MTTU** (Mean Time to Understand) | <10 min |
| **MTTR** (Mean Time to Resolve) | 50% reduction |
| **Scan Report** | scored 0–100 + letter grade + sub-scores |

---

## 🎉 You've Got This!

1. ✅ Start the database, backend, and frontend
2. ✅ Upload `sample-logs.txt` and view anomalies
3. ✅ Run a security scan and review the report
4. ✅ Good luck — and check **AGENTS.md** when you need conventions