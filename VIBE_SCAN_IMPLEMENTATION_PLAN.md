# Vibe-Code Security Scan — Implementation Plan

## Overview

**Feature:** Add a "Security Scan" module to AI Incident Copilot that audits vibe-coded (AI-generated) projects for security malpractice, while preserving all existing incident/log/anomaly functionality.

**Goal:** Users submit a GitHub/GitLab repo URL of a vibe-coded project. The backend clones it, runs a heuristic rules engine + LLM deep-review, and produces a scored vulnerability report. Critical/high findings auto-create incidents in the existing pipeline.

**User-approved decisions:**
- Scope: **defensive code audit** of the user's own project (no live URL probing)
- Input: **GitHub/GitLab repo URL** (https clone)
- Engine: **heuristic regex rules + OpenAI LLM** (no external SAST tools in MVP)
- Integration: high/critical findings **auto-create incidents**

**Out of scope (MVP):** zip upload, paste input, live URL probing, Semgrep/Bandit integration, multi-tenant auth/RLS.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│  Frontend (Next.js 14)                                           │
│  /scans — ScanForm, ScanList, ScanDetail (React Query polling)   │
└──────────────────────────────────┬───────────────────────────────┘
                                   │ REST /api/v1/scans
┌──────────────────────────────────▼───────────────────────────────┐
│  FastAPI Backend                                                 │
│  routes/scans.py                                                 │
│    POST /scans           → BackgroundTasks                       │
│    GET  /scans           → list runs                             │
│    GET  /scans/{id}      → run + findings                        │
│    POST /scans/{id}/findings/{fid}/incident → promote finding    │
│  services/scanner.py                                             │
│    clone_repo() → file walker → rules engine → LLM deep-review   │
│    → ScanReport (score 0–100, findings, summary, repo stats)     │
│  services/incidents (reuse) — auto-create incidents on findings  │
└──────────────────────────────────┬───────────────────────────────┘
                                   │ asyncpg
┌──────────────────────────────────▼───────────────────────────────┐
│  Postgres (Supabase)                                             │
│  scan_runs, scan_findings (new)                                  │
│  logs, incidents, log_templates (existing, unchanged)            │
└──────────────────────────────────────────────────────────────────┘
```

---

## Backend Tasks

### Task B1 — Config (`backend/app/config.py`)
Add to `Settings`:

| Setting | Default | Purpose |
|---|---|---|
| `LLM_MODEL` | `gpt-4o-mini` | Chat model for deep-review phase |
| `SCAN_TMP_DIR` | `./.scan-tmp` | Temp clone location |
| `MAX_REPO_SIZE_MB` | `50` | Abort scan if clone exceeds size |
| `MAX_SCAN_FILES` | `2000` | File walker cap |
| `MAX_LLM_FILES` | `10` | Files sent to LLM deep-review |
| `MAX_LLM_FILE_CHARS` | `12000` | Per-file truncation for LLM |
| `SCAN_ALLOWED_HOSTS` | `github.com, gitlab.com, bitbucket.org` | Clone URL whitelist |

### Task B2 — Models (`backend/app/models.py`)
Append Pydantic models:

- `ScanCreate` — `repo_url: str`, `name: Optional[str]`
- `ScanFinding` — `id: UUID`, `scan_id: UUID`, `severity: Literal["critical","high","medium","low"]`, `category: str`, `rule_id: Optional[str]`, `file: str`, `line: Optional[int]`, `evidence: str`, `description: str`, `remediation: str`, `promoted_to_incident: bool = False`
- `ScanStatus` — `Literal["queued","running","completed","failed"]`
- `ScanRun` / `ScanResponse` — `id, repo_url, name, status, score: Optional[float], summary: Optional[str], error: Optional[str], total_files, findings: list[ScanFinding], created_at, updated_at`

Follow existing conventions: `field_validator` for enums, UUID ids, ISO timestamps.

### Task B3 — Database (`backend/app/database.py` + `DATABASE_SCHEMA.md`)
Extend `SCHEMA_SQL`:

```sql
CREATE TABLE IF NOT EXISTS scan_runs (
    id TEXT PRIMARY KEY,
    repo_url TEXT NOT NULL,
    name TEXT,
    status TEXT NOT NULL DEFAULT 'queued'
        CHECK (status IN ('queued','running','completed','failed')),
    score REAL,
    summary TEXT,
    error TEXT,
    total_files INTEGER DEFAULT 0,
    created_at TEXT DEFAULT NOW(),
    updated_at TEXT DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS scan_findings (
    id TEXT PRIMARY KEY,
    scan_id TEXT NOT NULL,
    severity TEXT NOT NULL
        CHECK (severity IN ('critical','high','medium','low')),
    category TEXT NOT NULL,
    rule_id TEXT,
    file TEXT NOT NULL,
    line INTEGER,
    evidence TEXT,
    description TEXT NOT NULL,
    remediation TEXT,
    promoted_to_incident BOOLEAN DEFAULT FALSE
);
```

Add to `JSON_COLUMNS`/`TIMESTAMP_COLUMNS` maps as needed. Add CRUD methods on `Database`:
- `insert_scan_run(repo_url, name) -> dict`
- `update_scan_status(scan_id, status, score=None, summary=None, error=None, total_files=None)`
- `get_scan_runs(limit=50, offset=0) -> list[dict]`
- `get_scan_run(scan_id) -> Optional[dict]`
- `get_scan_findings(scan_id) -> list[dict]`
- `insert_finding(finding: dict)`
- `mark_finding_promoted(finding_id)`

Register `scan_runs`, `scan_findings` in the `JSON_COLUMNS`/`TIMESTAMP_COLUMNS` dicts (findings has no JSON/timestamp columns; scan_runs has `created_at`, `updated_at`).

### Task B4 — Scanner service (`backend/app/services/scanner.py`) [core]

**Module layout:**

1. **`validate_repo_url(url) -> str`** (raises `ValueError`)
   - Require `https://` scheme only (reject `file://`, `ssh://`, `git://`, `ftp://`)
   - Host must be in `settings.SCAN_ALLOWED_HOSTS`
   - Reject URLs containing `@` (credential smuggling) or path traversal (`..`)
   - Reject URL-encoded / non-ASCII hosts to defeat bypass tricks

2. **`clone_repo(url, scan_id) -> Path`**
   - `git clone --depth 1 --single-branch <url> <tmp>/<scan_id>` via `subprocess.run`, `timeout=60`
   - `SCAN_TMP_DIR` must exist; cleanup via `finally`/`shutil.rmtree` at scan end
   - Reject if `du`-style size check > `MAX_REPO_SIZE_MB` (post-clone `du` or walk)

3. **`iter_source_files(repo_path) -> Iterator[Path]`**
   - `rglob("*")`, skip: `.git`, `node_modules`, `vendor`, `.venv`, `dist`, `build`, `__pycache__`, `*.min.js`, `*.lock`, `package-lock.json`, `yarn.lock`, binaries (null bytes), images, `*.map`
   - Include: `.py, .js, .ts, .tsx, .jsx, .html, .php, .rb, .go, .java, .cs, .env*, .json (package.json/config only), .yml, .yaml, .sql, Dockerfile`
   - Cap at `MAX_SCAN_FILES` and `MAX_REPO_SIZE_MB` total bytes

4. **Rules engine — `RULE` dataclass:**
   `rule_id, name, severity, category, extensions: set[str], pattern: re.Pattern, description, remediation`
   Scan each file line-by-line (line numbers captured). Rule table:

   | rule_id | Category | Severity | Detects |
   |---|---|---|---|
   | `SECRET_AWS_KEY` | Secrets | critical | `AKIA[0-9A-Z]{16}` |
   | `SECRET_OPENAI_KEY` | Secrets | critical | `sk-[A-Za-z0-9]{20,}` |
   | `SECRET_PRIVATE_KEY` | Secrets | critical | `-----BEGIN (RSA|OPENSSH|EC) PRIVATE KEY-----` |
   | `SECRET_GENERIC_API_KEY` | Secrets | high | `(api[_-]?key\|apikey\|secret\|token)\s*[=:]\s*['\"][^'\"]{16,}` |
   | `SECRET_DB_URL` | Secrets | high | connection strings w/ `user:pass@` (`postgres://`, `mysql://`, `mongodb+srv://`) |
   | `SECRET_ENV_COMMITTED` | Secrets | critical | `.env` / `.env.local` files tracked in repo |
   | `DANGER_EVAL` | Code | high | `eval(` / `exec(` / `shell_exec` / `os.system` / `subprocess.call` on variable |
   | `DANGER_CHILD_PROCESS` | Code | high | `child_process.exec(` / `.spawn(` on variable |
   | `DANGER_XSS_INNERHTML` | Code | high | `innerHTML\s*=` / `dangerouslySetInnerHTML` |
   | `DANGER_SQL_CONCAT` | Code | high | SQL keyword followed by string concat `+`/`f"`/f-string (`.sql`, `.py`, `.js`) |
   | `DANGER_UNSAFE_YAML` | Code | medium | `yaml.load(` without `Loader=` / `pickle.loads` |
   | `DANGER_TEMPLATE_ESCAPE_OFF` | Code | medium | `autoescape=False`, `mark_safe(` |
   | `CONFIG_CORS_CREDENTIALS` | Config | high | `allow_origins=["*"]` (or `['*']`) + `allow_credentials=True` |
   | `CONFIG_DEBUG_TRUE` | Config | medium | `debug=True` / `APP_DEBUG=true` / `NODE_ENV=development` hardcoded |
   | `CONFIG_HARDCODED_SECRET_KEY` | Config | high | `SECRET_KEY\s*=\s*['\"](changeme\|secret\|password)[\"']` |
   | `CONFIG_DEFAULT_CREDS` | Config | high | `admin/admin`, `root/root`, `password = "password"` patterns |

   Severity false-positive guardrails: value-based rules (AWS/OpenAI/private keys) = critical; context-free keywords marked high/medium.

5. **LLM deep-review — `llm_review(files: list[(path, snippet)]) -> list[dict]`**
   - Client: reuse `OpenAI` from `app.services.embeddings` pattern (`_get_client`)
   - Select up to `MAX_LLM_FILES` files: rank by rule hits, then size (smallest first for token economy)
   - Prompt: "You are a security auditor for AI-generated ('vibe-coded') web apps. Review the following files for OWASP Top 10 and security malpractice. Respond ONLY with JSON: `{"findings":[{"category","severity","file","line","description","remediation","evidence"}]}`."
   - `response_format={"type": "json_object"}`; timeout ~60s; wrap in try/except
   - Parse + validate JSON, clamp severity to allowed set, dedupe against rule findings by (file, line, category)
   - If `OPENAI_API_KEY` unset or call fails → **rules-only mode** (log warning, continue)

6. **Orchestrator — `run_scan(scan_id: str, repo_url: str) -> None`** (runs in background thread)
   ```
   validate url → update status=running → clone → walk files
   → rules engine → llm_review → merge findings → score
   → persist findings → auto-create incidents (critical/high)
   → status=completed (+score, summary, total_files) | status=failed (+error)
   ```
   - Score: `100 - Σ severity_weight × per_finding` (critical=25, high=15, medium=7, low=3), floor at 0
   - Summary: one line — `"N findings (C critical, H high, M medium, L low) across X files"` (+ repo name, files scanned)
   - All DB writes go through `db = await get_db()` — call from `asyncio.run` inside thread, or make `run_scan` async and drive via `BackgroundTasks` + `await` (preferred: async function, FastAPI BackgroundTasks supports async)
   - Always cleanup temp dir in `finally`

### Task B5 — Route (`backend/app/api/v1/routes/scans.py`)
Follow existing route style (`incidents.py`):

- `POST /scans` (201, `ScanCreate` → `ScanRun`) — validate URL **synchronously** (fail fast 400), insert `scan_runs` row (status=queued), schedule `background_tasks.add_task(run_scan, scan_id, repo_url)`, return run
- `GET /scans` — list runs with findings counts (`?limit=50&offset=0`)
- `GET /scans/{scan_id}` — run + findings (404 if missing)
- `POST /scans/{scan_id}/findings/{finding_id}/incident` — manual promote:
  - Load finding (404 if missing); insert incident with `title=f"[Scan] {finding.description[:100]}"`, `severity=finding.severity`, `description` = full finding detail, `affected_services=[scan name/repo]`, `metadata={"scan_id":..., "finding_id":..., "source": "vibe-scan", "file":..., "line":...}`; set `promoted_to_incident=True`
  - Guard: 409 if already promoted
- Register router in `main.py`: `app.include_router(scans.router, prefix=settings.API_V1_PREFIX, tags=["scans"])`

### Task B6 — Auto-incident creation
In `run_scan` completion path: for each finding with severity in `("critical","high")`, call the same incident-creation helper used by B5 (shared function `promote_finding_to_incident(db, finding, scan_run)` in `scanner.py` or route module) so auto + manual paths stay consistent. Mark finding `promoted_to_incident=True` in DB.

---

## Frontend Tasks

### Task F1 — Types & API (`frontend/src/lib/types.ts`, `api.ts`, `hooks.ts`)
Follow existing patterns (React Query via `@tanstack/react-query`):
- Types: `ScanRun`, `ScanFinding`, `ScanStatus` (mirror backend)
- API: `createScan(repoUrl)`, `getScans()`, `getScan(id)`, `promoteFinding(scanId, findingId)`
- Hooks: `useScans()` (refetchInterval 3000 when any run `running`/`queued`), `useScan(id)` (same polling), `useCreateScan()`, `usePromoteFinding()`

### Task F2 — Components (`frontend/src/components/scans/`)
- `ScanForm.tsx` — repo URL text input + submit; validates https + trusted host client-side; disabled while scanning; on success refetch list + navigate to detail
- `ScanList.tsx` — table of runs: name/repo, status badge (queued/running/completed/failed with color mapping), score (with color: >=80 success, >=50 warning, else danger), finding count, created_at, link to detail
- `ScanDetail.tsx` — header (repo, status, score, summary, files scanned), findings table: severity badge, category chip, `file:line` (mono), evidence (collapsed `<details>`), description, remediation, "Create incident" button (disabled when promoted → show "Promoted" badge)

### Task F3 — Page (`frontend/src/app/scans/page.tsx`)
- `"use client"`; layout mirrors `dashboard/page.tsx` (title + controls row, cards)
- Left column: ScanForm; Right: ScanList; selecting a run shows ScanDetail (client-side selected state, no separate route in MVP)
- Add a `ShieldCheck`-icon KPI/tile linking here on the dashboard (optional, small)

### Task F4 — Navigation (`frontend/src/components/layout/Sidebar.tsx`)
- Add `{ href: "/scans", label: "Security Scans", icon: Shield }` (from `lucide-react`), positioned after "Logs"

---

## API Contract Summary

| Method | Path | Request | Response |
|---|---|---|---|
| POST | `/api/v1/scans` | `{repo_url, name?}` | 201 `ScanRun` (queued) |
| GET | `/api/v1/scans` | `?limit&offset` | `[ScanRun]` (without findings) |
| GET | `/api/v1/scans/{id}` | — | `ScanRun` + `findings[]` |
| POST | `/api/v1/scans/{id}/findings/{fid}/incident` | — | 201 `Incident` (or 409) |

---

## Security & Safety Measures (feature itself)
- URL whitelist: https + `github.com`/`gitlab.com`/`bitbucket.org`, no `@`, no `..` — blocks local file exfiltration via `file://` or clone tricks
- Temp dir cleaned in `finally`; clone timeout 60s; size caps prevent disk exhaustion
- Evidence snippets truncated (≤200 chars) and secrets partially masked (`sk-****…`) before persisting
- No secrets ever written to logs; `LOG_LEVEL` respected
- LLM failures degrade to rules-only — scan never hard-fails on OpenAI outage
- Note in docs: tool audits the user's **own** projects (defensive). No scanning of third-party systems without authorization.

---

## Verification

### Unit tests (`backend/tests/`)
- `test_scanner_url_validation.py` — valid github/gitlab URLs pass; `file://`, `ssh://`, `http://`, unknown hosts, `@user:pass`, path traversal rejected
- `test_scanner_rules.py` — one fixture snippet per rule (positive + near-miss negative), assert rule_id/severity/line
- `test_scanner_score.py` — score math: no findings=100, single critical=75, floor at 0
- `test_scanner_llm_parse.py` — LLM JSON response parser (mock response strings incl. malformed → falls back gracefully)
- `test_scans_api.py` — POST creates queued run (mock background task), GET list/detail, promote finding → incident created + 409 on second promote

Run: `cd backend; .\venv\Scripts\Activate.ps1; pytest`

### Frontend
- `cd frontend; npm run lint; npm run build`

### End-to-end (manual)
1. Seed a vulnerable sample repo (or use a public vulnerable-by-design repo) with: AWS key, `eval()`, `innerHTML`, SQL concat, `CORS * + credentials`, committed `.env`
2. POST `/api/v1/scans` → poll `GET /scans/{id}` → confirm: findings present with correct lines, score computed, critical/high auto-created incidents visible on `/incidents` and dashboard
3. Verify temp dir removed after completion
4. Kill OpenAI key (set `OPENAI_API_KEY=""`) → rescan → confirm rules-only path still completes

---

## Suggested Task Order & Dependencies

```
B1 (config) ─┬─> B2 (models) ─> B3 (db) ─> B4 (scanner core) ─> B5 (routes) ─> B6 (auto-incident)
             └──────────────────────────────────────────────────────────┘
F1 (types/api/hooks) ─> F2 (components) ─> F3 (page) ─> F4 (sidebar)
```

- B4 is the critical path and the largest unit; stub `run_scan` with rules-only first, add LLM phase after
- B5/B6 depend on B3 (tables) and B4 (`run_scan` signature)
- F tasks are independent of B4 internals (only need API contract) and can be parallelized

## Deliverables Checklist
- [ ] `backend/app/services/scanner.py` (URL validation, clone, walker, rules, LLM, orchestrator)
- [ ] `backend/app/models.py` — Scan models
- [ ] `backend/app/database.py` — 2 tables + 7 CRUD methods
- [ ] `backend/app/api/v1/routes/scans.py` + `main.py` registration
- [ ] `backend/app/config.py` — 7 new settings
- [ ] `backend/tests/` — 5 test modules
- [ ] `frontend/src/app/scans/page.tsx` + 3 components
- [ ] `frontend/src/lib/{types,api,hooks}.ts` updates
- [ ] `frontend/src/components/layout/Sidebar.tsx` nav item
- [ ] `DATABASE_SCHEMA.md` — scan_runs/scan_findings docs
- [ ] `AGENTS.md` — feature blurb + new env vars
