# AGENTS.md - AI Incident Copilot

## Project Overview
AI-powered incident management platform for small engineering teams. Automates log analysis, anomaly detection, semantic log search, incident tracking, and security scanning of public repositories.

**Tech Stack:** FastAPI (backend) + Next.js 14 (frontend) + PostgreSQL 16 via asyncpg

## Project Structure
```
C:\projectwa\workshop/
├── backend/                 # FastAPI Python backend
│   ├── app/                 # Application code
│   │   ├── api/v1/routes/   # health, logs, incidents, anomalies, search, scans
│   │   ├── services/        # parser (Drain3), anomaly (PyOD), embeddings, scanner
│   │   ├── config.py        # Settings (env-driven)
│   │   ├── database.py      # asyncpg pool + schema + CRUD
│   │   ├── main.py          # FastAPI app, lifespan, middleware
│   │   ├── middleware.py    # Security headers
│   │   └── models.py        # Pydantic models
│   ├── tests/               # pytest suite (159 tests, DB-free)
│   ├── .env                 # Environment variables (DO NOT COMMIT)
│   ├── .env.example         # Env template (committed)
│   ├── requirements.txt     # Python dependencies
│   └── Dockerfile
├── frontend/                # Next.js 14 frontend
│   ├── src/app/             # App router pages (/, /dashboard, /incidents, /incidents/[id], /logs, /scans, /analytics, /settings)
│   ├── src/components/      # layout/, dashboard/, scans/, ui/, shared/
│   ├── src/lib/             # api.ts, hooks.ts, types.ts
│   ├── package.json         # Node dependencies
│   └── tsconfig.json
├── .planning/               # Plans, research, SCAN-SUMMARY.md
├── docker-compose.yml       # PostgreSQL 16 + backend service
├── render.yaml              # Render Blueprint (backend + managed DB)
├── setup.ps1                # One-command setup script
└── quick-start.ps1          # Quick start reference
```

## Development Commands

### Backend
```powershell
cd backend
.\venv\Scripts\Activate.ps1
uvicorn app.main:app --reload          # Start dev server (port 8000)
python -m pytest -q                    # Run tests (159 tests, no DB required)
```

### Frontend
```powershell
cd frontend
npm run dev                             # Start dev server (port 3000)
npx tsc --noEmit                        # Typecheck
npm run lint                            # ESLint check
npm run build                           # Production build
```

There is no frontend JS test framework configured; typecheck + lint + build are the frontend validation commands.

### Database
```powershell
docker-compose up -d                    # Start PostgreSQL 16 (+ backend)
docker-compose down                     # Stop services
```

## Code Conventions

### Python (Backend)
- Follow PEP 8 style guide
- Use type hints for all function signatures
- Use Pydantic models for request/response validation
- Async/await for I/O operations
- Error handling with proper HTTP status codes

### TypeScript (Frontend)
- Strict TypeScript mode enabled
- Use functional components with React hooks
- Prefer server components unless interactivity needed
- Use Tailwind utility classes for styling
- File naming: kebab-case for files, PascalCase for components

## API Guidelines
- RESTful endpoints under `/api/v1/` (health under `/health`)
- Use HTTP methods correctly (GET, POST, PATCH)
- Return consistent JSON response format
- Document all endpoints with FastAPI docstrings

## Environment Variables
Required in `backend/.env` (see `backend/.env.example`):
- `DATABASE_URL` - PostgreSQL connection string
- `OPENAI_API_KEY` - OpenAI key (optional; scan/embeddings degrade without it)
- `ENVIRONMENT` - development/staging/production
- `LOG_LEVEL` - INFO/DEBUG/ERROR
- `CORS_ORIGINS` - comma-separated origins; default `*` (wildcard disables credentials)

Security Scan feature (optional — defaults fine):
- `LLM_MODEL` - LLM model for scan deep-review (default gpt-4o-mini)
- `SCAN_TMP_DIR` - temp dir for scan clones (default ./.scan-tmp)
- `MAX_REPO_SIZE_MB` - post-clone walk abort cap in MB (default 50)
- `MAX_SCAN_FILES` - walker abort cap on file count (default 2000)
- `MAX_LLM_FILES` - files sent to LLM per scan (default 10)
- `MAX_LLM_FILE_CHARS` - per-file truncation for LLM (default 12000)
- `MAX_LLM_INPUT_CHARS` - total LLM input budget; rules-only abort beyond (default 600000)
- `SCAN_ALLOWED_HOSTS` - exact-match host allowlist for repo URLs (default github.com,gitlab.com,bitbucket.org)
- `SCAN_MAX_CONCURRENT` - in-process scan semaphore (default 2)

## Security Scan Feature (implemented)
- Submit a public repo URL (https, allowlisted host) via `POST /api/v1/scans`
- 20 heuristic rules + optional OpenAI LLM deep-review (Structured Outputs)
- Scored report: 0-100 score, A-F grade, per-category sub-scores, summary
- Critical/high findings auto-create incidents (deduped across rescans)
- No OpenAI key / LLM failure → rules-only mode; scan never hard-fails
- Orphaned scans (queued/running at startup) are marked failed with "server restarted mid-scan"
- Details: `.planning/SCAN-SUMMARY.md`, `backend/app/services/scanner.py`

## Testing
- Backend: pytest in `backend/tests/` (159 tests; URL validation, rules engine, scoring, LLM parse, scans API, logs/search routes, security)
- Run from `backend/` with the venv active: `python -m pytest -q` (no PostgreSQL or OpenAI needed)
- Frontend: no test framework — validate with `npx tsc --noEmit`, `npm run lint`, `npm run build`

## Important Notes
- Never commit `.env` files or API keys
- Use the existing virtual environment in `backend/venv/`
- Database schema defined in `DATABASE_SCHEMA.md` (runtime schema created by `backend/app/database.py` on connect)
- Sample logs available in `sample-logs.txt` for testing
- The app has no authentication (documented limitation) — do not expose the API directly to the internet
- Production deployments behind an access layer; `render.yaml` provisions the managed PostgreSQL