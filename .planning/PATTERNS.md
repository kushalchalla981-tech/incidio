# Vibe-Code Security Scan — Pattern Map

**Mapped:** 2026-08-07
**Scope:** Full-stack feature: FastAPI backend + Next.js 14 frontend + Postgres (asyncpg/Supabase)
**Analogs found:** 15 / 17 classified files (2 have no existing analog: background-task execution, pytest tests)

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `backend/app/config.py` (mod) | config | n/a | itself (lines 5-17) | exact (self) |
| `backend/app/models.py` (mod) | model | n/a | `IncidentCreate`/`IncidentResponse` (47-93) | exact (self) |
| `backend/app/database.py` (mod) | db layer | CRUD | `query_incidents`/`insert` (125-135, 270-293) | exact (self) |
| `backend/app/services/scanner.py` (new) | service | transform + file-I/O + event-driven | `services/anomaly.py` + `services/embeddings.py` | role-match |
| `backend/app/api/v1/routes/scans.py` (new) | controller | request-response + background | `routes/incidents.py` (54 lines) | exact |
| `backend/app/main.py` (mod) | config | n/a | itself (lines 37-41) | exact (self) |
| `backend/tests/test_scanner_*.py` (new dir) | test | n/a | **none — tests/ does not exist** | no analog |
| `frontend/src/lib/types.ts` (mod) | type defs | n/a | `IncidentResponse`/`IncidentFilters` (48-62, 108-113) | exact (self) |
| `frontend/src/lib/api.ts` (mod) | api client | request-response | `getIncidents`/`createIncident`/`updateIncident` (45-70, 83-96) | exact (self) |
| `frontend/src/lib/hooks.ts` (mod) | react-query hooks | polling | `useIncidents` (37-43) | exact (self) |
| `frontend/src/components/scans/ScanForm.tsx` (new) | component | request-response | `logs/page.tsx` filter row + `Topbar.tsx` input (33-40) | partial (no text-input form exists) |
| `frontend/src/components/scans/ScanList.tsx` (new) | component | CRUD display | `dashboard/RecentIncidents.tsx` (table, 44-76) | exact |
| `frontend/src/components/scans/ScanDetail.tsx` (new) | component | CRUD display | `app/incidents/page.tsx` `IncidentCard` (21-82) | exact |
| `frontend/src/app/scans/page.tsx` (new) | page | CRUD display | `app/incidents/page.tsx` (full page) | exact |
| `frontend/src/components/layout/Sidebar.tsx` (mod) | component | nav | itself `links` array (11-17) | exact (self) |
| `DATABASE_SCHEMA.md` (mod) | docs | n/a | tables sections (11-133) | exact (self) |
| `AGENTS.md` (mod) | docs | n/a | Environment Variables section | exact (self) |

---

# Backend Patterns

## 1. Route structure (`backend/app/api/v1/routes/*.py`)

Every route file follows the same shape — **module-level `router = APIRouter()`** with no prefix (prefix applied at registration in `main.py`), typed decorators, and `db = await get_db()` per handler.

**Imports** (`routes/incidents.py:1-9`, `routes/logs.py:1-12`):
```python
from fastapi import APIRouter, HTTPException, Query
from app.database import get_db
from app.models import IncidentCreate, IncidentResponse, IncidentUpdate

router = APIRouter()
```

**Core handler pattern** (`routes/incidents.py:12-18` — the canonical template for POST):
```python
@router.post("/incidents", response_model=IncidentResponse, status_code=201)
async def create_incident(incident: IncidentCreate):
    try:
        db = await get_db()
        return await db.insert("incidents", incident.model_dump(mode="json"))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

**List with filters** (`routes/incidents.py:21-31`) — `Query(...)` with `ge`/`le` bounds:
```python
@router.get("/incidents", response_model=list[IncidentResponse])
async def list_incidents(
    status: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    db = await get_db()
    return await db.query_incidents(
        status=status, severity=severity, limit=limit, offset=offset
    )
```

**404 pattern** (`routes/incidents.py:34-40`):
```python
@router.get("/incidents/{incident_id}", response_model=IncidentResponse)
async def get_incident(incident_id: str):
    db = await get_db()
    result = await db.get_by_id("incidents", incident_id)
    if not result:
        raise HTTPException(status_code=404, detail="Incident not found")
    return result
```

**Partial update (PATCH)** (`routes/incidents.py:43-54`) — strips `None` values, stamps `updated_at`:
```python
data = {k: v for k, v in update.model_dump(mode="json").items() if v is not None}
data["updated_at"] = datetime.now(timezone.utc).isoformat()
result = await db.update_by_id("incidents", incident_id, data)
if not result:
    raise HTTPException(status_code=404, detail="Incident not found")
```

**400 validation pattern** (`routes/logs.py:31-32`): `raise HTTPException(status_code=400, detail="No logs provided")`

**Conventions to copy:**
- Response models declared on decorator; handler returns raw dict from db layer (FastAPI validates against `response_model`)
- No router-level error middleware — each handler wraps only DB-write operations in try/except → 500
- `model_dump(mode="json")` is the universal model→dict serialization call
- ISO timestamps via `datetime.now(timezone.utc).isoformat()` (also `logs.py:48`, `anomalies.py:47`)

## 2. Service structure (`backend/app/services/*.py`)

Three distinct conventions, all module-level functions (no classes):

**(a) Pure computation module** — `services/anomaly.py` (the analog for `scanner.py`):
- Private helpers prefixed `_` (`_to_datetime` line 10, `_build_windows` line 22, `_extract_feature_matrix` line 76)
- One public entrypoint returning `list[dict]` (`detect_anomalies` line 90)
- Defensive degradation on insufficient data (lines 96-107: returns all-zero scores rather than raising)

**(b) Lazy singleton external-client module** — `services/embeddings.py:8-16` (the analog for the LLM client in `scanner.py`):
```python
_client: Optional[OpenAI] = None
EMBEDDING_MODEL = "text-embedding-3-small"

def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=settings.OPENAI_API_KEY)
    return _client
```
- Module-level `_client` + `_get_client()` lazy init; reads key from `settings` (config.py)
- Same pattern in `services/parser.py:11,32-41` (`_miner` + `get_miner()`, created eagerly in `main.py` lifespan)

**(c) Try/except with graceful fallback** — `services/parser.py:53-60` (`extract_params` swallows exceptions → `[]`) and `routes/search.py:90-104` (backfill catches per-batch errors, records error strings, continues). **This is the "rules-only fallback" precedent** for LLM failure in the scanner.

**No existing background-task / asyncio.run / subprocess usage anywhere in the backend** (verified by grep). `scanner.py`'s `clone_repo` (subprocess) and `run_scan` (FastAPI `BackgroundTasks`) will be the first — the plan (VIBE_SCAN_IMPLEMENTATION_PLAN.md:172-182) specifies: async `run_scan` driven via `BackgroundTasks` + `await` (preferred), cleanup in `finally`.

## 3. Database layer (`backend/app/database.py`)

**Singleton + connection** (`database.py:296-304`):
```python
_db: Optional[Database] = None

async def get_db() -> Database:
    global _db
    if _db is None:
        _db = Database(settings.DATABASE_URL)
        await _db.connect()
    return _db
```

**Schema is a raw SQL string constant** (`database.py:23-70`) executed at connect (`database.py:80-81`). New tables must be appended here as `CREATE TABLE IF NOT EXISTS` + indexes. Note: **actual schema uses `TEXT` ids and `TEXT` timestamps** (not UUID/TIMESTAMPTZ as in DATABASE_SCHEMA.md's aspirational version).

**Serialization maps** (`database.py:11-21`) — register new tables here:
```python
JSON_COLUMNS = {
    "logs": {"metadata", "parameters", "embedding"},
    "incidents": {"metadata", "affected_services"},
    "log_templates": {"metadata"},
}
TIMESTAMP_COLUMNS = {
    "logs": {"timestamp", "created_at"},
    "incidents": {"start_time", "end_time", "created_at", "updated_at"},
    "log_templates": {"first_seen", "last_seen"},
}
```
- `_serialize`/`_deserialize` (88-111) convert dict↔JSON-strings and ISO-strings↔`datetime` per table
- For the scan feature: register `scan_runs` in both maps (`created_at`, `updated_at`); `scan_findings` has neither (per VIBE_SCAN_IMPLEMENTATION_PLAN.md:117)

**Generic CRUD helpers** — no per-table repetition needed for basics:
- `insert(table, data) -> dict` (125-135): auto-generates `id = str(uuid.uuid4())` when missing, `RETURNING *`, deserializes
- `insert_batch(table, records) -> int` (137-153)
- `get_by_id(table, id)` (155-160), `update_by_id(table, id, data)` (162-171)

**Typed query methods** — the pattern for new `query_incidents`-style reads (`database.py:270-293`): build `conditions`/`params` list with `idx` counter for `$n` placeholders, `"WHERE " + " AND ".join(conditions) if conditions else ""`, `ORDER BY <col> DESC LIMIT ${idx} OFFSET ${idx+1}`, deserialize each row.

**Specialized write methods** for non-generic updates — `update_embedding` (247-250) is the analog for `update_scan_status` / `mark_finding_promoted`:
```python
async def update_embedding(self, log_id: str, embedding: list[float]):
    serialized = json.dumps(embedding)
    async with self.pool.acquire() as conn:
        await conn.execute("UPDATE logs SET embedding = $1 WHERE id = $2", serialized, log_id)
```

## 4. Pydantic models (`backend/app/models.py`)

Convention: **triple per resource — `XxxCreate`, `XxxUpdate`, `XxxResponse`** — plus request/response pairs for actions.

- **Create** (`IncidentCreate`, 47-60): required fields with `Field(..., max_length=255)`, `Optional[str] = None`, defaults for lists (`affected_services: List[str] = []`), `field_validator` for enum-like strings:
```python
@field_validator("severity")
@classmethod
def validate_severity(cls, v: str) -> str:
    if v not in ("low", "medium", "high", "critical"):
        raise ValueError("Invalid severity")
    return v
```
- **Update** (`IncidentUpdate`, 63-77): all fields `Optional`, validator tolerates `None` (`if v and v not in (...)`)
- **Response** (`IncidentResponse`, 80-93): `id: UUID`, `datetime` timestamps, `Optional` for nullable, `dict`/`List[str]` for JSON columns
- **Action result wrappers** (`LogUploadResponse` 41-44, `BackfillResponse` 148-151): `processed/failed/errors: list[str] = []` — copy this shape for scan summary types
- Vibe-scan additions (per VIBE_SCAN_IMPLEMENTATION_PLAN.md:64-72): `ScanCreate`, `ScanFinding`, `ScanStatus` (`Literal["queued","running","completed","failed"]`), `ScanRun`/`ScanResponse` — follow the existing create/response split; `promoted_to_incident: bool = False` default.

## 5. Config (`backend/app/config.py`)

Full file is 20 lines — pydantic-settings:
```python
class Settings(BaseSettings):
    DATABASE_URL: str = ""
    OPENAI_API_KEY: str = ""
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"
    LOG_LEVEL: str = "INFO"
    API_V1_PREFIX: str = "/api/v1"
    CORS_ORIGINS: list[str] = ["*"]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )

settings = Settings()
```
New scan settings (`LLM_MODEL`, `SCAN_TMP_DIR`, `MAX_REPO_SIZE_MB`, `MAX_SCAN_FILES`, `MAX_LLM_FILES`, `MAX_LLM_FILE_CHARS`, `SCAN_ALLOWED_HOSTS`) append here with defaults. **Note:** `.env.example` lists `SUPABASE_URL`/`SUPABASE_KEY` but config.py never reads them — new vars must be added to both `.env.example` and the docker-compose `environment` block if needed.

## 6. main.py registration (`backend/app/main.py`)

- Lifespan (14-19): `get_db()` + eager `get_miner()` on startup, `await db.close()` on shutdown
- CORS (29-35): `allow_origins=settings.CORS_ORIGINS`
- Router registration (37-41) — **add scans here**:
```python
app.include_router(health.router, tags=["health"])
app.include_router(logs.router, prefix=settings.API_V1_PREFIX, tags=["logs"])
app.include_router(incidents.router, prefix=settings.API_V1_PREFIX, tags=["incidents"])
app.include_router(anomalies.router, prefix=settings.API_V1_PREFIX, tags=["anomalies"])
app.include_router(search.router, prefix=settings.API_V1_PREFIX, tags=["search"])
```
- Static frontend mount (43-44) — must remain last.

## 7. requirements.txt

```
fastapi>=0.109.0, uvicorn[standard]>=0.27.0, pydantic>=2.11.0, pydantic-settings>=2.1.0,
python-multipart>=0.0.6, asyncpg>=0.29.0, drain3>=0.9.11, python-dotenv>=1.0.0,
aiofiles>=23.2.1, python-dateutil>=2.8.2, numpy>=1.26.0, scikit-learn>=1.4.0,
pyod>=1.1.0, openai>=1.0.0
```
`openai>=1.0.0` already present — scanner reuses it (new-style client). **No new backend dependency needed** (git clone via `subprocess.run`).

---

# Frontend Patterns

## 1. Page structure (`frontend/src/app/*/page.tsx`)

Every page: `"use client"` (line 1), imports `lucide-react` icons, `@/lib/hooks`, `@/components/ui/*` with `@/` alias, `type` imports from `@/lib/types`. Layout skeleton (from `incidents/page.tsx:100-170`):

```
<>  (fragment — pages render inside layout's <main>)
  header row: flex items-center justify-between mb-6
    → h1 className="text-gradient-anim text-[24px] font-semibold" + LiveBadge/status badge
    → action Buttons (variant="primary" size="sm", icon + label)
  filter row: flex items-center gap-[10px] flex-wrap mb-5 with Select components + Clear button
  content: isLoading ? Array of LoadingSkeleton : empty-state div : list of cards
</>
```

- **Loading pattern** (`incidents/page.tsx:157-160`): `Array.from({ length: 5 }).map((_, i) => <LoadingSkeleton key={i} className="h-24 w-full" />)`
- **Empty state** (`incidents/page.tsx:161-165`): centered muted icon + `No X match your filters`
- **Card list** (`incidents/page.tsx:156,167`): `flex flex-col gap-4` wrapper; each item a `Card hover shine glow cursor-pointer`
- Page-level state via `useState` for filters, passed to hooks as `{ severity: sevFilter || undefined, ... }` (`incidents/page.tsx:85-90`)

## 2. React Query hooks (`frontend/src/lib/hooks.ts` — full file is the template)

```typescript
export function useIncidents(filters?: IncidentFilters) {
  return useQuery({
    queryKey: ["incidents", filters],
    queryFn: () => getIncidents(filters),
    refetchInterval: 15000,
  });
}
```
- Polling convention: `refetchInterval` 5000 (logs) / 15000 (incidents) / 30000 (health)
- `useBackfill` (`hooks.ts:31-35`) is the mutation template for `useCreateScan`/`usePromoteFinding`:
```typescript
export function useBackfill() {
  return useMutation({ mutationFn: backfillEmbeddings });
}
```
- For scans (per VIBE_SCAN_IMPLEMENTATION_PLAN.md:206): `useScans()` with conditional `refetchInterval: 3000` — pattern precedent: `useLogSearch`'s conditional `enabled: query.query.length > 0` (`hooks.ts:23-29`). Use `refetchInterval: runs.some(r => r.status === "running" || r.status === "queued") ? 3000 : false`.

## 3. API client (`frontend/src/lib/api.ts` — full file is the template)

```typescript
const BASE = "";

async function fetchJSON<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${url}`, {
    headers: { "Content-Type": "application/json", ...init?.headers },
    ...init,
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API ${res.status}: ${body}`);
  }
  return res.json();
}
```
- GET with filters (`api.ts:45-53`): build `URLSearchParams`, `params.set(...)` per optional field, append `${qs ? `?${qs}` : ""}`
- POST/PATCH (`api.ts:59-70`, `83-96`): `fetchJSON<T>(url, { method: "POST", body: JSON.stringify(data) })`
- New scan functions (`createScan`, `getScans`, `getScan`, `promoteFinding`) copy these verbatim with `/api/v1/scans` paths.

## 4. Types (`frontend/src/lib/types.ts`)

- Interfaces mirror backend response models **field-for-field, snake_case** (e.g., `IncidentResponse` 48-62 ↔ backend `IncidentResponse` models.py:80-93)
- `metadata: Record<string, unknown>`, `string | null` for nullable, `string` for timestamps (ISO)
- Filter interfaces (`IncidentFilters` 108-113) = optional versions of query params
- Scan additions: `ScanRun`, `ScanFinding`, `ScanStatus` union of `"queued" | "running" | "completed" | "failed"` (mirror backend)

## 5. UI components (`frontend/src/components/ui/*`)

All: `import clsx from "clsx"`, props interface, `export default function`, variant/size maps as `Record<Variant, string>`, arbitrary Tailwind values.

- **Card** (`ui/Card.tsx`): glass style `bg-[var(--surface)] backdrop-blur-[16px] border border-[var(--border)] rounded-[20px] p-6`; boolean props `hover` (shadow lift), `shine` (`glass-shine` class), `glow` (`border-glow-hover`), `onClick`
- **Button** (`ui/Button.tsx`): `variant: "primary" | "secondary" | "ghost" | "danger"` (lines 6-11), `size: "sm" | "md"` (15-18); icons inside via `{children}` with `gap-[6px]`; exports `IconButton` too
- **Badge** (`ui/Badge.tsx`): `variant: "success" | "warn" | "danger" | "info" | "neutral"` (lines 6-12) — **scan status/severity badges reuse this map directly** (`bg-green-100 text-success` etc.)
- **Select** (`ui/Select.tsx`): `options: { value: string; label: string }[]` prop, ChevronDown adornment, `focus:border-accent focus:shadow-[0_0_0_3px_var(--accent-soft)]`
- **KPI** (`ui/KPI.tsx`): label/value/decimals/prefix/suffix/`change={{value, up, down}}` props, count-up animation on IntersectionObserver (32-55)

## 6. Layout (`frontend/src/components/layout/*`)

- **Sidebar** (`Sidebar.tsx:11-17`) — nav links array to extend:
```typescript
const links = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/incidents", label: "Incidents", icon: AlertTriangle },
  { href: "/logs", label: "Logs", icon: ScrollText },
  { href: "/analytics", label: "Analytics", icon: BarChart3 },
  { href: "/settings", label: "Settings", icon: Settings },
];
```
  Active state: `pathname.startsWith(href)` (line 47) → `bg-[var(--accent-soft)] text-accent` + left accent bar (57). Add `{ href: "/scans", label: "Security Scans", icon: Shield }` after Logs.
- **Providers** (`Providers.tsx`): single `QueryClient` in `useState` — no per-page QueryClient needed
- **Topbar** (`Topbar.tsx:33-40`): the only text-input styling precedent — rounded-full search input with icon:
```typescript
<input type="text" placeholder="Search incidents, logs..."
  className="w-full py-2 pl-9 pr-4 border border-[var(--border)] rounded-[9999px] bg-white/50 text-[13px] ... focus:border-accent focus:shadow-[0_0_0_3px_var(--accent-soft)]" />
```
  (Copy for `ScanForm.tsx` repo-URL input.)

## 7. Styling conventions

- **Colors are Tailwind theme tokens** (`tailwind.config.ts:11-32`) mapped to CSS vars (`globals.css:5-30`): `accent`, `accent-soft`, `success`, `warn`, `danger`, `muted`, `fg`, `fg-2`, `border`, `border-soft`, `surface`. Both forms used: `text-accent` (token) and `bg-[var(--surface)]` (arbitrary var) — prefer tokens for named colors, `var(--...)` for translucent surfaces/borders.
- **Arbitrary px values** everywhere instead of default scale: `text-[13px]`, `gap-[10px]`, `py-[10px]`, `rounded-[10px]`, `w-[7px]`
- Utility classes from `globals.css` `@layer utilities` (97-193): `text-gradient-anim` (page titles), `skeleton` (LoadingSkeleton), `glass-shine`, `border-glow-hover`
- Icons: `lucide-react` (`ChevronDown`, `Plus`, `AlertTriangle`, `Shield` for scans)
- Status dot pattern (`incidents/page.tsx:35-41`): `w-[7px] h-[7px] rounded-full shadow-[0_0_8px_currentColor] text-danger bg-danger animate-glow-pulse` with per-severity color classes

---

# Testing Patterns

**`backend/tests/` does not exist** (verified: no `test_*.py` files anywhere in repo). No pytest config, no fixtures, no existing test files.

**Precedents to follow (from AGENTS.md + VIBE_SCAN_IMPLEMENTATION_PLAN.md:246-253):**
- Command: `cd backend; .\venv\Scripts\Activate.ps1; pytest` (venv exists at `backend/venv/`)
- New files land in `backend/tests/`: `test_scanner_url_validation.py`, `test_scanner_rules.py`, `test_scanner_score.py`, `test_scanner_llm_parse.py`, `test_scans_api.py`
- No pytest config file is planned; per-module functions are the style (matching the codebase's module-level function convention)
- LLM tests should use mocked response strings (malformed JSON → graceful fallback), mirroring the service's try/except degrade pattern (`search.py:90-104`)
- API tests mock the background task (assert POST returns queued run immediately)

**Frontend testing:** none configured (AGENTS.md says "Jest/React Testing Library (to be configured)"); `npm run lint` + `npm run build` are the checks (`package.json:9-10`).

---

# Database Schema Documentation (`DATABASE_SCHEMA.md`)

Each table documented as: heading `### N. <table>`, one-line purpose, ` ```sql CREATE TABLE ... ``` ` block with CHECK constraints + indexes, then a bullet list of column descriptions (name — meaning), then Relationships / Sample Data / Query Examples sections. The new `scan_runs` and `scan_findings` tables must be appended as `### 4. scan_runs` / `### 5. scan_findings` with the same structure. **Note:** schema doc shows UUID/TIMESTAMPTZ but runtime `SCHEMA_SQL` uses TEXT — document the runtime form (`database.py:23-70`) to match reality.

---

# Patterns for the Vibe-Code Security Scan Feature (new → analog map)

## Backend

| New file / change | Copy from | What to copy |
|---|---|---|
| `config.py` +7 settings | `config.py:5-17` | Settings class fields with defaults; add vars to `.env.example` + docker-compose |
| `models.py` +Scan models | `models.py:47-93` (Incident triple) | `ScanCreate`/`ScanRun` response split; `field_validator` for status/severity (15-21); `BackfillResponse` shape (148-151) for summary fields |
| `database.py` +2 tables, 7 methods | `SCHEMA_SQL` (23-70); `insert` (125-135); `update_embedding` (247-250) for status updates; `query_incidents` (270-293) for `get_scan_runs` | SQL string append; `JSON_COLUMNS`/`TIMESTAMP_COLUMNS` registration (11-21); `$n` placeholder builder (121-123) |
| `services/scanner.py` (new) | `anomaly.py` structure (helpers + single entrypoint), `embeddings.py:12-16` `_get_client` lazy singleton for OpenAI, `parser.py:53-60` try/except fallback for LLM-degrade-to-rules | Module layout per VIBE_SCAN_IMPLEMENTATION_PLAN.md:121-182; **no analog exists for** subprocess clone / `BackgroundTasks` — implement per plan |
| `routes/scans.py` (new) | `incidents.py` (all 54 lines) | router + response_model/status_code; POST 201 try/except 500 (12-18); list w/ limit/offset (21-31); 404 get (34-40); new: 409 conflict guard for double-promote (no analog — closest is 400 at `logs.py:31-32`) |
| `main.py` +1 line | `main.py:37-41` | `app.include_router(scans.router, prefix=settings.API_V1_PREFIX, tags=["scans"])` |
| `tests/*.py` (new dir) | none | pytest per AGENTS.md; 5 modules per plan |
| `DATABASE_SCHEMA.md` | existing table sections | Append scan tables, same format |

## Frontend

| New file / change | Copy from | What to copy |
|---|---|---|
| `lib/types.ts` +Scan types | `types.ts:48-62,108-113` | Interface + filter interface, snake_case, `Record<string, unknown>` |
| `lib/api.ts` +4 functions | `api.ts:45-53` (list w/ URLSearchParams), `59-70` (POST), `55-57` (by-id) | `fetchJSON<T>` wrapper, `/api/v1/scans` paths |
| `lib/hooks.ts` +4 hooks | `hooks.ts:37-43` (useIncidents), `31-35` (useBackfill mutation), `23-29` (conditional options) | `useScans` w/ conditional `refetchInterval: 3000` while running/queued; `useCreateScan`/`usePromoteFinding` mutations |
| `components/scans/ScanForm.tsx` (new) | `Topbar.tsx:33-40` (input styling), `logs/page.tsx` filter row, `Button.tsx` | URL input + submit Button; disabled state while scanning; client-side https/host validation |
| `components/scans/ScanList.tsx` (new) | `RecentIncidents.tsx:44-76` (full file) | Table with mono header labels, `border-t border-[var(--border-soft)] hover:bg-[var(--accent-soft)]` rows, Badge variant maps (8-20), Link to detail |
| `components/scans/ScanDetail.tsx` (new) | `incidents/page.tsx:21-82` (`IncidentCard`) | Expandable Card sections, severity→Badge variant map (13-15), mono `file:line`, `border-[var(--border-soft)]` dividers; findings table rows like `RecentIncidents` |
| `app/scans/page.tsx` (new) | `incidents/page.tsx:84-171` | Page skeleton: header row + text-gradient-anim h1, content grid, LoadingSkeleton arrays, empty states |
| `Sidebar.tsx` +1 link | `Sidebar.tsx:11-17` | `{ href: "/scans", label: "Security Scans", icon: Shield }` after Logs |

## Shared cross-cutting patterns

1. **All controller POST/PATCH handlers**: `try/except → HTTPException(500)` + `response_model` + `model_dump(mode="json")`
2. **All DB writes**: via `await get_db()` singleton; JSON columns through `_serialize` (register table in `JSON_COLUMNS`)
3. **All list endpoints**: `limit: int = Query(50, ge=1, le=500), offset: int = Query(0, ge=0)`
4. **All frontend data**: React Query hooks with `queryKey` arrays + `refetchInterval` polling; API errors thrown as `Error(\`API ${status}: ${body}\`)`
5. **All UI lists**: Card/table + LoadingSkeleton + empty state; Badge variant maps for enums
6. **Lazy external clients**: module-level `_client` + `_get_client()` from `settings` — reuse for scanner's OpenAI LLM calls
7. **Graceful degradation**: never hard-fail on external service errors (`parser.py:53-60`, `search.py:90-104`) — scanner falls back to rules-only when LLM unavailable

---

# No Analog Found

| File | Role | Reason |
|---|---|---|
| `backend/app/services/scanner.py` (clone/subprocess/BackgroundTasks parts) | service | No existing subprocess, background-task, or file-walk code in backend — use VIBE_SCAN_IMPLEMENTATION_PLAN.md:129-182 spec + Python stdlib (`subprocess.run`, `pathlib.rglob`) |
| `backend/tests/*.py` (whole directory) | test | No tests exist anywhere in repo — follow AGENTS.md pytest conventions + plan's 5-module spec |

---

# Metadata

**Analog search scope:** `backend/app/**` (18 files), `frontend/src/**` (27 files), `backend/tests/` (0 files), root docs
**Files scanned:** ~30 (all backend + frontend source files)
**Pattern extraction date:** 2026-08-07
