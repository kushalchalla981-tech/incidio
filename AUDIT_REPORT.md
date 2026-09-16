# AI Incident Copilot — Complete Project Audit

**Audited:** 2026-08-14 · **Scope:** `C:\projectwa\workshop` (read-only audit, no files modified except this report)

---

## A. Executive Summary

**Overall completion estimate: ~45% of the documented vision.** The core Day 1–2 incident-management MVP (log ingestion, Drain3 parsing, incident CRUD, anomaly detection, vector search scaffolding, and a styled Next.js UI) is functionally implemented and was verified working against a live Postgres at some point (evidence: `backend/uvicorn_out.txt`). The newer "Vibe-Code Security Scan" phase is ~35–40% complete: foundations (config, models, DB, frontend data layer, scanner rules engine) exist, but the scoring math, LLM orchestrator, API routes, UI, and all tests are missing. The project has **zero tests**, **zero auth**, **no working production deployment config**, and **no git history** (no commits).

**Major strengths:**
- Clean, consistent FastAPI architecture (routes → services → database layer)
- Well-documented scan feature plan (`.planning/PLAN.md`, ~1136 lines with dependency waves, P1–P8)
- High-quality scanner security code (SSRF-hardened URL validation, hardened git clone, 20 gitleaks-verified rules)
- Polished, consistent frontend design system
- Frontend passes `npm run lint` and `tsc --noEmit` cleanly

**Major problems:**
1. Scan feature incomplete mid-implementation (P4 scoring, P6–P8 entirely missing)
2. No backend tests at all; `backend/tests/` doesn't exist despite AGENTS.md
3. No database available in the current environment — `DATABASE_URL` points to `localhost:5432`, but Postgres isn't running and **Docker is not installed**
4. Deployment config is broken: `render.yaml` would fail on Render (wrong build root/start command); `main.py` statically serves Next.js *source* files (no built app) at `/`
5. Docs vs. reality contradictions everywhere (README claims Supabase, LangChain, HDBSCAN, postmortems — none exist; ARCHITECT.md specifies a dark design that isn't implemented; root `requirements.txt` is a different, unused manifest)
6. Two real backend bugs verified by code reading (see section E)

**Biggest blockers:**
1. No runnable database (Postgres/Docker absent) — blocks all runtime verification
2. No `OPENAI_API_KEY` in `backend/.env` (empty) — embeddings, LLM review, and semantic search are non-functional until a key is provided
3. Missing scan orchestrator/routes block the whole scan feature
4. No git commits — no history/recovery safety net

---

## B. Technology and Architecture

**Tech stack (actual, verified):**

| Layer | Technology | Evidence |
|---|---|---|
| Backend | FastAPI 0.136.1, Python 3.14.4 (venv), uvicorn | `backend/requirements.txt`, venv probe |
| DB access | asyncpg pool, raw SQL, schema auto-created at connect | `backend/app/database.py` |
| DB driver target | PostgreSQL 16 (local via docker-compose) — **Supabase was abandoned** | `docker-compose.yml`, `.env` (URL `…@localhost:5432/incidents`) |
| Log parsing | Drain3 (TemplateMiner, file persistence) | `backend/app/services/parser.py` |
| Anomaly detection | PyOD IForest (Isolation Forest) | `backend/app/services/anomaly.py` |
| Embeddings/search | OpenAI `text-embedding-3-small`, brute-force cosine | `backend/app/services/embeddings.py`, `search.py` |
| LLM | OpenAI SDK 2.43.0 (planned Structured Outputs) | `backend/requirements.txt`, `.planning/PLAN.md` |
| Frontend | Next.js 14.2.35, React 18, TypeScript strict, Tailwind 3.4, React Query 5, Recharts, lucide-react | `frontend/package.json` |
| Scanner | git subprocess + 20 regex rules | `backend/app/services/scanner.py` |

**Architecture:** Frontend (Next.js dev server :3000, rewrites `/api/*` → :8000) ↔ FastAPI REST API (`/api/v1/*`) ↔ asyncpg pool ↔ PostgreSQL. Backend layers: `routes/` (controllers) → `services/` (pure logic + external clients) → `database.py` (generic CRUD + typed queries). Background work planned via FastAPI `BackgroundTasks` + `asyncio.to_thread`.

**Major modules (implemented):**
- Backend: `logs.py` (CRUD + file upload), `incidents.py` (CRUD), `anomalies.py` (windowed IForest detection), `search.py` (semantic search + embedding backfill), `health.py`, `scanner.py` (partial)
- Frontend: `/`, `/dashboard`, `/incidents`, `/logs` + 15 components (`ui/`, `layout/`, `dashboard/`, `shared/`)

**External services:** OpenAI (embeddings; key currently empty). Planned: OpenAI chat for scan LLM review (never wired).

**Database:** 5 tables auto-created at startup: `logs`, `incidents`, `log_templates`, `scan_runs`, `scan_findings` (TEXT ids/timestamps, JSON-as-TEXT). `backend/data/app.db` is a leftover empty SQLite file from the pre-migration era (verified: 3 tables, 0 rows).

**Authentication:** **None.** No users, no login, no RLS, no API keys.

**Deployment:** `docker-compose.yml` (db + backend only, no frontend service), `backend/Dockerfile`, `render.yaml` (broken — see E), `setup.ps1` / `quick-start.ps1`.

---

## C. Completed Work (verified)

| Feature | Status | Evidence |
|---|---|---|
| Log CRUD + batch API | ✅ Working | `backend/app/api/v1/routes/logs.py`; 200s in `uvicorn_out.txt` |
| Log file upload w/ Drain3 parsing + template upsert | ✅ Working | `logs.py:42-102`, `services/parser.py`, `database.upsert_template` |
| Incident CRUD API | ✅ Working | `incidents.py`; 200 in `uvicorn_out.txt` |
| Anomaly detection API (windowed Isolation Forest) | ✅ Working | `anomalies.py`, `services/anomaly.py` |
| Semantic search + embedding backfill | ✅ Working (needs OpenAI key) | `search.py`, `embeddings.py` |
| Health endpoint | ✅ Working | `health.py`; 200 in `uvicorn_out.txt` |
| DB layer: 5 tables, JSON/timestamp serialization, generic + typed queries | ✅ Working | `database.py` (391 lines) |
| Scan config settings (9) | ✅ | `config.py:12-20` |
| Scan Pydantic models | ✅ | `models.py:160-200` |
| Scan DB tables + 8 CRUD methods | ✅ | `database.py:73-105, 331-375`; `DATABASE_SCHEMA.md` §4–5 |
| Scanner: URL validation, hardened clone, walker, 20 rules, handlers, `scan_repo` | ✅ (rules half) | `services/scanner.py:1-504` |
| Frontend data layer for scans (types/api/hooks) | ✅ | `types.ts:115-156`, `api.ts:98-113`, `hooks.ts:45-84` |
| Frontend: dashboard, incidents, logs pages + design system | ✅ Working | `src/app/{dashboard,incidents,logs}/page.tsx`, `components/ui/*` |
| Landing page with typed-hero animation | ✅ | `src/app/page.tsx` |
| Lint + typecheck | ✅ Clean | `npm run lint` (0 errors), `npx tsc --noEmit` (0 errors) |
| AGENTS.md env-var docs, .gitignore (.scan-tmp, backend/data) | ✅ | root files |

---

## D. Incomplete and Pending Work

| # | Item | Status | Evidence | Priority |
|---|---|---|---|---|
| 1 | **Scanner scoring** (`score_report`, `_letter_grade`, `_category_of`, `build_summary`, `SEVERITY_WEIGHTS`) | **Missing** — PLAN P4 Task 4.3 never implemented; `scanner.py` ends at `scan_repo` (line 504) | grep for `def score_report` → no matches | **Critical** |
| 2 | **LLM deep-review** (`llm_review`, `select_llm_files`, `LLMFinding/LLMReview`, `_get_llm_client`) | **Missing** — PLAN P6 Task 6.1 | grep → no matches | **Critical** |
| 3 | **Scan orchestrator** (`run_scan`, `promote_finding_to_incident`, `sweep_orphaned_scans`, `merge_findings`, semaphore) | **Missing** — PLAN P6 Task 6.2 | grep → no matches | **Critical** |
| 4 | **Scan API routes** (`routes/scans.py` + main.py registration + lifespan sweep) | **Missing** — PLAN P7 | Route list probe: no `/api/v1/scans`; `main.py` imports 5 routers only | **Critical** |
| 5 | **Backend tests** (5 modules + conftest + pytest.ini) | **Missing** — PLAN P8; `backend/tests/` doesn't exist | glob `backend/**/test*.py` → none | **High** |
| 6 | **Frontend scans UI** (`components/scans/*`, `app/scans/page.tsx`, Sidebar link) | **Missing** — PLAN P5 | glob `components/scans/**` → none | **High** |
| 7 | **Search route bug** (stale `svc`/`lvl` vars) | **Broken** | `search.py:38-39` assigns in scoring loop; used in results loop at `:59-60` → wrong service/level on results | **High** |
| 8 | **Log upload crash on empty/unparseable file** | **Broken** — `inserted` unbound when `batch` empty | `logs.py:96-102` | **High** |
| 9 | **Dead nav links** (`/analytics`, `/settings`, `/incidents/[id]`) | **Broken** — links to pages that don't exist (404) | `Sidebar.tsx:15-16`, `page.tsx:86`, `RecentIncidents.tsx:58`; only 4 page files exist | **Medium** |
| 10 | **render.yaml deployment** | **Broken** — builds root `requirements.txt`; starts `uvicorn app.main:app` from repo root; app lives in `backend/`; no `rootDir` | `render.yaml:7-8` vs project layout | **Critical** |
| 11 | **Static frontend mount in `main.py`** | **Broken** — serves Next.js source `.tsx` files, not a built app; no `index.html` → `/` 404s | `main.py:43-44` | **Medium** |
| 12 | **docker-compose** | **Incomplete** — no frontend service; scan tmp/settings not wired; fine for dev DB only | `docker-compose.yml` | **Medium** |
| 13 | **Auth / authorization** | **Missing entirely** | no auth code anywhere | High (roadmap) |
| 14 | **LLM incident analysis, postmortem generation, timeline, root-cause ranking** (README MVP items) | **Not implemented** | README `:126-136` claims; no such code/routes | Medium (scope decision) |
| 15 | **OpenAI key** | **Missing** — `OPENAI_API_KEY` empty in `.env` → embeddings/LLM degrade | `.env` probe | **High** |
| 16 | **Database runtime** | **Down** — Postgres not running; Docker not installed | asyncpg connect probe → `ConnectionRefusedError`; `docker` command not found | **Critical (env)** |
| 17 | **Frontend build verification** | Requires verification — `.next/` exists, lint/tsc clean, but `npm run build` not re-run in audit | `.next/` present | Low |
| 18 | **Git history** | **Missing** — zero commits, everything untracked | `git log` → "no commits yet" | Medium |
| 19 | **README/docs accuracy** | **Stale/contradictory** — Supabase, LangChain, HDBSCAN, RAG, postmortem, perf metrics claimed but absent; root `requirements.txt` unused (langchain/torch/etc.) | README §Tech Stack/Features; root `requirements.txt` | Medium |
| 20 | **ARCHITECT.md design system** | **Contradicts implementation** — spec: dark `#0A0A0F` + cyan `#00FFC8`, Tailwind v4, Next 16; implementation: light blue theme `#4f8cff`, Tailwind 3, Next 14 | `ARCHITECT.md` vs `globals.css`/`tailwind.config.ts` | Low |
| 21 | **DB connection robustness** | **Requires verification** — lifespan `get_db()` fails hard if DB down at boot | `main.py:15-19` | Medium |
| 22 | **`parser.py` CWD dependency** | **Unclear** — `data/drain3_state.bin` relative path breaks if launched from another dir | `parser.py:9` | Low |

---

## E. Missing or Broken Functionality (details)

1. **Search returns wrong service/level** (`search.py:36-65`) — `svc`/`lvl` are loop-last values leaked into every result row (verified by code trace). Must be recomputed per row in the results loop.
2. **Upload 500 on empty file** (`logs.py:96`) — `inserted` is only assigned inside `if batch:`; empty/fully-unparseable files raise `UnboundLocalError` → 500 instead of `{logs_processed: 0, logs_failed: N}`.
3. **`render.yaml` cannot deploy** — no `rootDir`/`workingDirectory`; `pip install -r requirements.txt` (root manifest, includes torch/langchain!) + `uvicorn app.main:app` from repo root where `app/` doesn't exist → guaranteed build/start failure.
4. **`main.py` serves source, not app** — `StaticFiles(frontend/, html=True)` has no `index.html`; would serve `.tsx` sources. In prod this must be removed or pointed at a Next.js static export/build output.
5. **CORS misconfiguration** — `allow_origins=["*"]` + `allow_credentials=True` (browser-invalid combo, and dangerous with no auth).
6. **`anomalies.py` GET/POST duplication** and zero validation of `window_minutes`/`contamination` bounds.
7. **Frontend mock data in production UI** — SystemHealth, KPI trends, notifications, 24h chart are hardcoded; buttons ("New Incident", "Export", "Refresh", "Run Postmortem") are non-functional.
8. **No loading/error/empty distinctions on API failures** — React Query errors silently render as empty states.
9. **`finding_has_incident`** relies on `metadata::jsonb` containment — works only if `metadata` is valid JSON (fine), but no rescan dedupe exists yet since scan flow doesn't exist.
10. **`select` filters with no `onChange`** on dashboard/logs pages (service/time filters are decorative).

---

## F. Dependency-Aware Implementation Roadmap

```
Phase 0 (environment, prerequisite):  Postgres running + OPENAI_API_KEY + git init
   └─ unblocks every verification step
Phase 1 (foundation fixes):            bug fixes (search.py, logs.py upload) — independent
Phase 2 (backend scan core):           scoring (Prompt 01) → orchestrator/LLM (Prompt 02)
Phase 3 (backend API):                 routes/scans.py + main.py wiring (Prompt 03)
Phase 4 (testing):                     pytest suite: conftest + 5 modules (Prompt 04)
Phase 5 (frontend):                    scans UI (Prompt 05) → nav reconciliation (Prompt 06)
Phase 6 (integrations/deploy):         deployment fixes: render.yaml, static mount, compose,
                                       requirements consolidation (Prompt 07)
Phase 7 (security):                    CORS, input bounds, DB-boot resilience (Prompt 08)
Phase 8 (final QA + docs):             E2E verification, docs sync, commit (Prompt 09)
```

---

## G. AI Coding Prompts (execution order)

---

### Prompt 01 — Scanner scoring math (complete P4 Task 4.3)

**ROLE:** Senior Python backend engineer, expert in the FastAPI + asyncpg codebase conventions of this project.

**CONTEXT:** The Vibe-Code Security Scan feature (`.planning/PLAN.md`) is half-implemented. `backend/app/services/scanner.py` already contains `validate_repo_url`, `clone_repo`, `iter_source_files`, the 20-rule `RULES` table, handlers, and `scan_repo` (returns the frozen 4-tuple `(findings, files_with_hits, texts, total_bytes)`). The scoring subsystem planned in P4 Task 4.3 was never written — `scanner.py` ends at `scan_repo` (line 504).

**OBJECTIVE:** Append the scoring module: `SEVERITY_WEIGHTS`, `_letter_grade`, `_category_of`, `score_report`, `build_summary` to `backend/app/services/scanner.py`.

**CURRENT STATE:** `scanner.py` lines 1–504 exist and import cleanly (verified: app imports OK). No scoring functions exist (grep-verified).

**REQUIREMENTS:**
- `SEVERITY_WEIGHTS = {"critical": 25, "high": 15, "medium": 7, "low": 3}` (module constant).
- `_letter_grade(score: float) -> str`: A ≥90, B ≥75, C ≥50, D ≥25, else F.
- `_category_of(finding: dict) -> str`: rule findings carry `category`; LLM findings map by keyword: `secret|key|token|credential` → `secrets`; `cors|debug|config|header|secret-key` → `config`; else `code`.
- `score_report(findings: list[dict]) -> dict` returning `{"score", "grade", "sub_scores": {"secrets_score", "code_score", "config_score"}, "counts": {critical, high, medium, low}}`; `score = max(0, 100 - Σ weights)`; each sub-score = `max(0, 100 - Σ weights in that category)`; identical weights for LLM findings.
- `build_summary(scan_run, findings) -> str`: `"{n} findings ({c} critical, {h} high, {m} medium, {l} low) across {files} files"` (files = count of distinct `file` values or `total_files` from scan_run — use distinct finding files).

**IMPLEMENTATION GUIDELINES:** Follow existing module conventions (module-level functions, `_`-prefixed privates, pure logic, no I/O). Do not modify any existing function in `scanner.py`. Match the exact signatures/names from PLAN.md so later prompts (orchestrator, tests) integrate without renaming.

**FILES AND MODULES:** `backend/app/services/scanner.py` (append only).

**DEPENDENCIES:** None — pure Python + `re`. (Prompt 02 depends on this.)

**EDGE CASES:** Empty findings list → score 100, grade A, all sub-scores 100, counts zero. More than 4 criticals → floor at 0 (not negative). Findings with unknown/None category → treated as `code` in sub-scores but counted in totals. LLM category strings not in the 3 known buckets → `_category_of` keyword mapping.

**ERROR HANDLING:** No exceptions expected; guard against `finding.get("severity")` being None (skip weight, count 0).

**SECURITY:** No data from findings is logged; only numeric aggregation.

**TESTING:** No test framework exists yet (added in Prompt 04) — but verify with the inline asserts below. Do not create `backend/tests/` now.

**VALIDATION:** From `backend/` with venv:
```
python -c "from app.services.scanner import score_report, _letter_grade; assert _letter_grade(90)=='A' and _letter_grade(75)=='B' and _letter_grade(50)=='C' and _letter_grade(25)=='D' and _letter_grade(24)=='F'; r=score_report([{'severity':'critical','category':'secrets'}]); assert r['score']==75 and r['grade']=='B' and r['sub_scores']['secrets_score']==75 and r['sub_scores']['code_score']==100; r=score_report([{'severity':'critical','category':'secrets'}]*4); assert r['score']==0 and r['grade']=='F'; print('score ok')"
```

**NON-GOALS:** Do not write `llm_review`/`run_scan`/routes/tests. Do not touch other files. Do not modify the 4-tuple `scan_repo` signature.

**COMPLETION CRITERIA:** Functions exist with exact names; asserts above pass; `scanner.py` imports cleanly; no other file changed.

**FINAL REPORT:** List changed file, added functions, verification output, any deviations.

---

### Prompt 02 — Scan orchestrator + LLM deep-review (P6)

**ROLE:** Senior Python backend engineer, FastAPI + asyncpg + OpenAI Structured Outputs specialist.

**CONTEXT:** Completing the Vibe-Code Security Scan backend. Prompt 01 added scoring to `scanner.py`. PLAN.md P6 (Tasks 6.1–6.2) specifies the async orchestrator that binds the pure rules engine to the DB and OpenAI. The DB layer already has all 8 scan CRUD methods (`insert_scan_run`, `update_scan_status`, `get_scan_runs`, `get_scan_run`, `get_scan_findings`, `mark_finding_promoted`, `finding_has_incident`, `active_scan_for_repo`) in `database.py:331-375`.

**OBJECTIVE:** Append to `scanner.py`: LLM deep-review (`_get_llm_client`, `LLMFinding`, `LLMReview`, `select_llm_files`, `llm_review`), orchestrator (`run_scan`, `promote_finding_to_incident`, `sweep_orphaned_scans`, `merge_findings`, `_scan_semaphore`).

**CURRENT STATE:** `scanner.py` has validation/clone/walker/rules/scoring (after Prompt 01). `config.py` has `LLM_MODEL`, `MAX_LLM_FILES`, `MAX_LLM_FILE_CHARS`, `MAX_LLM_INPUT_CHARS`, `SCAN_MAX_CONCURRENT`. `OPENAI_API_KEY` is currently empty in `.env` — degradation must be graceful.

**REQUIREMENTS (from PLAN.md P6, exact):**
- `_get_llm_client()` lazy singleton mirroring `embeddings.py:12-16`, `timeout=60.0`.
- `LLMFinding`/`LLMReview` Pydantic models (severity `Literal`, `findings` with `default_factory=list`).
- `select_llm_files(scanned_files: list[tuple[str,int]], texts: dict[str,str]) -> list[tuple[str,str]]` — rank by hit-count desc, size asc; cap `MAX_LLM_FILES`; snippet = `"# path\n" + text[:MAX_LLM_FILE_CHARS]`; if total input > `MAX_LLM_INPUT_CHARS` → return fewer files (highest-ranked first).
- `llm_review(snippets) -> tuple[list[dict], str]` — status `"ok"` or `"rules_only"`; `([])` on: no key, empty snippets, refusal, exception, length error. Use `client.beta.chat.completions.parse(model=settings.LLM_MODEL, ..., response_format=LLMReview, max_tokens=4000)`. System prompt: security auditor for vibe-coded web apps, OWASP Top 10, precision over recall, at most 20 findings.
- `merge_findings(rule_findings, llm_findings)` — drop LLM findings colliding on `(file, line, category)`.
- `promote_finding_to_incident(db, finding, scan_run) -> Optional[dict]` — dedupe via `db.finding_has_incident`; incident: `title=f"[Scan] {description[:100]}"`, `severity`, `start_time=now-utc`, description multi-line, `affected_services=[scan name or repo_url]`, `metadata={scan_id, finding_id, source:"vibe-scan", file, line, rule_id}`; then `mark_finding_promoted`.
- `run_scan(scan_id, repo_url)` — **async, Shape B**: `_scan_semaphore = asyncio.Semaphore(settings.SCAN_MAX_CONCURRENT)`; status transitions queued→running→completed/failed; `asyncio.to_thread` for `clone_repo`/`scan_repo`/`llm_review`; deterministic finding ids `sha1(repo_url|rule_id|file|line)` assigned **before** `insert_batch` (rescan dedupe); auto-promote critical/high findings; metadata includes sub-scores + `rule_findings`/`llm_findings`/`llm_status`; cleanup temp dir in `finally`; `ScanAbortError` → failed with message; any other exception → failed (never crash).
- `sweep_orphaned_scans(db) -> int` — mark queued/running as failed with "server restarted mid-scan".

**IMPLEMENTATION GUIDELINES:** Append only to `scanner.py`. Follow `anomaly.py`/`embeddings.py` conventions. Do not create routes (Prompt 03 does that). Never write secrets to logs; evidence is already masked upstream.

**FILES AND MODULES:** `backend/app/services/scanner.py` (append), reference `app/services/embeddings.py`, `app/database.py`.

**DEPENDENCIES:** Prompt 01 (scoring) — `score_report`, `build_summary` used here. DB methods already exist.

**EDGE CASES:** Empty repo (no files) → complete with 0 findings; `scanned_files` empty → skip LLM; OpenAI outage/refusal/length → rules-only; git missing → `ScanAbortError`; timeout → `TimeoutError` wrapped as failed; Windows lock on temp dir → `_rmtree_retry` retries.

**ERROR HANDLING:** Every failure path must leave the run in `failed` with a readable `error`; never raise out of `run_scan`.

**SECURITY:** URL re-validated defensively inside `run_scan`; temp dir cleanup always; deterministic ids prevent duplicate incidents on rescan; no secrets logged.

**TESTING:** No test framework yet; run the verify snippet: clear key → `llm_review` returns `([], "rules_only")`; `merge_findings` drops duplicates; `inspect.iscoroutinefunction(run_scan)` is True.

**VALIDATION:**
```
python -c "import app.services.scanner as s; s.settings.OPENAI_API_KEY=''; assert s.llm_review([('a.py','x')])==([],'rules_only'); m=s.merge_findings([{'file':'a','line':1,'category':'secrets'}],[{'file':'a','line':1,'category':'secrets'}]); assert len(m)==1; import inspect; assert inspect.iscoroutinefunction(s.run_scan); print('orchestrator ok')"
```

**NON-GOALS:** No routes, no main.py changes, no frontend, no tests directory.

**COMPLETION CRITERIA:** All functions exist with exact names; verify snippet passes; module imports cleanly.

**FINAL REPORT:** Functions added, verification output, failure-mode handling confirmed.

---

### Prompt 03 — Scan API routes + main.py wiring (P7)

**ROLE:** Senior FastAPI backend engineer.

**CONTEXT:** P6 is done (orchestrator exists in `scanner.py`). The frontend data layer (`api.ts:98-113`, `hooks.ts:45-84`) already calls `/api/v1/scans` endpoints that don't exist yet — this prompt makes the frozen contract (PLAN.md §4) real.

**OBJECTIVE:** Create `backend/app/api/v1/routes/scans.py` with 4 endpoints and register it in `main.py`, plus the lifespan orphan-sweep.

**CURRENT STATE:** `main.py` imports/routes health, logs, incidents, anomalies, search (lines 10, 37–41); lifespan at 14–19. No scans router (route-probe verified).

**REQUIREMENTS (contract):**
- `POST /api/v1/scans` → 201 `ScanRun`: `validate_repo_url` synchronous (400 on `ValueError`), `active_scan_for_repo` → 409 duplicate, `insert_scan_run`, `background_tasks.add_task(run_scan, run["id"], scan.repo_url)`.
- `GET /api/v1/scans?limit&offset` → 200 `ScanRun[]` (finding_count populated).
- `GET /api/v1/scans/{scan_id}` → 200 with `findings`; 404.
- `POST /api/v1/scans/{scan_id}/findings/{finding_id}/incident` → 201 `IncidentResponse`; 404 scan/finding; 409 already promoted.
- `main.py`: register router with `prefix=settings.API_V1_PREFIX, tags=["scans"]`; lifespan: `await sweep_orphaned_scans(db)` after `get_db()`; static frontend mount stays last.

**IMPLEMENTATION GUIDELINES:** Copy conventions from `routes/incidents.py` exactly (router pattern, `response_model` on decorator, `db = await get_db()`, try/except → 500 on writes, 404 pattern). Response model `ScanResponse`; findings detail returns `ScanRun` + findings.

**FILES AND MODULES:** `backend/app/api/v1/routes/scans.py` (new), `backend/app/main.py` (modify).

**DEPENDENCIES:** Prompt 02 (run_scan, promote_finding_to_incident, sweep_orphaned_scans, validate_repo_url).

**EDGE CASES:** Missing scan → 404; finding not belonging to scan → 404; double promote → 409; empty/invalid URL → 400; duplicate concurrent scan → 409.

**ERROR HANDLING:** Follow incidents.py try/except pattern for writes; 500 with detail on unexpected DB errors.

**SECURITY:** URL validation is server-side enforced (never trust client); dedupe guards prevent incident spam.

**TESTING:** None yet (Prompt 04 adds tests). Verify via imports and route listing.

**VALIDATION:**
```
python -c "from app.main import app; paths={r.path for r in app.routes if hasattr(r,'path')}; assert '/api/v1/scans' in paths and '/api/v1/incidents' in paths; print('routes ok')"
python -c "import app.api.v1.routes.scans as r; print([x.path for x in r.router.routes])"
```

**NON-GOALS:** Do not modify scanner.py, database.py, or models.py. Do not create tests yet.

**COMPLETION CRITERIA:** 4 endpoints registered; route assertions pass; existing routes untouched; sweep runs at startup.

**FINAL REPORT:** Files changed, routes list, verification output.

---

### Prompt 04 — Backend test suite (P8)

**ROLE:** Test engineer, pytest + pytest-asyncio + FastAPI TestClient specialist.

**CONTEXT:** PLAN.md P8 specifies a 5-module suite. `backend/tests/` does not exist. All runtime code from Prompts 01–03 exists. Suite must run **without** Postgres, OpenAI, or network (uses a FakeDatabase + monkeypatched `run_scan`).

**OBJECTIVE:** Create `backend/pytest.ini`, `backend/tests/__init__.py`, `backend/tests/conftest.py`, and 5 test modules: `test_scanner_url_validation.py`, `test_scanner_rules.py`, `test_scanner_score.py`, `test_scanner_llm_parse.py`, `test_scans_api.py`.

**CURRENT STATE:** Scanner functions exist (validation, rules, score, merge, llm fallback). Routes exist. `pytest`, `pytest-asyncio`, `httpx` already in `backend/requirements.txt` and installed in venv.

**REQUIREMENTS (from PLAN.md P8):**
- `pytest.ini`: `asyncio_mode = auto`, `asyncio_default_fixture_loop_scope = function`, `testpaths = tests`.
- `conftest.py`: dict-backed `FakeDatabase` (insert, insert_batch, get_by_id, update_by_id, insert_scan_run, update_scan_status, get_scan_runs, get_scan_run, get_scan_findings, mark_finding_promoted, finding_has_incident, active_scan_for_repo); fixture patching **`app.api.v1.routes.scans.get_db`** (module symbol, not `app.database.get_db`); `TestClient(app)` **without** context manager (skip lifespan); `fake_run_scan` async stub recording calls.
- URL tests: parametrized passes (github/gitlab/bitbucket https) and rejects (trailing dot, evil host, creds, `..`, `%2e%2e`, file://, ssh://, http://, git://, leading dash, empty, >2048, unknown host).
- Rules tests: fixture-pair (positive + near-miss negative) per rule — AWS key base32, OpenAI `T3BlbkFJ` marker, `ghp_`+36, PEM banner, entropy gate, DB URL creds, `.env` vs `.env.example`, NEXT_PUBLIC, eval literal→medium/variable→high, SQL concat, CORS `*`+credentials→high / `*` alone→medium, SECRET_KEY blocklist→high/entropy→medium, Supabase-no-RLS with/without `.sql` policy.
- Score tests: 100/A empty; 75/B one critical; 50/C one each; 0/F four criticals; grade boundaries 90/89/75/74/50/49/25/24; sub-scores per category; `_category_of` keyword mapping.
- LLM tests: monkeypatch `app.services.scanner._llm_client` fake; valid parse → ok; refusal → rules_only; exception → rules_only; no key → rules_only.
- API tests: 201 queued + recorded background call; 400 bad URL (run_scan not called); 409 duplicate; GET list/detail (with findings); 404 missing; promote 201 → promoted flag; second promote 409; wrong scan_id → 404.

**IMPLEMENTATION GUIDELINES:** Pure unit tests, deterministic, no real I/O. Use the existing venv.

**FILES AND MODULES:** `backend/pytest.ini`, `backend/tests/*` (6 new files).

**DEPENDENCIES:** Prompts 01–03. Postgres NOT required (FakeDatabase).

**EDGE CASES:** Ensure tests assert exact severity values (medium vs high) per the handler logic; `%2e%2e` rejection proves the `unquote` fix.

**ERROR HANDLING:** Tests assert `pytest.raises(ValueError)` where relevant.

**SECURITY:** Test suite itself is offline; no keys needed.

**TESTING/VALIDATION:** From `backend/` with venv: `python -m pytest -q` → all green (target: ≥45 tests).

**NON-GOALS:** Do not add production code; do not test frontend; do not require a live DB.

**COMPLETION CRITERIA:** `pytest -q` green; suite runs with no DB/network; every rule has positive+negative coverage.

**FINAL REPORT:** Tests created, count, pass/fail output.

---

### Prompt 05 — Frontend scans UI (P5)

**ROLE:** Senior Next.js 14 / TypeScript / Tailwind frontend engineer.

**CONTEXT:** PLAN.md P5. The data layer already exists (`types.ts`, `api.ts`, `hooks.ts` — `useScans`, `useScan`, `useCreateScan`, `usePromoteFinding` with polling that auto-stops on terminal status). Backend endpoints now exist (Prompt 03). The `/scans` page, components, and sidebar link are missing.

**OBJECTIVE:** Create `frontend/src/components/scans/ScanForm.tsx`, `ScanList.tsx`, `ScanDetail.tsx`, `frontend/src/app/scans/page.tsx`, and add the sidebar entry.

**CURRENT STATE:** Design system (`ui/Badge`, `ui/Card`, `ui/Button`, `LoadingSkeleton`), table pattern (`RecentIncidents.tsx`), page skeleton (`incidents/page.tsx`), input styling (`Topbar.tsx:33-40`) all exist. Sidebar links at `Sidebar.tsx:11-17`. **No scans UI exists** (glob-verified).

**REQUIREMENTS (PLAN.md P5, exact):**
- `ScanForm`: client-side validation (https, allowlisted host, no `@`/`..`), inline error, disabled while pending, `createScan.mutate(data, { onSuccess: (scan) => { setRepoUrl(""); onCreated?.(scan); } })` (per-call onSuccess — mandatory).
- `ScanList`: RecentIncidents-style table; columns Repo/Status/Score/Grade/Findings/Created; status badge map (queued→info, running→warn+pulse, completed→success, failed→danger); score color ≥80 success / ≥50 warn / else danger; row click `onSelect`; selected highlight; skeleton loading; empty state.
- `ScanDetail`: props `{scanId}`; `useScan` + `usePromoteFinding`; header (repo, status, score, grade, summary, total_files); sub-scores from `metadata` (`secrets_score`/`code_score`/`config_score` via `Number(...)`, `—` if absent); findings list with severity badge, category chip, `file:line`, rule_id, `<details>` evidence — **plain text only, never `dangerouslySetInnerHTML`**; description/remediation; promote button → "Promoted" disabled badge when `promoted_to_incident`.
- `app/scans/page.tsx`: `"use client"`, header "Security Scans" + running-count badge, grid: ScanForm card + ScanList + ScanDetail (client-side `selectedId` state); placeholder "Select a scan to view findings".
- Sidebar: add `{ href: "/scans", label: "Security Scans", icon: Shield }` after Logs.

**IMPLEMENTATION GUIDELINES:** Mirror existing component conventions exactly (class names, `text-[13px]`, `font-mono`, etc.). No new dependencies.

**FILES AND MODULES:** `frontend/src/components/scans/*` (3 new), `frontend/src/app/scans/page.tsx` (new), `frontend/src/components/layout/Sidebar.tsx` (modify).

**DEPENDENCIES:** Prompt 03 (API contract live). Frontend data layer already done.

**EDGE CASES:** Failed scan → error card with message; empty findings → empty state; null score/grade → `—`; evidence with attacker-controlled strings rendered as text.

**ERROR HANDLING:** `mutate` error → inline error message; query errors → error state text.

**SECURITY:** No `dangerouslySetInnerHTML` anywhere in the new code.

**TESTING/VALIDATION:** `cd frontend; npx tsc --noEmit; npm run lint; npm run build` — all must pass.

**NON-GOALS:** No backend changes; no new pages beyond `/scans`; no auth.

**COMPLETION CRITERIA:** tsc/lint/build pass; page renders list/detail; polling stops on terminal status.

**FINAL REPORT:** Files created/modified, build output, remaining issues.

---

### Prompt 06 — Targeted backend bug fixes

**ROLE:** Senior FastAPI backend engineer.

**CONTEXT:** Two verified runtime bugs in the core MVP API (independent of the scan feature).

**OBJECTIVE:**
1. Fix `search.py` — results currently carry the **last-scanned row's** `service`/`level` on every result (variables `svc`/`lvl` assigned in the scoring loop, reused in the serialization loop). Compute per-row values inside the results loop.
2. Fix `logs.py` upload — `inserted` is unbound when `batch` is empty (all lines unparseable / empty file) → `UnboundLocalError` → 500. Initialize `inserted = 0` before the loop and return `logs_processed=0` properly.

**CURRENT STATE:** `search.py:36-65` (buggy serialization), `logs.py:42-102` (buggy empty-batch path).

**IMPLEMENTATION GUIDELINES:** Minimal surgical diffs. Preserve response shapes. Remove the dead `if isinstance(ts, str): ts = ts` no-op while in the area.

**FILES AND MODULES:** `backend/app/api/v1/routes/search.py`, `backend/app/api/v1/routes/logs.py`.

**DEPENDENCIES:** None.

**EDGE CASES:** Search with mixed service/level filters; upload of empty file; upload of only-unparseable lines; upload with zero lines (whitespace-only).

**ERROR HANDLING:** Upload must return `LogUploadResponse(logs_processed=0, logs_failed=N, errors=[...])`, never 500.

**SECURITY:** No change to auth/validation behavior.

**TESTING:** Manual curl-level verification (requires DB) OR a lightweight import-level smoke check; note that the full test suite arrives in Prompt 04 — if Prompt 04 already ran, add regression cases there instead of duplicating.

**VALIDATION:** Code trace + (if DB available) POST an empty file → expect 200 `{logs_processed: 0}`; POST search with a filter → verify result rows carry correct service/level.

**NON-GOALS:** No refactors, no formatting churn, no changes to other routes.

**COMPLETION CRITERIA:** Both bugs eliminated; unchanged behavior elsewhere; lint/typecheck unaffected.

**FINAL REPORT:** Diffs, verification method/results.

---

### Prompt 07 — Navigation reconciliation

**ROLE:** Next.js frontend engineer.

**CONTEXT:** The UI links to pages that don't exist: `/analytics` (homepage `page.tsx:86`, Sidebar, Topbar "Settings" item), `/settings` (Sidebar, profile drawer), `/incidents/[id]` (RecentIncidents row links + dashboard "View all"). ARCHITECT.md's page map lists these as intended pages, but the MVP scope only delivered 4 pages.

**OBJECTIVE (decision required — ask the user or default as shown):** Default approach: build lightweight but real pages backed by existing APIs where cheap, and remove links that can't be backed. Concretely: (a) `/incidents/[id]` detail page — read-only incident detail via `getIncidentById` (API exists), with status/severity badges; (b) `/analytics` and `/settings` — simple placeholder pages (consistent card + "coming soon" copy) so nav never 404s; keep the route map honest. Alternatively remove the nav entries — do not leave 404 links.

**CURRENT STATE:** `frontend/src/app/` has only `page.tsx`, `dashboard/`, `incidents/`, `logs/`. API client has `getIncidentById`/`updateIncident` already.

**IMPLEMENTATION GUIDELINES:** Reuse `Card`, `Badge`, `LoadingSkeleton`, `useIncident`-style patterns. Create dynamic route `frontend/src/app/incidents/[id]/page.tsx` with `params` prop (Next 14 pattern). Wire "New Incident" and "View all" buttons to real destinations (dashboard/incidents pages) instead of dead buttons where feasible.

**FILES AND MODULES:** `frontend/src/app/incidents/[id]/page.tsx` (new), `frontend/src/app/analytics/page.tsx` (new), `frontend/src/app/settings/page.tsx` (new), possibly `lib/api.ts`/`hooks.ts` additions (e.g., `getIncidentById` hook).

**DEPENDENCIES:** Backend `GET /api/v1/incidents/{id}` (exists). No DB needed for placeholders.

**EDGE CASES:** Missing incident id → 404 state; loading skeleton; API error state.

**ERROR HANDLING:** Not-found and error states per ARCHITECT.md four-state convention (loading/empty/error/success).

**SECURITY:** No auth changes; render incident fields as text.

**TESTING/VALIDATION:** `npx tsc --noEmit; npm run lint; npm run build`; manual nav walk of every link in Sidebar/Homepage/Profile → no 404s.

**NON-GOALS:** No backend changes; no full analytics charts (placeholders only); no auth.

**COMPLETION CRITERIA:** Zero broken nav links; detail page renders real data when API is up; build green.

**FINAL REPORT:** Pages created, nav walk results.

---

### Prompt 08 — Deployment and infrastructure fixes

**ROLE:** DevOps engineer / full-stack deployer.

**CONTEXT:** Current deployment config cannot work: `render.yaml` builds root `requirements.txt` (a stale manifest referencing supabase/langchain/torch) and runs `uvicorn app.main:app` from repo root where `app/` doesn't exist; `main.py:43-44` statically mounts the raw Next.js source tree; `docker-compose.yml` has no frontend service; no git history exists.

**OBJECTIVE:**
1. Fix `render.yaml`: add `rootDir: backend`, build `pip install -r requirements.txt` from `backend/`, start `uvicorn app.main:app --host 0.0.0.0 --port $PORT`, add `OPENAI_API_KEY` env placeholder, ensure `DATABASE_URL` from the managed DB add-on.
2. Fix `main.py`: remove (or gate behind `ENVIRONMENT == "development"`) the static frontend mount so prod serves only the API; add a proper `ENVIRONMENT=production` guard. Recommend the supported prod topology: frontend on Vercel (or `next start` separately) proxying `/api` to the backend.
3. Consolidate dependencies: root `requirements.txt` (torch/langchain/supabase/hdbscan…) is unused and misleading — replace with a pointer note or delete in favor of `backend/requirements.txt`; ensure `render.yaml`/README reference only `backend/requirements.txt`.
4. `docker-compose.yml`: optionally add a frontend service (`npm run start` after build) and pass scan env vars; keep dev-only.
5. Init git: `git init` (already a repo, no commits) — commit the current baseline with a clear message and a proper `.gitignore`; do NOT commit `.env` (already ignored).

**CURRENT STATE:** Files as described; verify `docker` not installed locally (environment note — do not require Docker for this task's validation).

**IMPLEMENTATION GUIDELINES:** Minimal, targeted edits. Preserve existing behavior in dev (`ENVIRONMENT=development` keeps the current mount or removes it — prefer removing the mount entirely and documenting `npm run dev` as the frontend dev path, since the mount is non-functional anyway).

**FILES AND MODULES:** `render.yaml`, `backend/app/main.py`, root `requirements.txt`, `docker-compose.yml`, README quick-start, `.gitignore`.

**DEPENDENCIES:** None (independent of scan feature).

**EDGE CASES:** Render free-tier no-op `ipAllowList`; `$PORT` injection; missing `OPENAI_API_KEY` (scan degrades to rules-only — already handled).

**ERROR HANDLING:** Deploy must fail fast with clear logs if misconfigured — validate by linting YAML and simulating the start command.

**SECURITY:** Never commit `.env`; never print keys; CORS remains for Prompt 09.

**TESTING/VALIDATION:** `python -c "from app.main import app"` still imports; YAML parses (`python -c "import yaml; yaml.safe_load(open('render.yaml'))"`); `docker-compose config` if docker available (else note as requires-verification); git status clean after baseline commit.

**NON-GOALS:** No code refactors; no auth; no CI pipeline creation.

**COMPLETION CRITERIA:** render.yaml corrected with rootDir; static mount resolved; single dependency manifest; baseline committed.

**FINAL REPORT:** Files changed, validation results, git commit hash.

---

### Prompt 09 — Security hardening

**ROLE:** Security-focused backend engineer.

**CONTEXT:** The API has no auth (out of MVP scope — document as known limitation), but several concrete hardening items are cheap and high-value.

**OBJECTIVE:**
1. Fix CORS: when `allow_origins=["*"]`, disable `allow_credentials` (or require explicit origins in production via env). Align with `ENVIRONMENT`.
2. Bound anomaly inputs: `window_minutes` (1–1440) and `contamination` (0.01–0.5) via `Query(ge=, le=)` and model validators.
3. Startup resilience: lifespan should tolerate DB-down at boot in dev (log + continue) or fail with a clear message in prod — at minimum, wrap `get_db()`/sweep so a down DB produces a helpful error instead of a crash loop.
4. Add security headers middleware (X-Content-Type-Options, Referrer-Policy, X-Frame-Options) — cheap, no deps.
5. Document the "no auth" posture in README security section (single-team assumption, deploy behind VPN/SSO in production).

**CURRENT STATE:** `config.py` CORS_ORIGINS `["*"]`; `main.py` CORSMiddleware with `allow_credentials=True`; anomalies accept any values; lifespan connects unconditionally.

**IMPLEMENTATION GUIDELINES:** Small, additive middleware/validation changes; keep response shapes identical.

**FILES AND MODULES:** `backend/app/config.py`, `backend/app/main.py`, `backend/app/models.py`, `backend/app/api/v1/routes/anomalies.py`, README.

**DEPENDENCIES:** None.

**EDGE CASES:** Preflight OPTIONS with credentials; anomaly call with zero logs (already 404); DB down at boot.

**ERROR HANDLING:** DB-down at boot → logged warning + healthy-app-import in dev; 500 with detail in prod.

**SECURITY:** This task IS the security work: CORS correctness, header hardening, input bounds.

**TESTING/VALIDATION:** `python -c "from app.main import app"` imports; route probes unchanged; (if DB available) anomaly requests with out-of-range params → 422.

**NON-GOALS:** No authentication implementation (separate roadmap item); no RLS; no rate limiting (document as future).

**COMPLETION CRITERIA:** CORS safe; bounds enforced; headers present; startup resilient; docs note auth posture.

**FINAL REPORT:** Changes, probes, remaining risks.

---

### Prompt 10 — Final QA, docs sync, and release prep

**ROLE:** QA lead / technical writer.

**CONTEXT:** All prompts 01–09 done. The project ships with stale docs (README claims Supabase/LangChain/postmortems; ARCHITECT.md dark theme vs light UI; AGENTS.md testing section references nonexistent tests).

**OBJECTIVE:**
1. Sync docs to reality: README (actual features, asyncpg + Postgres, scan feature usage, accurate quick start), QUICK_START_GUIDE (fix "cp .env.example .env" root references), AGENTS.md (mark scan feature status, verify test commands match new suite), DATABASE_SCHEMA.md already accurate.
2. Full regression pass: backend boots with DB; all route groups respond; frontend build + lint + typecheck; scans E2E (submit `https://github.com/octocat/Hello-World`, poll to completed, verify score/grade/findings/temp-dir cleanup; with key empty → rules-only path; restart mid-scan → sweep marks failed).
3. Fill `.planning/SCAN-SUMMARY.md` per PLAN.md §9 (files created, decisions, test results, deviations).
4. Final commit of the completed feature set.

**CURRENT STATE:** All prior prompts applied; DB availability depends on environment (requires Postgres + optionally an OpenAI key for full E2E).

**IMPLEMENTATION GUIDELINES:** Docs-first; update only what changed. Mark unverifiable items explicitly "requires verification" rather than asserting.

**FILES AND MODULES:** README.md, QUICK_START_GUIDE.md, AGENTS.md, ARCHITECT.md (add "reference design — implemented UI differs" note), `.planning/SCAN-SUMMARY.md` (new), any docs referenced by tests.

**DEPENDENCIES:** Prompts 01–09.

**EDGE CASES:** E2E must cover rules-only mode; DB-unavailable steps documented as conditional.

**ERROR HANDLING:** QA findings recorded in SCAN-SUMMARY, not fixed silently.

**SECURITY:** Confirm no secrets in committed files (grep for `sk-`, `ghp_`, AKIA in repo).

**TESTING/VALIDATION:** `pytest -q` green from `backend/`; `npm run lint && npm run build` green; manual E2E walk documented.

**NON-GOALS:** No new features; no scope expansion.

**COMPLETION CRITERIA:** Docs match implementation; all suites green; E2E recorded; commit pushed-ready.

**FINAL REPORT:** Docs diff summary, test/E2E results, remaining issues, commit hash.

---

## H. Final Completion Checklist

**Features:**
- [ ] Scan submit/list/detail/promote end-to-end
- [ ] Rules-only degradation verified
- [ ] Auto-incident on critical/high
- [ ] Rescan dedupe (sha1 ids)
- [ ] Orphan sweep
- [ ] Log upload empty-file fix
- [ ] Search service/level fix
- [ ] Incident detail page

**Frontend:**
- [ ] `/scans` page + 3 components
- [ ] No 404 nav links
- [ ] Four-state UX (loading/empty/error/success) on data components
- [ ] lint/build/typecheck green
- [ ] Sub-score display
- [ ] Evidence rendered as plain text

**Backend:**
- [ ] Scoring functions
- [ ] LLM review w/ Structured Outputs + fallback
- [ ] `run_scan` Shape B
- [ ] 4 scan endpoints
- [ ] main.py registration + sweep
- [ ] CORS/header hardening
- [ ] Anomaly param bounds

**Database:**
- [ ] Postgres reachable at `DATABASE_URL`
- [ ] Schema auto-create verified (all 5 tables)
- [ ] Leftover SQLite `app.db` removed or ignored

**APIs:**
- [ ] Contract §4 frozen & tested (201/400/404/409)
- [ ] Regression: logs/incidents/anomalies/search/health intact

**Auth/Authorization:**
- [ ] Documented single-team posture
- [ ] (Roadmap) login/users/RLS if multi-user required

**Validation:**
- [ ] URL allowlist server-side
- [ ] Pydantic bounds everywhere
- [ ] Evidence truncation+masking

**Error handling:**
- [ ] Never-500 on user input
- [ ] Scan failures → `failed` status + readable error
- [ ] DB-down startup resilience

**Security:**
- [ ] No secrets in repo (grep)
- [ ] No `dangerouslySetInnerHTML`
- [ ] CORS safe
- [ ] Clone SSRF guards intact

**Testing:**
- [ ] pytest suite ≥45 tests green offline
- [ ] Fixture pairs per rule
- [ ] LLM degrade matrix

**Performance:**
- [ ] Walk caps (50MB/2000 files)
- [ ] LLM input budget
- [ ] Polling stops on terminal status

**Responsiveness/Accessibility:**
- [ ] Mobile layout sanity check on new pages
- [ ] Semantic buttons/aria on new controls
- [ ] Keyboard nav on scans form

**Deployment:**
- [ ] `render.yaml` rootDir fixed
- [ ] Static mount resolved
- [ ] Single requirements manifest
- [ ] Baseline committed
- [ ] (Conditional) Render deploy smoke test

**Documentation:**
- [ ] README/QUICK_START/AGENTS synced
- [ ] ARCHITECT.md reality note
- [ ] `.planning/SCAN-SUMMARY.md` written

**Final QA:**
- [ ] `pytest -q` green
- [ ] `npm run build` green
- [ ] E2E walk recorded
- [ ] Git history clean

---

## Audit Method Note

All findings were verified by reading the actual files (full reads of all 20 source files, all 14 docs), runtime probes (venv import checks, route listing, DB connectivity, lint/typecheck), and grep verification of missing symbols. Items marked "requires verification" (frontend production build, Render deploy, Docker compose run) could not be executed in this environment because Docker is not installed and Postgres is not running.