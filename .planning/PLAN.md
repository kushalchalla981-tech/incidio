---
phase: vibe-code-security-scan
plan: 01
type: execute
wave: 1
depends_on: []
files_modified: [backend/app/config.py, backend/requirements.txt, backend/app/models.py, backend/.env.example, .gitignore, AGENTS.md]
autonomous: true
requirements: [SCAN-01, SCAN-02, SCAN-03, SCAN-04]
user_setup:
  - service: OpenAI
    why: "LLM deep-review phase (optional — scan degrades to rules-only if key unset)"
    env_vars:
      - name: OPENAI_API_KEY
        source: "https://platform.openai.com/api-keys"
    notes: "Already present in backend/.env per AGENTS.md. Scan works without it (rules-only fallback)."
  - service: git
    why: "Repo cloning"
    notes: "git 2.54.0 verified on PATH. If missing in prod: clone stage fails with a clear 'git executable not found' error; all other features unaffected."
must_haves:
  truths:
    - "Config exposes all scan knobs (model, temp dir, caps, allowlist) with sane defaults"
    - "Scan request/response Pydantic models exist and validate severity/status enums"
    - "pytest + pytest-asyncio + httpx installable so the 5-module test suite can run"
    - "Scan temp clones are gitignored so disk usage stays visible and clean"
  artifacts:
    - path: "backend/app/config.py"
      provides: "9 new scan settings"
      contains: "LLM_MODEL"
    - path: "backend/app/models.py"
      provides: "ScanCreate, ScanFinding, ScanRun, ScanResponse"
      contains: "class ScanResponse"
    - path: "backend/requirements.txt"
      provides: "pytest, pytest-asyncio, httpx"
      contains: "pytest"
    - path: ".gitignore"
      provides: ".scan-tmp exclusion"
      contains: ".scan-tmp"
---

# Vibe-Code Security Scan — Phase Plan (supersedes VIBE_SCAN_IMPLEMENTATION_PLAN.md)

## 1. Phase Goal

Users submit a GitHub/GitLab repo URL of a vibe-coded (AI-generated) project; the backend **validates the URL safely**, **clones it**, runs a **heuristic regex rules engine + OpenAI LLM deep-review**, produces a **scored vulnerability report** (0-100 score + letter grade + per-category sub-scores), **auto-creates incidents** for critical/high findings, and **persists scan runs + findings to Postgres**. Frontend gets a `/scans` page with submit form, polled scan list, and findings detail with manual promote-to-incident. **Existing log/incident/anomaly features keep working.**

Verification targets: 5 pytest modules pass · `npm run lint` + `npm run build` pass · end-to-end scan of a sample repo works.

## 2. Source-Audit Coverage

| Source | Items | Covered By |
|---|---|---|
| GOAL | scored report, auto-incident, persistence, /scans page, regression-free | P7 (report/incidents), P2 (persist), P5 (page), E2E/regression checks |
| RESEARCH deltas (9) | regex fixes, clone hardening, tree-kill, Shape B + startup sweep, Structured Outputs, 3 new rules, grade+sub-scores, fn-form refetchInterval, incident dedupe | P4 (regex/clone/kill/rules/score), P6 (Shape B/sweep/LLM), P3 (refetchInterval), P6+P7 (dedupe) |
| REQ | SCAN-01..04 (backend pipeline, API, frontend, tests) | P1-P8 |
| CONTEXT decisions | defensive audit, GitHub/GitLab input, regex+LLM engine, auto-incident | throughout |

Excluded (documented, not gaps): zip upload, paste input, live URL probing, Semgrep/Bandit, multi-tenant auth/RLS, WebSockets/SSE, subdomain hosts (self-hosted GitLab) — all deferred per RESEARCH Open Questions / draft plan "Out of scope".

## 3. Dependency Graph & Waves

```
Wave 1 (parallel):
  P1 Backend foundations ───────────────────────────────┐
  P2 Database schema + CRUD ────────────────────────────┤
  P3 Frontend data layer (types/api/hooks) ─────────────┤ (contract fixed in §7)

Wave 2 (parallel):
  P4 Scanner core: validation + clone + walker + rules + score   (needs P1, P2)
  P5 Frontend UI: ScanForm/ScanList/ScanDetail/page/sidebar      (needs P3)

Wave 3:
  P6 Scanner orchestrator: LLM review + run_scan + promote + sweep
     (appends to scanner.py → same file as P4 → must run after)

Wave 4:
  P7 Routes + main.py wiring (needs P6)

Wave 5:
  P8 Tests: conftest + 5 modules (needs P7)
```

| Plan | Wave | Depends on | File ownership (no cross-plan overlap within a wave) |
|---|---|---|---|
| P1 | 1 | — | config.py, models.py, requirements.txt, .env.example, .gitignore, AGENTS.md |
| P2 | 1 | — | database.py, DATABASE_SCHEMA.md |
| P3 | 1 | — | types.ts, api.ts, hooks.ts |
| P4 | 2 | P1, P2 | services/scanner.py (part 1) |
| P5 | 2 | P3 | components/scans/*, app/scans/page.tsx, Sidebar.tsx |
| P6 | 3 | P4 | services/scanner.py (part 2) |
| P7 | 4 | P6 | routes/scans.py, main.py |
| P8 | 5 | P7 | tests/* (new dir), pytest.ini |

**Parallelization rule of thumb for the executor:** P1, P2, P3 are independent of each other and of everything else. P4 and P5 are independent of each other. P6 must wait for P4 (same file). P7 waits for P6. P8 waits for P7.

---

# Wave 1

## PLAN P1 — Backend Foundations (config, models, deps)

**Objective:** All backend scaffolding exists so every later plan compiles and runs: scan settings in config, scan Pydantic models, test dependencies in requirements, scan temp dir gitignored, env/docs updated.

**Purpose:** Every downstream plan (P2-P8) imports `settings` and the Scan models; missing deps would break `pytest` at P8. This is the shared foundation.

**Context:** `backend/app/config.py:5-17` (Settings class), `backend/app/models.py:47-93` (Incident triple pattern), `backend/requirements.txt` (14 lines, no pytest — verified venv has none), `.gitignore` (no .scan-tmp entry), `backend/.env.example` (5 vars), `AGENTS.md` "Environment Variables" section.

### Task 1.1: Add scan settings to config.py

**Files:** `backend/app/config.py` (modify)

**Goal:** 9 scan knobs with defaults; zero impact on existing settings.

**Action:**
- Append to `Settings` (after `CORS_ORIGINS`, config.py:11), following the existing field style (config.py:5-17):
  ```python
  LLM_MODEL: str = "gpt-4o-mini"          # per RESEARCH §4.2 — cost-sane MVP default; gpt-4.1-mini is the documented upgrade
  SCAN_TMP_DIR: str = "./.scan-tmp"        # per RESEARCH §1.4 — resolved to absolute path inside scanner (P4)
  MAX_REPO_SIZE_MB: int = 50               # post-clone walk abort cap (RESEARCH §1.3)
  MAX_SCAN_FILES: int = 2000               # walker abort cap (RESEARCH §1.3)
  MAX_LLM_FILES: int = 10                  # files sent to LLM (RESEARCH §4.3)
  MAX_LLM_FILE_CHARS: int = 12000          # per-file truncation (RESEARCH §4.3)
  MAX_LLM_INPUT_CHARS: int = 600000        # ≈150k token budget guard → rules-only abort (RESEARCH R12)
  SCAN_ALLOWED_HOSTS: list[str] = ["github.com", "gitlab.com", "bitbucket.org"]  # exact-match allowlist (RESEARCH §1.1)
  SCAN_MAX_CONCURRENT: int = 2             # in-process scan semaphore (RESEARCH §3.4)
  ```
- Do **not** reorder existing fields. Do **not** add `model_config` changes.
- Append to `backend/.env.example`: `LLM_MODEL=gpt-4o-mini`, `MAX_REPO_SIZE_MB=50`, `MAX_SCAN_FILES=2000`, `SCAN_ALLOWED_HOSTS=github.com,gitlab.com,bitbucket.org` (pydantic-settings v2 parses comma-separated lists).
- Append `.scan-tmp/` to root `.gitignore` (with the `# Local database` comment block area).
- Append to `AGENTS.md`: the 9 new env vars under Environment Variables (mark optional: "scan feature — defaults fine"), plus one line under Testing: `pytest` (from `backend/`, venv active).

**Verify:** `python -c "from app.config import settings; print(settings.LLM_MODEL, settings.SCAN_ALLOWED_HOSTS, settings.SCAN_MAX_CONCURRENT)"` prints `gpt-4o-mini ['github.com', 'gitlab.com', 'bitbucket.org'] 2`.

**Done:** Config imports cleanly; .env.example/.gitignore/AGENTS.md updated; existing settings unchanged (`settings.API_V1_PREFIX` still `/api/v1`).

### Task 1.2: Add test dependencies to requirements.txt

**Files:** `backend/requirements.txt` (modify)

**Goal:** The P8 test suite can run. Verified: pytest/pytest-asyncio are NOT installed (pip list confirmed) and NOT in requirements.txt; **httpx 0.28.1 IS already installed** — it is re-added to requirements.txt only for reproducibility (not a new dependency).

**Action:**
- Append:
  ```
  pytest>=8.0.0
  pytest-asyncio>=0.23.0
  httpx>=0.27.0
  ```
- `openai>=1.0.0` is already present (installed 2.43.0 — supports `client.beta.chat.completions.parse`, RESEARCH §4.1). Do not change it.
- Install into the existing venv: `cd backend; .\venv\Scripts\Activate.ps1; pip install -r requirements.txt`.

**Verify:** `python -m pytest --version` prints pytest ≥8; `python -c "import pytest_asyncio, httpx; print('ok')"`.

**Done:** Requirements install cleanly; venv imports pytest_asyncio and httpx.

### Task 1.3: Add Scan Pydantic models to models.py

**Files:** `backend/app/models.py` (modify — append after `HealthResponse`, line 154)

**Goal:** Request/response models matching the API contract (§7), following the Incident triple convention (models.py:47-93) and the draft plan's Literal-based enums (VIBE_SCAN_IMPLEMENTATION_PLAN.md:64-72).

**Action:** Append exactly:
```python
from typing import Literal  # extend existing typing import at models.py:3

ScanSeverity = Literal["critical", "high", "medium", "low"]
ScanStatus = Literal["queued", "running", "completed", "failed"]


class ScanCreate(BaseModel):
    repo_url: str = Field(..., max_length=2048)
    name: Optional[str] = Field(None, max_length=255)


class ScanFinding(BaseModel):
    id: UUID
    scan_id: UUID
    severity: ScanSeverity
    category: str                      # "secrets" | "code" | "config" | LLM category string
    rule_id: Optional[str] = None
    file: str
    line: Optional[int] = None
    evidence: str
    description: str
    remediation: Optional[str] = None
    promoted_to_incident: bool = False


class ScanRun(BaseModel):
    id: UUID
    repo_url: str
    name: Optional[str] = None
    status: ScanStatus
    score: Optional[float] = None
    grade: Optional[Literal["A", "B", "C", "D", "F"]] = None
    summary: Optional[str] = None
    error: Optional[str] = None
    total_files: int = 0
    metadata: dict = Field(default_factory=dict)
    finding_count: int = 0
    created_at: datetime
    updated_at: datetime


class ScanResponse(ScanRun):
    findings: list[ScanFinding] = Field(default_factory=list)
```
- Use `Field(default_factory=...)` for mutable defaults (Pydantic v2 rule) — do NOT use `= {}`/`= []`.
- `id: UUID` matches the existing convention (models.py:80-93); DB stores TEXT uuid strings which Pydantic coerces (runtime verified in incidents).

**Verify:** `python -c "from app.models import ScanCreate, ScanResponse, ScanFinding; s = ScanCreate(repo_url='https://github.com/a/b'); print(s); r = ScanResponse.model_validate({'id':'00000000-0000-0000-0000-000000000000','repo_url':'x','status':'queued','total_files':0,'metadata':{},'finding_count':0,'created_at':'2026-01-01T00:00:00','updated_at':'2026-01-01T00:00:00'})"` succeeds; `ScanCreate(repo_url='')` fails validation.

**Done:** Models import; enum coercion works; invalid status/severity rejected by Literal.

---

## PLAN P2 — Database: scan_runs + scan_findings

**Objective:** Two new tables matching runtime conventions (TEXT ids, TEXT timestamps, SCHEMA_SQL string, JSON_COLUMNS/TIMESTAMP_COLUMNS registration) + 8 CRUD methods + DATABASE_SCHEMA.md update.

**Purpose:** Scan runs and findings persist across server restarts so the frontend can poll; auto-incident dedupe needs `finding_has_incident`.

**Context:** `database.py` — SCHEMA_SQL (23-70), JSON_COLUMNS/TIMESTAMP_COLUMNS (11-21), `insert`/`insert_batch`/`get_by_id`/`update_by_id` (125-171), `update_embedding` (247-250) as specialized-write analog, `query_incidents` (270-293) as typed-query analog. DATABASE_SCHEMA.md table format (11-133). **Runtime schema uses TEXT not UUID/TIMESTAMPTZ** (PATTERNS.md:143, 369) — document runtime form.

### Task 2.1: Append scan tables to SCHEMA_SQL + register serialization maps

**Files:** `backend/app/database.py` (modify)

**Goal:** Tables exist at connect time (connect() executes SCHEMA_SQL, database.py:78-81).

**Action:**
- Append to `SCHEMA_SQL` (before the closing `"""` at database.py:70), exactly:
  ```sql
  CREATE TABLE IF NOT EXISTS scan_runs (
      id TEXT PRIMARY KEY,
      repo_url TEXT NOT NULL,
      name TEXT,
      status TEXT NOT NULL DEFAULT 'queued'
          CHECK (status IN ('queued','running','completed','failed')),
      score REAL,
      grade TEXT CHECK (grade IN ('A','B','C','D','F')),
      summary TEXT,
      error TEXT,
      total_files INTEGER DEFAULT 0,
      metadata TEXT DEFAULT '{}',
      created_at TEXT DEFAULT NOW(),
      updated_at TEXT DEFAULT NOW()
  );
  CREATE INDEX IF NOT EXISTS idx_scan_runs_status ON scan_runs(status);
  CREATE INDEX IF NOT EXISTS idx_scan_runs_created_at ON scan_runs(created_at DESC);

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
  CREATE INDEX IF NOT EXISTS idx_scan_findings_scan_id ON scan_findings(scan_id);
  ```
- Register maps (database.py:11-21):
  ```python
  JSON_COLUMNS: add  "scan_runs": {"metadata"},
  TIMESTAMP_COLUMNS: add  "scan_runs": {"created_at", "updated_at"},
  ```
  `scan_findings` gets **no** entries (per PATTERNS.md:159 — no JSON/timestamp columns; `promoted_to_incident` stays a bool; severity/scan_id stay strings).
- `grade` column stores the letter grade (P4 computes) so the list view shows it without parsing metadata.

**Verify:** Backend boots against Postgres: `docker-compose up -d`, then (venv active) run:
```powershell
$env:DATABASE_URL='postgresql://postgres:postgres@localhost:5432/postgres'
python -c "import asyncio; from app.database import Database; async def m():\n d=Database('postgresql://postgres:postgres@localhost:5432/postgres'); await d.connect(); r=await d.pool.fetchval(\"SELECT to_regclass('public.scan_runs')\"); print(r); await d.close()\nasyncio.run(m())"
```
prints `scan_runs`.

**Done:** Tables created on connect; maps registered; existing tables untouched (logs/incidents/log_templates DDL unchanged).

### Task 2.2: Add scan CRUD methods to Database class

**Files:** `backend/app/database.py` (modify — append methods before `_db` at line 296)

**Goal:** All read/write paths the scanner, routes, and tests need. Reuse generic `insert`/`insert_batch`/`get_by_id`/`update_by_id` for findings — only the following specialized methods are new:

**Action:**
```python
async def insert_scan_run(self, repo_url: str, name: Optional[str] = None) -> dict:
    return await self.insert("scan_runs", {"repo_url": repo_url, "name": name, "status": "queued"})

async def update_scan_status(self, scan_id: str, status: str, *, score=None, grade=None,
                             summary=None, error=None, total_files=None, metadata=None) -> None:
    # Build SET clause ONLY from provided kwargs (mirror the PATCH pattern at incidents.py:47-48,
    # and update_embedding's execute style at database.py:247-250).
    data = {"status": status, "updated_at": datetime.now(timezone.utc).isoformat()}
    if score is not None: data["score"] = score
    if grade is not None: data["grade"] = grade
    if summary is not None: data["summary"] = summary
    if error is not None: data["error"] = error
    if total_files is not None: data["total_files"] = total_files
    if metadata is not None: data["metadata"] = metadata          # dict → _serialize via JSON_COLUMNS
    await self.update_by_id("scan_runs", scan_id, data)           # note: update_by_id returns row; ignore

async def get_scan_runs(self, limit: int = 50, offset: int = 0) -> list[dict]:
    # Mirror query_incidents (database.py:270-293) but with a LEFT JOIN count:
    sql = ("SELECT s.*, COUNT(f.id)::int AS finding_count FROM scan_runs s "
           "LEFT JOIN scan_findings f ON f.scan_id = s.id "
           "GROUP BY s.id ORDER BY s.created_at DESC LIMIT $1 OFFSET $2")
    # fetch rows, deserialize each with table="scan_runs"; finding_count passes through untouched
    # (only registered columns are transformed by _deserialize)

async def get_scan_run(self, scan_id: str) -> Optional[dict]:
    return await self.get_by_id("scan_runs", scan_id)

async def get_scan_findings(self, scan_id: str) -> list[dict]:
    # SELECT * FROM scan_findings WHERE scan_id = $1 ORDER BY severity DESC, file ASC
    # (severity DESC orders critical first lexically: critical>high>medium>low)
    # deserialize with table="scan_findings"

async def mark_finding_promoted(self, finding_id: str) -> None:
    await self.pool.execute("UPDATE scan_findings SET promoted_to_incident = TRUE WHERE id = $1", finding_id)

async def finding_has_incident(self, finding_id: str) -> bool:
    # Dedupe guard (RESEARCH R7): incidents.metadata is TEXT JSON; use @> containment:
    row = await self.pool.fetchval(
        "SELECT id FROM incidents WHERE metadata::jsonb @> $1::jsonb LIMIT 1",
        json.dumps({"finding_id": finding_id}))
    return row is not None

async def active_scan_for_repo(self, repo_url: str) -> Optional[dict]:
    # Duplicate-submission guard (RESEARCH R8): 409 source for routes
    row = await self.pool.fetchrow(
        "SELECT * FROM scan_runs WHERE repo_url = $1 AND status IN ('queued','running') LIMIT 1",
        repo_url)
    return self._deserialize(dict(row), "scan_runs") if row else None
```
- Import `timezone` at top: `from datetime import datetime, timezone` (replace database.py:3).
- Note: `insert_batch("scan_findings", findings)` (exists, database.py:137-153) is the findings-persist path used by P6 — no new method needed for bulk insert.

**Verify:** `python -c "from app.database import Database; print([m for m in dir(Database) if not m.startswith('_')])"` includes all 8 new names.

**Done:** Methods exist with correct SQL; existing methods untouched.

### Task 2.3: Document scan tables in DATABASE_SCHEMA.md

**Files:** `DATABASE_SCHEMA.md` (modify)

**Action:** Append sections `### 4. scan_runs` and `### 5. scan_findings` matching the existing format (DATABASE_SCHEMA.md:11-133): one-line purpose, SQL block, Column Descriptions bullets, Relationships, Sample Data. **Document the RUNTIME form** (TEXT ids, TEXT timestamps, metadata TEXT JSON) — add a note: "Runtime schema (database.py SCHEMA_SQL) uses TEXT ids/timestamps; shown here as implemented." Include the grade CHECK and the finding-count join in Query Examples.

**Verify:** File contains `### 4. scan_runs` and `### 5. scan_findings` headings.

**Done:** Doc updated; relationships note: `scan_findings.scan_id → scan_runs.id` (no FK constraint, consistent with existing loose coupling).

---

## PLAN P3 — Frontend Data Layer (types, api, hooks)

**Objective:** The API contract (§7) is consumed by typed client functions and React Query hooks with polling that stops on terminal status.

**Purpose:** P5 components depend on exactly these exports. Contract is frozen here — P7 implements the backend to match it.

**Context:** `types.ts` (interfaces mirror backend snake_case, `Record<string, unknown>` metadata — types.ts:48-62), `api.ts` (`fetchJSON` wrapper, URLSearchParams lists, POST/PATCH — api.ts:5-15, 45-70), `hooks.ts` (`useIncidents` polling 37-43, `useBackfill` mutation 31-35, conditional `enabled` 23-29).

### Task 3.1: Add scan types to types.ts

**Files:** `frontend/src/lib/types.ts` (modify — append after `IncidentFilters`, line 113)

**Action:** Mirror backend models (§7) exactly, snake_case, nullable as `| null`, timestamps as strings:
```typescript
export type ScanStatus = "queued" | "running" | "completed" | "failed";
export type ScanSeverity = "critical" | "high" | "medium" | "low";
export type ScanGrade = "A" | "B" | "C" | "D" | "F";

export interface ScanFinding {
  id: string;
  scan_id: string;
  severity: ScanSeverity;
  category: string;
  rule_id: string | null;
  file: string;
  line: number | null;
  evidence: string;
  description: string;
  remediation: string | null;
  promoted_to_incident: boolean;
}

export interface ScanRun {
  id: string;
  repo_url: string;
  name: string | null;
  status: ScanStatus;
  score: number | null;
  grade: ScanGrade | null;
  summary: string | null;
  error: string | null;
  total_files: number;
  metadata: Record<string, unknown>;   // sub-scores: {secrets_score, code_score, config_score, ...}
  finding_count: number;
  created_at: string;
  updated_at: string;
}

export interface ScanRunDetail extends ScanRun {
  findings: ScanFinding[];
}

export interface ScanFilters {
  limit?: number;
  offset?: number;
}
```

**Verify:** `npx tsc --noEmit` passes in `frontend/`.

**Done:** Types export cleanly, field-for-field with backend models.

### Task 3.2: Add scan API functions to api.ts

**Files:** `frontend/src/lib/api.ts` (modify)

**Action:** Append (copy `getIncidents`/`createIncident` shape — api.ts:45-70):
```typescript
export async function createScan(data: { repo_url: string; name?: string }): Promise<ScanRun> {
  return fetchJSON<ScanRun>("/api/v1/scans", { method: "POST", body: JSON.stringify(data) });
}
export async function getScans(filters?: ScanFilters): Promise<ScanRun[]> {
  const params = new URLSearchParams();
  if (filters?.limit) params.set("limit", String(filters.limit));
  if (filters?.offset) params.set("offset", String(filters.offset));
  const qs = params.toString();
  return fetchJSON<ScanRun[]>(`/api/v1/scans${qs ? `?${qs}` : ""}`);
}
export async function getScan(id: string): Promise<ScanRunDetail> {
  return fetchJSON<ScanRunDetail>(`/api/v1/scans/${id}`);
}
export async function promoteFinding(scanId: string, findingId: string): Promise<IncidentResponse> {
  return fetchJSON<IncidentResponse>(`/api/v1/scans/${scanId}/findings/${findingId}/incident`, { method: "POST" });
}
```
- Extend the type import on api.ts:1 with `IncidentResponse`, `ScanFilters`, `ScanRun`, `ScanRunDetail`.

**Verify:** `npx tsc --noEmit` passes.

**Done:** Four functions exported, paths match §7 contract exactly.

### Task 3.3: Add scan hooks to hooks.ts

**Files:** `frontend/src/lib/hooks.ts` (modify)

**Action:** Append. **Use function-form `refetchInterval`** (RESEARCH §7 — this is a mandatory delta; the plain-number form would poll forever):
```typescript
export function useScans(filters?: ScanFilters) {
  return useQuery({
    queryKey: ["scans", filters],
    queryFn: () => getScans(filters),
    refetchInterval: (query) =>
      query.state.data?.some((s) => s.status === "queued" || s.status === "running") ? 3000 : false,
  });
}

export function useScan(id: string) {
  return useQuery({
    queryKey: ["scan", id],
    queryFn: () => getScan(id),
    refetchInterval: (query) => {
      const st = query.state.data?.status;
      return st === "completed" || st === "failed" ? false : 3000;
    },
  });
}

export function useCreateScan() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: createScan,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["scans"] }),
  });
}

export function usePromoteFinding() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ scanId, findingId }: { scanId: string; findingId: string }) =>
      promoteFinding(scanId, findingId),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: ["scan", vars.scanId] });
      qc.invalidateQueries({ queryKey: ["scans"] });
      qc.invalidateQueries({ queryKey: ["incidents"] });
    },
  });
}
```
- Add imports: `useQueryClient` from `@tanstack/react-query` (hooks.ts:3), `createScan, getScan, getScans, promoteFinding` from `./api` (hooks.ts:4), `ScanFilters` type (hooks.ts:5).

**Verify:** `npx tsc --noEmit` passes; `npm run lint` passes.

**Done:** Polling auto-stops on `completed`/`failed`; mutations invalidate the right query keys (detail, list, and incidents after promote).

---

# Wave 2

## PLAN P4 — Scanner Core: URL validation, hardened clone, walker, rules engine, scoring

**Objective:** The deterministic half of the scanner — everything except LLM + orchestration. Pure module-level functions (PATTERNS.md:102-110 convention), testable without network or DB.

**Purpose:** This is the security-critical surface: SSRF/command-injection/disk-exhaustion controls all live here. All RESEARCH §1 and §2 deltas land in this plan.

**Context:** `services/anomaly.py` (helper + single entrypoint structure), `services/embeddings.py:12-16` (`_get_client` lazy singleton — the LLM client lands in P6 but the module skeleton belongs here). Config settings from P1. RESEARCH §1.1 (validation), §1.2 (clone), §1.3 (size caps), §2 (rule table).

### Task 4.1: URL validation + hardened git clone

**Files:** `backend/app/services/scanner.py` (new — part 1: this task)

**Goal:** `validate_repo_url` (fail-fast, synchronous) and `clone_repo` (list-args subprocess, never shell, tree-kill on Windows timeout).

**Action:** Create `backend/app/services/scanner.py` with:
- Imports: `os, re, shutil, subprocess, sys, asyncio, json, math, time, hashlib`, `from pathlib import Path`, `from typing import Optional`, `from urllib.parse import urlparse, unquote`, `from app.config import settings`.
- `SCAN_TMP = Path(settings.SCAN_TMP_DIR).resolve()` — absolute at import (RESEARCH §1.4). `ALLOWED_HOSTS = set(settings.SCAN_ALLOWED_HOSTS)`.
- **`validate_repo_url(url: str) -> str`** — implement verbatim the RESEARCH §1.1 logic (RESEARCH.md:36-54): strip; reject empty/>2048; reject leading `-` (arg injection, CVE-2017-1000117 class); `urlparse`; require `scheme == "https"` (rejects http/file/ssh/git/ftp/ext); reject `username`/`password` (credential smuggling); host = `(parsed.hostname or "").lower()` — urlparse already percent-decodes; reject trailing dot `host != host.rstrip(".")`; reject `host not in ALLOWED_HOSTS` (exact match — no subdomain wildcarding); reject `".." in unquote(parsed.path)` (path traversal — **use `unquote` from urllib.parse: urlparse does NOT percent-decode `%2e` in paths**, so literal-`..` checks alone accept `https://github.com/%2e%2e/repo`). Return the original stripped url.
- **`_run_git(args: list[str], timeout: int = 60) -> subprocess.CompletedProcess`** — the Windows-safe runner (RESEARCH.md:95-111): `subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)` (NEVER `PIPE` — pipe-drain deadlock bug bpo-43346); `proc.communicate(timeout=timeout)`; on `TimeoutExpired`: on win32 `subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)` (tree kill), else `proc.kill()`; `proc.wait(timeout=10)`; raise `TimeoutError(f"git clone timed out after {timeout}s")`. Return `CompletedProcess(args, returncode)`.
- **`clone_repo(url: str, scan_id: str) -> Path`** — command (RESEARCH.md:77-84), **flags BEFORE `clone`, list args, `--` separator**:
  ```python
  dest = SCAN_TMP / scan_id
  os.makedirs(SCAN_TMP, exist_ok=True)
  cmd = ["git", "-c", "protocol.ext.allow=never", "-c", "protocol.file.allow=never",
         "clone", "--depth", "1", "--single-branch", "--no-tags",
         "--no-recurse-submodules", "--", url, str(dest)]
  try:
      result = _run_git(cmd, timeout=60)
  except FileNotFoundError:
      raise ScanAbortError("git executable not found on PATH; install git to scan repos")
  if result.returncode != 0 or not (dest / ".git").exists():
      raise ScanAbortError(f"git clone failed (exit {result.returncode})")
  return dest
  ```
- Define **`class ScanAbortError(Exception)`** in this module (P6's run_scan catches it → status failed with the message). Also define the retry-cleanup helper now:
- **`_rmtree_retry(path: Path)`** — `shutil.rmtree` with 3 attempts, 0.5s sleep between, on `PermissionError` (Windows file locks from surviving git helpers, RESEARCH §1.3); after final failure `print`/log a loud warning — a leaked clone is disk-exhaustion risk, not security risk.

**Verify:**
```powershell
cd backend; .\venv\Scripts\Activate.ps1
python -c "from app.services.scanner import validate_repo_url; assert validate_repo_url('https://github.com/user/repo') == 'https://github.com/user/repo'; print('ok')"
python -c "from app.services.scanner import validate_repo_url; [validate_repo_url(u) for u in ['file:///etc/passwd','ssh://git@github.com/x','http://github.com/x','https://github.com.','https://user:pass@github.com/x','https://github.com.evil.com/x','https://github.com/../etc/passwd','-oProxyCommand=evil']]" 2>&1 | Select-String ValueError | Measure-Object | Select-Object -ExpandProperty Count  # expect 8
```

**Done:** All §1.1 edge cases enforced; clone command hardened; Windows timeout kills the process tree.

### Task 4.2: File walker + rules engine

**Files:** `backend/app/services/scanner.py` (continue — append)

**Goal:** `iter_source_files` (capped walker, no `du`) and the full gitleaks-verified rules table with correlation rules and entropy/blocklist gates.

**Action:**
1. **`iter_source_files(repo_path: Path)`** generator yielding `(Path relative_path, Path absolute_path)`:
   - `repo_path.rglob("*")`; skip any path with segment in `{".git", "node_modules", "vendor", ".venv", "dist", "build", "__pycache__"}`; skip `*.min.js`, `*.lock`, `package-lock.json`, `yarn.lock`, `*.map`, images (`*.png *.jpg *.jpeg *.gif *.ico *.svg *.woff* *.ttf *.eot`).
   - Include extensions: `.py .js .ts .tsx .jsx .html .php .rb .go .java .cs .json .yml .yaml .sql` + filename matches `.env`, `.env.*` + files named `Dockerfile`, `next.config.js`, `next.config.ts`, `config.js`, `config.ts`.
   - **Binary detection:** read first 8000 bytes, skip file if `b"\x00"` present (RESEARCH §2 note).
   - **Caps during walk** (RESEARCH §1.3): accumulate bytes (Python `os.scandir`/`stat` sums — NO `du`, absent on Windows). If total > `MAX_REPO_SIZE_MB * 1024 * 1024` → raise `ScanAbortError("repo exceeds MAX_REPO_SIZE_MB")`. If count > `MAX_SCAN_FILES` → raise `ScanAbortError("repo exceeds MAX_SCAN_FILES")`.
   - Per-file `try/except (FileNotFoundError, PermissionError, OSError)` → log and continue (Windows long-path, RESEARCH §1.4/R14).
2. **`RULE` dataclass** — fields: `rule_id, name, category, severity, extensions: Optional[set[str]], pattern: Optional[re.Pattern], patterns: list[re.Pattern] = field(default_factory=list), description, remediation` + a `handler: Optional[str]` (name of special-case function, `None` for plain line regex).
3. **`RULES: list[RULE]`** — the 20-rule table, patterns EXACTLY as follows (RESEARCH §2 — these replace the draft plan's wrong AWS/OpenAI patterns):

   | rule_id | category | severity | pattern(s) (Python re) | handler |
   |---|---|---|---|---|
   | `SECRET_AWS_KEY` | secrets | critical | `r"\b(?:AKIA\|ASIA\|ABIA\|ACCA)[A-Z2-7]{16}\b"` | `_skip_placeholder` (skip if evidence contains `EXAMPLE`/`XXXXXXXX`) |
   | `SECRET_OPENAI_KEY` | secrets | critical | `r"\bsk-(?:proj\|svcacct\|admin)-(?:[A-Za-z0-9_-]{74}\|[A-Za-z0-9_-]{58})T3BlbkFJ(?:[A-Za-z0-9_-]{74}\|[A-Za-z0-9_-]{58})\b"` AND `r"\bsk-[a-zA-Z0-9]{20}T3BlbkFJ[a-zA-Z0-9]{20}\b"` (both) | none |
   | `SECRET_GITHUB_TOKEN` | secrets | critical | `r"\b(?:ghp\|gho\|ghu\|ghs\|ghr)_[A-Za-z0-9]{36}\b"` AND `r"\bgithub_pat_[A-Za-z0-9_]{22,}\b"` | none |
   | `SECRET_PRIVATE_KEY` | secrets | critical | `r"-----BEGIN (?:RSA \|EC \|OPENSSH \|DSA \|PGP )?PRIVATE KEY(?: BLOCK)?-----"` | none |
   | `SECRET_GENERIC_API_KEY` | secrets | high | `r"(?:api[_-]?key\|apikey\|secret\|token)\s*[=:]\s*[\"']([^\"'\s]{16,})[\"']"` | `_entropy_gate` (Shannon ≥ 3.5 bits/char on group 1) |
   | `SECRET_DB_URL` | secrets | high | `r"(?:postgres(?:ql)?\|mysql\|mongo(?:db)?\+srv\|redis\|amqp)://[^\s:@/]+:[^\s:@/]+@"` | none |
   | `SECRET_ENV_COMMITTED` | secrets | critical | filename rule (no regex): relative path is `.env`, `.env.local`, `.env.production` (in repo root or any dir) | `_env_filename` — **never flag `.env.example`** |
   | `SECRET_ENV_NEXT_PUBLIC` | secrets | high | `r"NEXT_PUBLIC_[A-Z0-9_]*?(?:KEY\|SECRET\|TOKEN)\s*="` on `.env*` files + `next.config.*` | none |
   | `SECRET_STRIPE` | secrets | critical | `r"\bsk_live_[0-9a-zA-Z]{24}\b"` | none (`sk_test_` NOT matched → acceptable) |
   | `DANGER_EVAL` | code | high→medium | `r"\beval\(\|exec(\|shell_exec(\|os\.system(\|subprocess\.call(\|subprocess\.Popen("` | `_literal_or_variable` (arg matches `[a-z_]\w*` → high; literal string arg → medium) |
   | `DANGER_CHILD_PROCESS` | code | high→medium | `r"child_process\.(?:exec\|execSync\|spawn\|spawnSync)\("` | `_literal_or_variable` |
   | `DANGER_XSS_INNERHTML` | code | high | `r"innerHTML\s*=\|outerHTML\s*=\|dangerouslySetInnerHTML\|v-html="` | none |
   | `DANGER_SQL_CONCAT` | code | high | `r"(SELECT\|INSERT\|UPDATE\|DELETE\|WHERE)"` on a line AND a concat operator (`+`, `f"`, ` % `) on the same line or ±1 line | `_sql_concat` (severity high) |
   | `DANGER_UNSAFE_YAML` | code | medium | `r"yaml\.load(\|yaml\.unsafe_load(\|pickle\.loads("` | none (`yaml.safe_load` NOT flagged) |
   | `DANGER_TEMPLATE_ESCAPE_OFF` | code | medium | `r"autoescape\s*=\s*False\|mark_safe(\|raw="` | none |
   | `CONFIG_CORS_CREDENTIALS` | config | high→medium | `r"allow_origins\s*=\s*\[?[\"']\*[\"']\]?"` | `_cors_correlation`: `*` AND `allow_credentials\s*=\s*True` (same file) → **high**; `*` alone → **medium** |
   | `CONFIG_DEBUG_TRUE` | config | medium | `r"debug\s*=\s*True\|APP_DEBUG\s*=\s*true\|NODE_ENV\s*=\s*[\"']development[\"']"` | `_skip_test_paths` (skip files under `.github/`, `test*/`, `spec*/`) |
   | `CONFIG_HARDCODED_SECRET_KEY` | config | high→medium | `r"(?:SECRET_KEY\|JWT_SECRET\|signing_key\|SESSION_SECRET)\s*[=:]\s*[\"']([^\"']+)[\"']"` | `_secret_blocklist`: value lowercased in `{supersecretkey, supersecretjwt, secret, changeme, password, your-secret-key, change-me, replace_me}` → **high**; else entropy ≥ 3.5 → **medium** (RESEARCH §5 row 4 / RESEARCH.md:153) |
   | `CONFIG_DEFAULT_CREDS` | config | high→medium | two patterns: `r"(?:username\|user\|login)\s*[=:]\s*[\"']admin[\"']"` and `r"password\s*[=:]\s*[\"'](?:admin\|password\|123456)[\"']"` | `_creds_correlation`: both within 3 lines → **high**; username alone → **medium** |
   | `CONFIG_SUPABASE_NO_RLS` | config | high | repo-level correlation, no regex | `_supabase_correlation` (below) |

   - Extension scope: `secrets`/`code` rules → all included extensions; `CONFIG_*` → `.py .js .ts .tsx .jsx .yml .yaml .json .env*` (+ `next.config.*`); `DANGER_SQL_CONCAT` → `.py .sql .js .ts`.
   - Note: `|` inside patterns above is the regex alternation char — do not strip it when copying into code.
4. **Special handlers** (module functions): `_shannon_entropy(s) -> float` (standard Shannon over char counts, base 2, bits/char); `_mask_secret(s) -> str` (if starts with `sk-`/`ghp_`/`gho_`/`ghu_`/`ghs_`/`ghr_`/`github_pat_`/`AKIA`/`AKIA...`/`sk_live_` → `s[:4] + "****"` else `s[:3] + "****"`); `_truncate_evidence(s, 200)`; the correlation handlers from the table.
5. **`scan_repo(repo_path: Path) -> tuple[list[dict], list[tuple[str, int]], dict[str, str], int]`** — orchestrates walk + rules. **Signature frozen here** (P6 Task 6.2 depends on the exact 4-tuple; do not change):
   - Walk with `iter_source_files`; for each file read text lines (`errors="replace"`), `enumerate(lines, 1)` for line numbers.
   - Per-line rules: match → handler check (entropy/blocklist/literal) → finding dict: `{rule_id, severity, category, file (relative posix path), line, evidence (truncated+masked match line), description, remediation}`.
   - File-level correlation rules (`_cors_correlation`, `_creds_correlation`) after line pass, per file.
   - Collect `files_with_hits` (relative path strings + hit counts) for P6 LLM selection, and `texts: dict[str, str]` mapping relative path → file content **already truncated to `MAX_LLM_FILE_CHARS` during read** (bounds memory; P6's `select_llm_files` needs content without re-reading).
   - Repo-level: `_supabase_correlation(files, texts)` — if any `.js/.ts/.tsx/.jsx` file contains `createClient` AND (`supabase.co` or `SUPABASE_`) AND **no** `.sql` file anywhere contains `rowLevelSecurity` or `create policy` → one high finding on the createClient file (RESEARCH.md:160).
   - Return `(findings, files_with_hits, texts, total_bytes)`.

**Verify:**
```powershell
python -c "from app.services.scanner import RULES; print(len(RULES))"   # expect 20
python - <<'PY'   # if PowerShell heredoc fails, use a temp file tests/fixture probe
from app.services.scanner import RULES, scan_repo
from pathlib import Path
import tempfile
with tempfile.TemporaryDirectory() as d:
    p = Path(d)
    (p/"app.py").write_text('aws = "AKIA1234567890ABCDEF"\n')  # AKIA + 16 base32 chars
    (p/"app.py").write_text('x = "AKIA1234567890ABCDEF"\n')
    (p/"bad.py").write_text('import os\nos.system("ls")\nSECRET_KEY="supersecretkey"\n')
    (p/".env").write_text('NEXT_PUBLIC_API_KEY=sk-12345678901234567890\n')
    f, _, _, _ = scan_repo(p)
    for x in f: print(x["rule_id"], x["severity"], x["file"], x["line"])
PY
```
Expect `SECRET_AWS_KEY critical`, `DANGER_EVAL medium` (literal arg `os.system("ls")` → medium per `_literal_or_variable`; variable args → high), `CONFIG_HARDCODED_SECRET_KEY high`, `SECRET_ENV_NEXT_PUBLIC high`, `SECRET_ENV_COMMITTED critical`.

**Done:** All 20 rules fire on positive fixtures and stay silent on near-misses (verified by P8's fixture tests); walker enforces both caps.

### Task 4.3: Scoring math (weighted penalty + letter grade + sub-scores)

**Files:** `backend/app/services/scanner.py` (continue — append)

**Goal:** Pure, testable scoring per RESEARCH §6: `max(0, 100 - (crit×25 + high×15 + med×7 + low×3))`, letter grade, per-category sub-scores.

**Action:**
- **`SEVERITY_WEIGHTS = {"critical": 25, "high": 15, "medium": 7, "low": 3}`** (module constant).
- **`_letter_grade(score: float) -> str`** — `A` if ≥90, `B` ≥75, `C` ≥50, `D` ≥25, else `F` (RESEARCH.md:310 thresholds verbatim).
- **`_category_of(finding: dict) -> str`** — rule findings carry `category` in `{secrets, code, config}`; LLM findings (P6) map by keyword heuristic: category/description contains `secret|key|token|credential` → `secrets`; `cors|debug|config|header|secret-key` → `config`; else `code`.
- **`score_report(findings: list[dict]) -> dict`** returning `{"score": float, "grade": str, "sub_scores": {"secrets_score": float, "code_score": float, "config_score": float}, "counts": {"critical": n, "high": n, "medium": n, "low": n}}`:
  - `score = max(0, 100 - Σ weights)`; floor at 0 is intended (saturation — 4+ criticals floors to 0, RESEARCH §6 refinement 1).
  - Each `sub_scores[cat] = max(0, 100 - Σ weights of findings in that category)` — makes the number explainable (refinement 3).
  - Apply identical weights to LLM findings (refinement 4) — no special-casing by source.
- **`build_summary(scan_run, findings) -> str`** — one line per draft plan B4: `"{n} findings ({c} critical, {h} high, {m} medium, {l} low) across {files} files"`.

**Verify:**
```python
from app.services.scanner import score_report, _letter_grade
assert _letter_grade(90) == "A" and _letter_grade(75) == "B" and _letter_grade(50) == "C" and _letter_grade(25) == "D" and _letter_grade(24) == "F"
r = score_report([{"severity": "critical", "category": "secrets"}])
assert r["score"] == 75 and r["grade"] == "B" and r["sub_scores"]["secrets_score"] == 75 and r["sub_scores"]["code_score"] == 100
r = score_report([{"severity": "critical", "category": "secrets"}] * 4)
assert r["score"] == 0 and r["grade"] == "F"
print("score ok")
```

**Done:** Score/grade/sub-scores match the research-specified math, floor, and thresholds.

---

## PLAN P5 — Frontend UI: ScanForm, ScanList, ScanDetail, page, sidebar

**Objective:** The `/scans` page: submit form, polled list, findings detail with manual promote. Follows existing card/table/skeleton/badge conventions exactly.

**Purpose:** Users can trigger, watch, and act on scans. Uses P3's hooks — no new API surface.

**Context:** `RecentIncidents.tsx` (table pattern 44-76, severity/status variant maps 8-20), `incidents/page.tsx` (page skeleton 100-171, IncidentCard expandable 21-82, LoadingSkeleton arrays 157-160, empty state 161-165, status dot 35-41), `Topbar.tsx:33-40` (text input styling), `ui/Badge.tsx` variants, `ui/Card.tsx`, `ui/Button.tsx`, `Sidebar.tsx:11-17` (links array) + `:47` (active state), `shared/LoadingSkeleton.tsx`.

### Task 5.1: ScanForm + ScanList components

**Files:** `frontend/src/components/scans/ScanForm.tsx` (new), `frontend/src/components/scans/ScanList.tsx` (new)

**Goal:** URL submission with client-side validation; polled run list.

**Action — ScanForm.tsx:**
- `"use client"`; `useState` for `repoUrl`, `error`; `useCreateScan()` from `@/lib/hooks`.
- Input styled per Topbar (Topbar.tsx:33-40): `w-full py-2 px-4 border border-[var(--border)] rounded-[16px] bg-white/50 text-[13px] focus:border-accent focus:shadow-[0_0_0_3px_var(--accent-soft)]`.
- Client-side validation before submit (mirror of backend rules, user feedback only): must start `https://`, host in `["github.com","gitlab.com","bitbucket.org"]`, no `@`, no `..`; show inline `text-danger text-[12px]` error otherwise.
- Submit → `createScan.mutate({ repo_url: repoUrl }, { onSuccess: (scan) => { setRepoUrl(""); onCreated?.(scan); } })` — **the created run is delivered to the page via the per-call `onSuccess`** (a hook-level `onSuccess` only invalidates queries and does not expose the result); on error: show `error.message`.
- Button `variant="primary"` disabled while `isPending` or when input empty; label `Run Scan` with a `Shield` icon from lucide-react.
- Component props: `onCreated?: (scan: ScanRun) => void` so the page can select the new run for detail view.

**Action — ScanList.tsx:**
- `"use client"`; `useScans()` from `@/lib/hooks`.
- Table copied from RecentIncidents.tsx (44-76): mono uppercase header labels, `border-t border-[var(--border-soft)] hover:bg-[var(--accent-soft)]` rows, `transition-colors duration-[180ms]`.
- Columns: Repo (`scan.name || scan.repo_url`, mono truncated), Status (Badge variant map: queued→"info", running→"warn" (+ `animate-pulse`), completed→"success", failed→"danger"), Score (only when `completed`: color `>=80 → text-success`, `>=50 → text-warn`, else `text-danger`; show `—` otherwise), Grade badge (A/B→success, C→warn, D/F→danger), Findings (`finding_count`), Created (mono, `new Date(...).toLocaleString()`).
- Row click → `onSelect(scan)` prop; highlight selected row (`bg-[var(--accent-soft)]`).
- Loading: `Array.from({ length: 5 }).map((_, i) => <LoadingSkeleton key={i} className="h-12 w-full" />)`; empty: centered muted "No scans yet".

**Verify:** `cd frontend; npx tsc --noEmit; npm run lint`.

**Done:** Both components compile; no new dependencies; `onSelect`/`onCreated` props defined.

### Task 5.2: ScanDetail component

**Files:** `frontend/src/components/scans/ScanDetail.tsx` (new)

**Goal:** Findings list with severity badges, evidence, remediation, and manual promote-to-incident.

**Action:**
- `"use client"`; props `{ scanId: string }`; `useScan(scanId)` (polling stops on terminal — P3); `usePromoteFinding()`.
- Header card (Card component, `p-6`): repo_url (mono), status Badge, score (big, colored per 5.1 map) + grade Badge, summary line, `total_files` files, `created_at`.
- Sub-scores row: read `metadata` (`secrets_score`, `code_score`, `config_score` as `unknown` → `Number(...)`) — three small stat blocks: label uppercase mono `text-[11px] text-muted`, value `text-[15px] font-semibold` (show `—` if absent). This satisfies the per-category sub-score display.
- Findings list: `flex flex-col gap-4`. Each finding a Card (hover, `p-5`): header row — severity Badge (variant map per RecentIncidents.tsx:8-13), category chip (`font-mono text-[11px] text-muted uppercase`), `file:line` in `font-mono text-[13px]` (`file:line` shown as `line ?? "—"`), rule_id chip if present.
- Evidence in `<details>` (`<summary>Evidence</summary>` + `text-[12px] font-mono whitespace-pre-wrap break-all bg-[var(--border-soft)]/50 rounded-[10px] p-3`). **Render evidence as plain text only — never `dangerouslySetInnerHTML`** (XSS guard; findings may contain attacker-controlled strings).
- Description + remediation paragraphs (`text-[13px] text-[var(--fg-2)]`).
- Promote button: if `promoted_to_incident` → disabled Badge "Promoted" (success); else `Button variant="primary" size="sm"` "Create Incident" → `promoteFinding.mutate({ scanId, findingId })`; on error show `error.message` inline. Also show muted note for auto-created incidents: "Auto-promoted on scan completion" when `promoted_to_incident` is true and metadata indicates auto-source is not needed — simply rely on the Promoted badge.
- Loading: LoadingSkeleton `h-24 w-full` ×3. Failed scan: error card with `error` text.

**Verify:** `npx tsc --noEmit; npm run lint`.

**Done:** Detail view renders all report fields; promote flow wired to P3 hook; no dangerouslySetInnerHTML.

### Task 5.3: /scans page + sidebar link

**Files:** `frontend/src/app/scans/page.tsx` (new), `frontend/src/components/layout/Sidebar.tsx` (modify)

**Goal:** The page assembles form + list + detail; nav entry added.

**Action — page.tsx:**
- `"use client"`; skeleton per incidents/page.tsx (100-171): fragment, header row `flex items-center justify-between flex-wrap gap-4 mb-6` with `h1 className="text-gradient-anim text-[24px] font-semibold"` "Security Scans" + a live scan-count Badge (`queued/running` count, `variant="warn" animate-pulse` when >0).
- Layout: `grid grid-cols-1 lg:grid-cols-3 gap-6` — left column (col-span-1): ScanForm in a Card (`bg-[var(--surface)] ... rounded-[20px] p-6`); right (col-span-2): ScanList Card; below list: ScanDetail card when `selectedId` set (client-side `useState<string | null>`, no separate route — per draft F3).
- `onCreated={(scan) => setSelectedId(scan.id)}`; `onSelect={setSelectedId}`.
- Empty selected state: muted placeholder text "Select a scan to view findings".

**Action — Sidebar.tsx:**
- Add `Shield` to the lucide import (Sidebar.tsx:7-9) and insert after Logs (Sidebar.tsx:14): `{ href: "/scans", label: "Security Scans", icon: Shield },`. Active state logic (`pathname.startsWith`, line 47) works unchanged.

**Verify:** `npx tsc --noEmit; npm run lint; npm run build` (build requires backend? No — frontend-only, static analysis only; `/api/v1/scans` calls are client-side at runtime).

**Done:** Page renders; sidebar link appears after Logs; build passes.

---

# Wave 3

## PLAN P6 — Scanner Orchestrator: LLM deep-review, run_scan, promote, startup sweep

**Objective:** The async half: Structured Outputs LLM review with rules-only fallback, the `run_scan` background orchestrator (Shape B: async + `asyncio.to_thread`), shared promote helper with incident dedupe, and the orphaned-run sweep.

**Purpose:** Binds P4's pure logic to the DB and OpenAI. RESEARCH §3, §4 deltas land here. Appends to `backend/app/services/scanner.py` (same file as P4 → this plan runs after P4).

**Context:** `services/embeddings.py:12-16` (`_get_client` lazy singleton pattern), `services/parser.py:53-60` (try/except → graceful fallback — the rules-only precedent), `database.py` methods from P2, RESEARCH §4 (Structured Outputs via `client.beta.chat.completions.parse`, refusal/length handling), §3.2 (startup sweep), §3.4 (semaphore).

### Task 6.1: LLM deep-review with Structured Outputs

**Files:** `backend/app/services/scanner.py` (append)

**Goal:** `llm_review(snippets) -> list[dict]` returns validated findings or `[]` on ANY failure (rules-only degrade). Uses openai 2.43.0's Pydantic-integrated parse (RESEARCH.md:203-229).

**Action:**
```python
from openai import OpenAI
from pydantic import BaseModel

_llm_client: Optional[OpenAI] = None

def _get_llm_client() -> OpenAI:
    global _llm_client
    if _llm_client is None:
        _llm_client = OpenAI(api_key=settings.OPENAI_API_KEY, timeout=60.0)  # mirror embeddings.py:12-16; timeout per RESEARCH §4.1
    return _llm_client

class LLMFinding(BaseModel):
    category: str
    severity: Literal["critical", "high", "medium", "low"]   # enum via Literal (import from typing; add to imports)
    file: str
    line: Optional[int] = None
    description: str
    remediation: str
    evidence: str

class LLMReview(BaseModel):
    findings: list[LLMFinding] = Field(default_factory=list)
    summary: Optional[str] = None
```
- **`select_llm_files(scanned_files: list[tuple[str, int]], texts: dict[str, str]) -> list[tuple[str, str]]`** — files ranked by rule-hit count desc, then size asc (smallest first); strongly prefer including some zero-hit files (RESEARCH §4.3 — LLM adds most value on logic/auth flaws); cap `MAX_LLM_FILES`; each snippet = `"# path\n" + text[:MAX_LLM_FILE_CHARS]` with a `# path:line` header per RESEARCH; if `sum(len(s)) > MAX_LLM_INPUT_CHARS` → return fewer files (keep the highest-ranked; log). `scanned_files` items are `(relative_path_str, hit_count)` — matches the frozen `scan_repo` 4-tuple (P4 Task 4.2).
- **`llm_review(snippets: list[tuple[str, str]]) -> tuple[list[dict], str]`** returns `(findings, status)` where status ∈ `{"ok", "rules_only"}`:
  - If `not settings.OPENAI_API_KEY` or `not snippets` → return `([], "rules_only")`.
  - System prompt verbatim from RESEARCH.md:249-260 (security auditor for vibe-coded apps; OWASP Top 10; missing-control orientation per RESEARCH §5 context; "Report at most 20 findings. Prefer precision over recall."). No "respond with JSON" instruction (Structured Outputs removes it — RESEARCH §4.3).
  - `resp = _get_llm_client().beta.chat.completions.parse(model=settings.LLM_MODEL, messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": "\n\n".join(f"### {path}\n{snippet}" for path, snippet in snippets)}], response_format=LLMReview, max_tokens=4000)`
  - `if resp.choices[0].message.refusal: return ([], "rules_only")` (RESEARCH.md:226).
  - `parsed = resp.choices[0].message.parsed` → convert each `LLMFinding` to dict with `model_dump()`, set `category` per `_category_of` mapping (P4 Task 4.3) — actually keep LLM's category string but ALSO ensure `rule_id=None`; line/file carried through.
  - Wrap ENTIRE body in `try/except Exception: return ([], "rules_only")` (RESEARCH §4.1 — SDK retries 429/5xx; `finish_reason == "length"` raises LengthFinishReasonError in 2.43.0 → caught → rules-only). Log one warning line.

**Verify:**
```python
# no-key path — MUST clear the key first: backend/.env contains a valid key (AGENTS.md), so
# an unmodified assert would make a real API call and fail on dev machines.
import app.services.scanner as s
s.settings.OPENAI_API_KEY = ""          # environment-independent
assert s.llm_review([("a.py", "x")]) == ([], "rules_only")
print("llm fallback ok")
```

**Done:** LLM path uses Structured Outputs; every failure mode (no key, refusal, length, exception) returns `([], "rules_only")`.

### Task 6.2: run_scan orchestrator + promote helper + startup sweep

**Files:** `backend/app/services/scanner.py` (append)

**Goal:** The background job: status transitions, staged execution off the event loop, findings persist, auto-incidents with dedupe, cleanup in `finally`. Plus the shared promote function and `sweep_orphaned_scans` for lifespan.

**Action:**
1. **`promote_finding_to_incident(db, finding: dict, scan_run: dict) -> Optional[dict]`** — shared by auto (here) and manual (P7) paths:
   - Guard: `if await db.finding_has_incident(finding["id"]): return None` (RESEARCH R7 — dedupe, skip if incident with this finding_id exists).
   - Build incident dict: `title=f"[Scan] {finding['description'][:100]}"`, `severity=finding["severity"]`, `start_time=datetime.now(timezone.utc).isoformat()`, `description` = `category / rule_id / file:line / evidence / remediation` joined multi-line, `affected_services=[scan_run.get("name") or scan_run["repo_url"]]`, `metadata={"scan_id": scan_run["id"], "finding_id": finding["id"], "source": "vibe-scan", "file": finding["file"], "line": finding.get("line"), "rule_id": finding.get("rule_id")}`.
   - `incident = await db.insert("incidents", data)` then `await db.mark_finding_promoted(finding["id"])`; return incident. (`incidents.status` defaults to `open` via schema.)
2. **`async def run_scan(scan_id: str, repo_url: str) -> None`** — **Shape B** (RESEARCH.md:185-187 — mandatory delta; do NOT use `asyncio.run` in a thread):
   ```python
   _scan_semaphore = asyncio.Semaphore(settings.SCAN_MAX_CONCURRENT)   # module-level, RESEARCH §3.4

   async def run_scan(scan_id: str, repo_url: str) -> None:
       db = await get_db()
       async with _scan_semaphore:
           try:
               validate_repo_url(repo_url)                     # defensive re-check; route already validated
               await db.update_scan_status(scan_id, "running")
                repo_path = await asyncio.to_thread(clone_repo, repo_url, scan_id)   # blocking → thread
                try:
                    findings, scanned_files, texts_of_files, total_bytes = await asyncio.to_thread(scan_repo, repo_path)  # walk+rules → thread; 4-tuple (frozen in P4 Task 4.2)
                    # LLM phase:
                    llm_findings, llm_status = [], "skipped"
                    if scanned_files:
                        snippets = select_llm_files(scanned_files, texts_of_files)
                        llm_findings, llm_status = await asyncio.to_thread(llm_review, snippets)  # sync OpenAI client → thread
                    merged = merge_findings(findings, llm_findings)   # dedupe by (file, line, category) — LLM duplicates of rule findings dropped (RESEARCH §4.3)
                    report = score_report(merged)
                    # Deterministic finding ids (RESEARCH R7 / PLAN-CHECK W2): sha1 of repo_url|rule_id|file|line so
                    # finding_has_incident metadata containment fires ACROSS rescans (fresh uuid4 per scan would never match).
                    for f in merged:
                        f["id"] = hashlib.sha1(
                            f"{repo_url}|{f.get('rule_id')}|{f['file']}|{f.get('line')}".encode()
                        ).hexdigest()
                    await db.insert_batch("scan_findings", [dict(f, scan_id=scan_id) for f in merged])
                   # auto-incidents (critical/high) with dedupe guard:
                   for f in merged:
                       if f["severity"] in ("critical", "high"):
                           await promote_finding_to_incident(db, dict(f, scan_id=scan_id), scan_run_dict)
                   metadata = {"secrets_score": ..., "code_score": ..., "config_score": ...,
                               "rule_findings": len(findings), "llm_findings": len(llm_findings),
                               "llm_status": llm_status}
                   await db.update_scan_status(scan_id, "completed", score=report["score"],
                                               grade=report["grade"], summary=build_summary(...),
                                               total_files=len(scanned_files), metadata=metadata)
               finally:
                   await asyncio.to_thread(_rmtree_retry, repo_path)     # cleanup ALWAYS (RESEARCH §1.3)
           except ScanAbortError as e:
               await db.update_scan_status(scan_id, "failed", error=str(e))
           except Exception as e:                                          # never crash the task
               await db.update_scan_status(scan_id, "failed", error=f"scan failed: {e}")
   ```
   - **Note on texts:** `texts_of_files` comes from the frozen `scan_repo` 4-tuple (`(findings, scanned_files, texts, total_bytes)` — P4 Task 4.2 already returns it; content pre-truncated to `MAX_LLM_FILE_CHARS` during read). **Frozen coordination rule:** P4's `scan_repo` signature is `-> tuple[list[dict], list[tuple[str, int]], dict[str, str], int]` and is NOT negotiable here.
   - `merge_findings` — module function: keep rule findings in order; append LLM findings whose `(file, line, category)` doesn't collide with a rule finding (RESEARCH §4.3 post-processing).
   - Fetch `scan_run` dict once after `update_scan_status(scan_id, "running")` (`await db.get_scan_run(scan_id)`) for the promote helper's `scan_run` argument.
3. **`async def sweep_orphaned_scans(db) -> int`** — `UPDATE scan_runs SET status='failed', error='server restarted mid-scan', updated_at=<now> WHERE status IN ('queued','running')` via `db.pool.execute`; return `rowcount`. (RESEARCH §3.2 — mandatory delta.)

**Verify:**
```python
# signature check + sweep SQL shape
from app.services.scanner import run_scan, promote_finding_to_incident, sweep_orphaned_scans, merge_findings
import inspect
assert inspect.iscoroutinefunction(run_scan) and inspect.iscoroutinefunction(sweep_orphaned_scans)
m = merge_findings([{"file":"a","line":1,"category":"secrets"}], [{"file":"a","line":1,"category":"secrets"}])
assert len(m) == 1   # LLM duplicate dropped
print("orchestrator ok")
```

**Done:** run_scan is async, offloads blocking work, always cleans up, never crashes the process, marks failed on abort, dedupes LLM findings and incident promotion.

---

# Wave 4

## PLAN P7 — Routes + main.py wiring

**Objective:** The `/api/v1/scans` API surface (POST/GET/GET detail/promote) + router registration + lifespan sweep hookup.

**Purpose:** The contract §7 becomes real; frontend P3 hooks now have a backend.

**Context:** `routes/incidents.py` (full 54-line analog), `main.py:14-19` (lifespan), `main.py:37-41` (router registration).

### Task 7.1: routes/scans.py

**Files:** `backend/app/api/v1/routes/scans.py` (new)

**Action:** Follow incidents.py conventions exactly (module-level `router = APIRouter()`, `response_model` on decorator, `db = await get_db()`, try/except → 500 on writes):
```python
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from app.database import get_db
from app.models import IncidentResponse, ScanCreate, ScanResponse
from app.services.scanner import run_scan, promote_finding_to_incident, validate_repo_url

router = APIRouter()

@router.post("/scans", response_model=ScanResponse, status_code=201)
async def create_scan(scan: ScanCreate, background_tasks: BackgroundTasks):
    try:
        validate_repo_url(scan.repo_url)          # synchronous fail-fast → 400 (RESEARCH §3.5)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    db = await get_db()
    if await db.active_scan_for_repo(scan.repo_url):   # duplicate guard → 409 (RESEARCH R8)
        raise HTTPException(status_code=409, detail="A scan for this repo is already queued or running")
    run = await db.insert_scan_run(scan.repo_url, scan.name)
    background_tasks.add_task(run_scan, run["id"], scan.repo_url)   # async coroutine OK (RESEARCH §3.5)
    return run

@router.get("/scans", response_model=list[ScanResponse])
async def list_scans(limit: int = Query(50, ge=1, le=500), offset: int = Query(0, ge=0)):
    db = await get_db()
    return await db.get_scan_runs(limit=limit, offset=offset)

@router.get("/scans/{scan_id}", response_model=ScanResponse)
async def get_scan(scan_id: str):
    db = await get_db()
    run = await db.get_scan_run(scan_id)
    if not run:
        raise HTTPException(status_code=404, detail="Scan not found")
    run["findings"] = await db.get_scan_findings(scan_id)
    run["finding_count"] = len(run["findings"])
    return run

@router.post("/scans/{scan_id}/findings/{finding_id}/incident", response_model=IncidentResponse, status_code=201)
async def promote_finding(scan_id: str, finding_id: str):
    db = await get_db()
    scan = await db.get_scan_run(scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    finding = await db.get_by_id("scan_findings", finding_id)
    if not finding or finding.get("scan_id") != scan_id:
        raise HTTPException(status_code=404, detail="Finding not found")
    incident = await promote_finding_to_incident(db, finding, scan)
    if not incident:                                      # dedupe guard fired (R7)
        raise HTTPException(status_code=409, detail="Finding already promoted to an incident")
    return incident
```
- Note: `get_by_id` returns `Optional[dict]` with deserialized JSON columns — `scan_findings` has none registered, so `finding["scan_id"]` is a plain string. `finding.get("scan_id") != scan_id` string compare works.

**Verify:** `python -c "import app.api.v1.routes.scans as r; print([x.path for x in r.router.routes])"` shows the 4 paths; backend imports without DB connection.

**Done:** Contract §7 implemented; 400/404/409 semantics in place.

### Task 7.2: Register router + lifespan sweep in main.py

**Files:** `backend/app/main.py` (modify)

**Action:**
- Import: `from app.api.v1.routes import health, logs, incidents, anomalies, search, scans` (extend line 10) and `from app.services.scanner import sweep_orphaned_scans` (line 11 area).
- Registration after search (main.py:41): `app.include_router(scans.router, prefix=settings.API_V1_PREFIX, tags=["scans"])` — static frontend mount (43-44) stays last.
- Lifespan (main.py:14-19): after `get_db()`, add `await sweep_orphaned_scans(db)` — orphaned queued/running runs from a previous server lifetime become `failed` (RESEARCH §3.2, mandatory delta):
  ```python
  @asynccontextmanager
  async def lifespan(app: FastAPI):
      db = await get_db()
      await sweep_orphaned_scans(db)
      get_miner()
      yield
      await db.close()
  ```
- Verify existing routes still register: `python -c "from app.main import app; print(sorted({r.path for r in app.routes if hasattr(r,'path')}))"` includes `/api/v1/scans` and `/api/v1/incidents`, `/api/v1/logs`, `/api/v1/anomalies`, `/api/v1/search`.

**Done:** Router registered; sweep runs at startup; existing routes unchanged.

---

# Wave 5

## PLAN P8 — Test Suite (5 modules + conftest)

**Objective:** The 5 pytest modules from the draft plan + shared fixtures, with async support. `backend/tests/` does not exist — create it. pytest/pytest-asyncio/httpx installed via P1.

**Purpose:** Proves the phase goal's "pytest modules pass" verification target. Pure-logic modules (url, rules, score, llm-parse) need no DB; API module uses a FakeDatabase so it runs without Postgres.

**Context:** PATTERNS.md "Testing Patterns" (354-363): per-module functions, no pytest config file historically — **we add a minimal `pytest.ini`** for `asyncio_mode = auto` since P1 installs pytest-asyncio. AGENTS.md test command: `cd backend; .\venv\Scripts\Activate.ps1; pytest`.

### Task 8.1: conftest.py + pytest.ini

**Files:** `backend/tests/__init__.py` (new, empty), `backend/tests/conftest.py` (new), `backend/pytest.ini` (new)

**Goal:** Async mode auto-on; a FakeDatabase usable by API tests; DB-free test environment.

**Action — pytest.ini:**
```ini
[pytest]
asyncio_mode = auto
asyncio_default_fixture_loop_scope = function
testpaths = tests
```

**Action — conftest.py:**
- `FakeDatabase` class (dict-backed, in-memory) implementing the subset used by routes + scanner: `insert(table, data)` (assigns `id` if missing; stores `metadata` as dict; for `incidents` keeps `status="open"`), `insert_batch`, `get_by_id`, `update_by_id`, `insert_scan_run`, `update_scan_status`, `get_scan_runs`, `get_scan_run`, `get_scan_findings`, `mark_finding_promoted`, `finding_has_incident`, `active_scan_for_repo`. `findings` list keyed by scan_id; `finding_has_incident` scans stored incidents' `metadata["finding_id"]`.
- Fixture `fake_db` → `pytest.fixture` returning a fresh `FakeDatabase()` and `monkeypatch.setattr("app.api.v1.routes.scans.get_db", ...)` — **patch the routes module's imported symbol** (routes do `from app.database import get_db` at import time; patching `app.database.get_db` would not affect it).
- Fixture `client` → `fastapi.testclient.TestClient(app)` **without context manager** (`client = TestClient(app)`, not `with ...`) — avoids running lifespan (which would call real `get_db()`/sweep and fail on empty DATABASE_URL). This is the documented TestClient behavior: lifespan only runs inside the context manager.
- Fixture `fake_run_scan` → monkeypatches `app.api.v1.routes.scans.run_scan` with an `async def` stub that records `(scan_id, repo_url)` calls in a list (BackgroundTasks executes after response; the stub keeps tests instant and DB-free).

**Verify:** `python -m pytest --collect-only` collects 0 tests but imports conftest without error (error-free collection).

**Done:** Test scaffolding in place; no DB connection required to run the suite.

### Task 8.2: URL validation, rules engine, score, LLM-parse modules

**Files:** `backend/tests/test_scanner_url_validation.py`, `backend/tests/test_scanner_rules.py`, `backend/tests/test_scanner_score.py`, `backend/tests/test_scanner_llm_parse.py` (all new)

**Goal:** Deterministic unit coverage of P4 + P6 pure logic.

**Action — test_scanner_url_validation.py:** `pytest.mark.parametrize` table covering RESEARCH.md:59-69:
- pass: `https://github.com/user/repo`, `https://github.com/user/repo.git`, `https://gitlab.com/group/repo`, `https://bitbucket.org/user/repo`
- reject (assert `pytest.raises(ValueError)`): trailing dot `https://github.com.`, `https://github.com.evil.com/x`, embedded creds `https://user:pass@github.com/repo`, path traversal `https://github.com/../etc/passwd`, encoded traversal `https://github.com/%2e%2e/repo`, `file:///etc/passwd`, `ssh://git@github.com/x`, `http://github.com/x`, `git://github.com/x`, leading dash `-oProxyCommand=...`, empty string, 2049-char URL, unknown host `https://evil.com/x`.

**Action — test_scanner_rules.py:** fixture-pair style per PATTERNS.md:347 (positive + near-miss negative), using a temp dir + `scan_repo` (update unpack for the 4-tuple return):
- `SECRET_AWS_KEY`: pos `x = "AKIAIOSFODNN7EXAMPLE"` (16 base32 chars after AKIA) / neg `x = "AKIAIOSFODNN7EXAMPL0"` (contains `0` — outside base32 alphabet [A-Z2-7]).
- `SECRET_OPENAI_KEY`: pos legacy `sk-REDACTED-EXAMPLE-KEY` (20 chars + marker + 20 chars) / neg `sk-12345678901234567890` (no marker).
- `SECRET_GITHUB_TOKEN`: pos `ghp_` + 36 alnum / neg bare `ghp_` (7 chars).
- `SECRET_PRIVATE_KEY`: pos PEM banner line / neg truncated banner.
- `SECRET_GENERIC_API_KEY`: pos `api_key = "abcdefghijklmnopqrstuvwxyz"` (high-entropy) / neg `secret = "my-cool-secret"` (low entropy → no finding).
- `SECRET_DB_URL`: pos `postgres://user:pass@host/db` / neg `postgres://host/db` (no creds).
- `SECRET_ENV_COMMITTED`: `.env` file present → finding; `.env.example` only → NO finding.
- `SECRET_ENV_NEXT_PUBLIC`: `.env` with `NEXT_PUBLIC_SUPABASE_KEY=` → finding / `REACT_APP_KEY=` → no finding.
- `DANGER_EVAL`: pos `os.system(cmd)` (variable → high) / `os.system("ls -la")` (literal → medium severity).
- `DANGER_SQL_CONCAT`: pos py file `query = "SELECT * FROM users WHERE id = " + user_id` / neg `cursor.execute("SELECT 1")`.
- `CONFIG_CORS_CREDENTIALS`: pos `allow_origins=["*"]` + `allow_credentials=True` → high / `allow_origins=["*"]` alone → medium.
- `CONFIG_HARDCODED_SECRET_KEY`: pos `SECRET_KEY="supersecretkey"` → high / `SECRET_KEY="hJk2$#pQ9xLm7vNw4rTz"` → medium (entropy gate).
- `CONFIG_SUPABASE_NO_RLS`: repo with `client.js` containing `createClient("https://xyz.supabase.co", "anon")` and NO `.sql` RLS → finding; add a `.sql` containing `create policy` → no finding.
- Each assert: `rule_id`, `severity`, `file`, `line` correctness.

**Action — test_scanner_score.py:**
- `no findings → 100 / A`; `one critical → 75 / B`; `one of each severity → 50 / C` (25+15+7+3); `four criticals → 0 / F` (floor); `negative-immune` (10 criticals → still 0).
- Letter grade boundary table: 90→A, 89→B, 75→B, 74→C, 50→C, 49→D, 25→D, 24→F.
- Sub-scores: critical secrets finding → `secrets_score 75`, `code_score 100`; mixed findings only hit their category.
- `_category_of` LLM mapping: `"missing authentication middleware"` → code; `"hardcoded api token in client"` → secrets; `"CORS allows all origins"` → config.

**Action — test_scanner_llm_parse.py:** monkeypatch `app.services.scanner._llm_client` with a fake whose `beta.chat.completions.parse(...)` returns a fake response object:
- valid: `message.parsed = LLMReview(findings=[...])` → returns parsed dicts, status `"ok"`.
- refusal: `message.refusal = "I can't..."` → `([], "rules_only")`.
- exception: fake raises `Exception("OpenAI outage")` → `([], "rules_only")`.
- length: fake raises `LengthFinishReasonError` (import from `openai` — 2.43.0 exposes it) → `([], "rules_only")`.
- no key: ensure `settings.OPENAI_API_KEY = ""` via monkeypatch → `([], "rules_only")` without client call.

**Verify:** `python -m pytest backend/tests/test_scanner_url_validation.py backend/tests/test_scanner_rules.py backend/tests/test_scanner_score.py backend/tests/test_scanner_llm_parse.py -q` → all green.

**Done:** 4 modules green; every rule has positive + near-miss coverage; score math including grade and sub-scores covered; LLM degrades covered.

### Task 8.3: API module (mocked background task)

**Files:** `backend/tests/test_scans_api.py` (new)

**Goal:** Contract-level tests with DB and background task both faked (PATTERNS.md:361-362).

**Action:** Using `client` + `fake_db` + `fake_run_scan` fixtures:
- `POST /api/v1/scans {"repo_url": "https://github.com/user/repo"}` → 201; body has `status == "queued"`, `id` set; `fake_run_scan` recorded exactly `(scan_id, "https://github.com/user/repo")`.
- `POST` with `file:///etc/passwd` → 400 with `"Only https"`-class detail; `fake_run_scan` NOT called.
- `POST` same repo twice → second returns 409 (fake `active_scan_for_repo` sees the queued run).
- `GET /api/v1/scans` → 200 list with `finding_count`; `GET /api/v1/scans/{missing}` → 404.
- `GET /api/v1/scans/{id}` → 200 with `findings` array (seed one finding via `fake_db.insert("scan_findings", {...})`).
- `POST /api/v1/scans/{id}/findings/{fid}/incident` → 201 IncidentResponse; finding marked promoted (`promoted_to_incident is True` in fake DB); second promote → 409.
- `POST .../incident` with wrong scan_id for the finding → 404.

**Verify:** `python -m pytest -q` from `backend/` — all modules green. Then the full target: `.\venv\Scripts\Activate.ps1; pytest`.

**Done:** API module green; the 5-module suite passes; suite runs without Postgres/OpenAI/network.

---

## 4. API Contract (frozen — P3 and P7 both implement this exactly)

| Method | Path | Request | Success | Errors |
|---|---|---|---|---|
| POST | `/api/v1/scans` | `{"repo_url": str, "name"?: str}` | 201 `ScanRun` (status `queued`, `finding_count: 0`, no findings) | 400 invalid URL; 409 duplicate active scan |
| GET | `/api/v1/scans` | `?limit&offset` | 200 `ScanRun[]` (no findings; `finding_count` populated) | — |
| GET | `/api/v1/scans/{id}` | — | 200 `ScanRunDetail` (`findings: ScanFinding[]`) | 404 |
| POST | `/api/v1/scans/{id}/findings/{fid}/incident` | — | 201 `IncidentResponse` | 404 scan/finding; 409 already promoted |

## 5. DB Schema (runtime form — P2)

`scan_runs`: id TEXT PK · repo_url TEXT NOT NULL · name TEXT · status TEXT CHECK (queued/running/completed/failed) DEFAULT 'queued' · score REAL · grade TEXT CHECK (A/B/C/D/F) · summary TEXT · error TEXT · total_files INTEGER · metadata TEXT JSON DEFAULT '{}' · created_at/updated_at TEXT DEFAULT NOW(). Indexes: status, created_at DESC.
`scan_findings`: id TEXT PK · scan_id TEXT NOT NULL · severity TEXT CHECK · category TEXT · rule_id TEXT · file TEXT · line INTEGER · evidence TEXT · description TEXT · remediation TEXT · promoted_to_incident BOOLEAN DEFAULT FALSE. Index: scan_id.
JSON_COLUMNS += scan_runs.metadata; TIMESTAMP_COLUMNS += scan_runs.created_at/updated_at. `scan_findings`: no registrations.

## 6. Verification

```powershell
# Backend (target #1)
cd backend; .\venv\Scripts\Activate.ps1; pip install -r requirements.txt; pytest
# Frontend (target #2)
cd frontend; npm run lint; npm run build
# Regression (target #3: existing features keep working)
cd backend; .\venv\Scripts\Activate.ps1
python -c "from app.main import app; paths=sorted({r.path for r in app.routes if hasattr(r,'path')}); assert '/api/v1/incidents' in paths and '/api/v1/logs' in paths and '/api/v1/anomalies' in paths and '/api/v1/search' in paths and '/api/v1/scans' in paths; print('all routes registered')"
```

### End-to-end (manual, target #4)

1. `docker-compose up -d` (Postgres). Set `DATABASE_URL` in `backend/.env` if not already.
2. `cd backend; .\venv\Scripts\Activate.ps1; uvicorn main:app --reload`.
3. `curl -X POST http://localhost:8000/api/v1/scans -H "Content-Type: application/json" -d '{"repo_url":"https://github.com/octocat/Hello-World"}'` → 201 queued run.
4. Poll `curl http://localhost:8000/api/v1/scans/{id}` until `completed` (30-120s; if `OPENAI_API_KEY` unset it completes via rules-only — both paths must complete).
5. Confirm: score + grade + summary present; findings array (may be empty for a clean repo — Hello-World has none); `total_files > 0`; temp dir cleaned (`Test-Path backend/.scan-tmp/{id}` is False).
6. **Findings-path E2E (optional but recommended):** if the executor can push a fixture repo (seed files: AWS key line, `SECRET_KEY="supersecretkey"`, `os.system(cmd)`, CORS `*`+credentials, committed `.env`) to a throwaway GitHub repo, scan it and confirm findings render with correct lines and critical/high auto-create incidents visible at `GET /api/v1/incidents` (metadata.source == "vibe-scan"). Otherwise findings-path coverage is via P8 unit tests + the mocked-LLM path.
7. Kill OpenAI key (`OPENAI_API_KEY=""`), rescan Hello-World → completes via rules-only (RESEARCH §5 degradation confirmed).
8. Restart uvicorn mid-scan → the orphaned run appears `failed` with "server restarted mid-scan" (sweep proof).
9. Frontend: `cd frontend; npm run dev`; open `http://localhost:3000/scans`; submit a URL; watch list poll (status badges update, polling stops at terminal); open detail; promote a finding → badge flips to "Promoted", incident appears on `/incidents`.

## 7. Risks & Mitigations

| # | Risk | Mitigation (where implemented) |
|---|---|---|
| R1 | Regex FPs flood the report | gitleaks-verified patterns (P4 Task 4.2: base32 alphabet, `T3BlbkFJ` marker, `ghp_`+36), entropy ≥3.5 gates, blocklist, `.env.example` exemption, `.github`/test skip — each with fixture-pair tests (P8) |
| R2 | Git not installed in prod | `FileNotFoundError` → `ScanAbortError("git executable not found...")` → scan marked failed with clear error (P4 Task 4.1); verified git 2.54.0 on dev PATH |
| R3 | OpenAI outage / malformed output | Structured Outputs + Pydantic parse; refusal/length/exception → rules-only; scan never hard-fails (P6 Task 6.1) |
| R4 | Large repos → disk exhaustion | `--depth 1 --single-branch --no-tags --no-recurse-submodules`; `MAX_REPO_SIZE_MB`/`MAX_SCAN_FILES` abort during walk; `_rmtree_retry` cleanup in `finally` (P4) |
| R5 | Server restart mid-scan → UI stuck "running" | Lifespan sweep marks queued/running → failed with "server restarted mid-scan" (P7 Task 7.2); frontend polling stops on failed (P3) |
| R6 | Windows orphan git processes after clone timeout | `Popen` + DEVNULL pipes + `taskkill /F /T /PID` tree kill (P4 Task 4.1); retry-loop rmtree |
| R7 | False positives → users ignore report | UI copy + grade/sub-scores + "heuristic scan, not a guarantee" framing in ScanDetail; precision-oriented LLM prompt |
| R8 | Duplicate incidents on rescan | `finding_has_incident` guard (P6 Task 6.2, P7 Task 7.1) **+ deterministic finding ids — sha1 of `repo_url|rule_id|file|line` assigned before `insert_batch` (P6 Task 6.2)** — so the metadata containment check fires across rescans (fresh per-scan uuid4 ids would never match a previous scan) → 409/skip |
| R9 | Duplicate concurrent scans of same repo | `active_scan_for_repo` 409 on POST (P7 Task 7.1); semaphore bounds concurrency (P6) |
| R10 | SSRF / clone tricks | exact-match host allowlist on urlparse-decoded hostname, no creds, no trailing dot, `--` separator, `protocol.ext/file.allow=never`; DNS-rebinding residual accepted + documented (P4) |
| R11 | Secrets leak to logs/DB | evidence truncation ≤200 chars + masking; URLs with creds rejected pre-clone (P4) |
| R12 | LLM token blowup / cost | 10 files × 12k chars + 600k-char input budget → rules-only; 4o-mini ≈ $0.01-0.02/scan (P6) |
| R13 | Gunicorn worker timeout kills scans in prod | Documented: prod must set `--timeout 300` or scans die at 30s (dev uvicorn unaffected) — note in AGENTS.md |
| R14 | Long-path walk errors (Windows) | per-file try/except skip+log; longPathAware registry note (P4) |

## 8. Success Criteria Checklist (mapped to phase goal)

- [ ] **Safe URL validation**: all RESEARCH §1.1 edge cases enforced + tested (`test_scanner_url_validation.py` green)
- [ ] **Hardened clone**: list-args, `--` separator, transport flags, tree-kill timeout, caps, cleanup (`test_scanner_rules.py` + E2E step 5)
- [ ] **Rules engine**: 20 rules incl. 3 new (SUPABASE_NO_RLS, NEXT_PUBLIC, blocklist) with fixture pairs green
- [ ] **LLM deep-review**: Structured Outputs parse + rules-only fallback on no-key/refusal/length/exception (`test_scanner_llm_parse.py` green + E2E step 7)
- [ ] **Scored report**: 0-100 score, letter grade, per-category sub-scores, summary (`test_scanner_score.py` green)
- [ ] **Auto-incidents**: critical/high findings create incidents with dedupe guard (P8 promote tests + E2E step 6)
- [ ] **Persistence**: scan_runs/scan_findings tables + 8 CRUD methods + DATABASE_SCHEMA.md (P2 verify)
- [ ] **API contract**: 4 endpoints with 400/404/409 semantics (P8 API module green)
- [ ] **Background jobs**: Shape B async + to_thread, startup sweep (E2E step 8)
- [ ] **Frontend**: /scans page with form, polled list (fn-form refetchInterval), detail with promote; `npm run lint` + `npm run build` pass
- [ ] **Regression**: logs/incidents/anomalies/search routes registered and untouched; health OK
- [ ] **pytest suite**: 5 modules + conftest green via `cd backend; .\venv\Scripts\Activate.ps1; pytest`

## 9. Output

After completion, create `.planning/phases/vibe-code-security-scan/` summaries per plan (or a single `.planning/SCAN-SUMMARY.md` if phase dir absent) recording: files created, decisions taken, test results, E2E findings, and any deviations from this plan.
