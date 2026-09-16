# Security Scan Feature — Implementation & QA Summary

Phase: `vibe-code-security-scan` (Prompt 03–09 implementation; Prompt 10 final QA & release prep)
Date: 2026-08-14
Status: **RELEASE-READY** (with documented `REQUIRES VERIFICATION` items)

---

## 1. Files Created

### Backend
| File | Purpose |
|---|---|
| `backend/app/services/scanner.py` | Scan engine: URL validation, hardened clone, walker, 20-rule engine, scoring, LLM review, orchestrator, orphan sweep |
| `backend/app/api/v1/routes/scans.py` | `/api/v1/scans` API surface (4 routes) |
| `backend/app/middleware.py` | SecurityHeadersMiddleware (Prompt 09) |
| `backend/pytest.ini` | pytest config (`asyncio_mode = auto`) |
| `backend/tests/__init__.py` | Test package marker |
| `backend/tests/conftest.py` | FakeDatabase + client + fake_run_scan fixtures |
| `backend/tests/test_scanner_url_validation.py` | 11 URL-validation tests |
| `backend/tests/test_scanner_rules.py` | 45 rules-engine tests (fixture pairs) |
| `backend/tests/test_scanner_score.py` | 12 scoring/grade/sub-score tests |
| `backend/tests/test_scanner_llm_parse.py` | 7 LLM parse/fallback tests |
| `backend/tests/test_scans_api.py` | 18 API contract + run_scan integration tests |
| `backend/tests/test_security.py` | 17 security-hardening tests (Prompt 09) |

### Frontend
| File | Purpose |
|---|---|
| `frontend/src/components/scans/ScanForm.tsx` | URL submission with client-side validation |
| `frontend/src/components/scans/ScanList.tsx` | Polled scan history table |
| `frontend/src/components/scans/ScanDetail.tsx` | Findings detail + promote-to-incident |
| `frontend/src/app/scans/page.tsx` | `/scans` page |

### Planning / Docs
| File | Purpose |
|---|---|
| `.planning/PLAN.md`, `RESEARCH.md`, `PATTERNS.md`, `PLAN-CHECK.md` | Phase planning artifacts |
| `.planning/SCAN-SUMMARY.md` | This file (PLAN.md §9) |

## 2. Files Modified

| File | Change |
|---|---|
| `backend/app/config.py` | 9 scan settings + `cors_allow_credentials` property |
| `backend/app/database.py` | `scan_runs`/`scan_findings` tables + 8 CRUD methods |
| `backend/app/models.py` | ScanCreate/ScanFinding/ScanRun/ScanResponse + anomaly param bounds |
| `backend/app/main.py` | scans router, lifespan orphan sweep, CORS hardening, security middleware, env-aware startup |
| `backend/app/api/v1/routes/anomalies.py` | `window_minutes`/`contamination` bounds (422) |
| `backend/requirements.txt` | pytest, pytest-asyncio, httpx |
| `backend/.env.example` | DATABASE_URL + CORS + all scan vars (Supabase vars removed) |
| `.gitignore` | `.scan-tmp/`, venv, build artifacts |
| `AGENTS.md` | Stack, structure, commands, scan feature, tests |
| `DATABASE_SCHEMA.md` | §4 scan_runs, §5 scan_findings sections |
| `frontend/src/lib/types.ts` / `api.ts` / `hooks.ts` | Scan types, API functions, polling hooks |
| `frontend/src/components/layout/Sidebar.tsx` | "Security Scans" nav entry |
| `README.md`, `QUICK_START_GUIDE.md`, `ARCHITECT.md` | Prompt 10 documentation sync |

## 3. Implementation Decisions (vs. alternatives)

- **Shape B background execution** — `run_scan` is async; blocking git/scan work offloaded via `asyncio.to_thread`; FastAPI `BackgroundTasks` triggers it. No Celery/ARQ.
- **Deterministic finding IDs** — `sha1(repo_url|rule_id|file|line)` so `finding_has_incident` metadata containment dedupes across rescans (fresh uuid4s would never match).
- **Rules-only is first-class** — no key / refusal / length / any exception → `([], "rules_only")`; scan never hard-fails.
- **Structured Outputs** — `client.beta.chat.completions.parse` with a Pydantic `LLMReview` schema; no JSON-in-prompt parsing.
- **Windows-safe git** — `Popen` + DEVNULL (no pipe-deadlock), `taskkill /F /T` tree-kill on timeout, `_rmtree_retry` for locked temp dirs.
- **Evidence hygiene** — truncation ≤200 chars + prefix masking (`sk-****` style) before persistence.
- **No FK constraints** on `scan_findings.scan_id` — consistent with the codebase's existing loose coupling.
- **run_scan signature** — deviates from PLAN.md §P6 (see §10): the route creates the run row; `run_scan(scan_id, repo_url)` transitions that exact row (Prompt 10 fixed the original mismatch, see §11 QA-01).

## 4. Backend Implementation

- `validate_repo_url`: https-only, host allowlist (github.com/gitlab.com/bitbucket.org, exact match), no credentials, no trailing dot, no `..` (percent-decoded), no leading `-`, ≤2048 chars.
- `clone_repo`: `git -c protocol.ext.allow=never -c protocol.file.allow=never clone --depth 1 --single-branch --no-tags --no-recurse-submodules -- <url> <dest>` (list args, `--` separator).
- Walker: skip dirs (`node_modules`, `.git`, `vendor`, …), skip binary (NUL-byte probe), caps `MAX_REPO_SIZE_MB` / `MAX_SCAN_FILES` (abort → failed).
- Rules: 20 rules (secrets ×9, code ×6, config ×5) with handlers: entropy gate (≥3.5 bits/char), secret blocklist, CORS/creds/SQL-concat correlation, supabase-no-RLS repo-level correlation, `.env.example` exemption, test-path skips.
- Scoring: `max(0, 100 − Σ weights)` with weights critical 25 / high 15 / medium 7 / low 3; grade A ≥90, B ≥75, C ≥50, D ≥25, F <25; per-category sub-scores.
- Orchestrator: `run_scan` transitions queued → running → completed/failed, persists findings, auto-creates incidents for critical/high (deduped), cleans temp dir in `finally`, semaphore `SCAN_MAX_CONCURRENT`.
- Startup sweep: queued/running → `failed` with `server restarted mid-scan`.
- Env-aware startup: dev continues without DB (health `degraded`); production fails fast.

## 5. Frontend Implementation

- `/scans` page: ScanForm (client-side URL validation), ScanList (polled, fn-form `refetchInterval` stops at terminal status), ScanDetail (score/grade/sub-scores, evidence in `<details>`, plain-text evidence — no `dangerouslySetInnerHTML`), promote button flips to "Promoted".
- Sidebar entry "Security Scans" with Shield icon; `useScans`/`useScan`/`useCreateScan`/`usePromoteFinding` hooks invalidate the correct query keys.

## 6. API Routes (Prompt 03 contract)

| Method | Path | Behavior |
|---|---|---|
| POST | `/api/v1/scans` | 201 queued run; 400 invalid URL; 409 duplicate active scan; 500 DB write failure |
| GET | `/api/v1/scans` | 200 list with `finding_count` (limit 1–500, offset) |
| GET | `/api/v1/scans/{id}` | 200 run + findings; 404 |
| POST | `/api/v1/scans/{id}/findings/{fid}/incident` | 201 incident; 404 scan/finding; 409 already promoted |

## 7. Test Coverage

| Suite | Tests | Result |
|---|---|---|
| Backend (all modules) | **163** | **PASS** (2.01s → 0.88s) |
| — URL validation | 11 | PASS |
| — Rules engine | 45 | PASS |
| — Scoring | 12 | PASS |
| — LLM parse/fallback | 7 | PASS |
| — Scans API | 18 | PASS |
| — Security hardening | 17 | PASS |
| — Logs/search routes | 7 | PASS |
| Frontend `npx tsc --noEmit` | — | PASS |
| Frontend `npm run lint` | — | PASS |
| Frontend `npm run build` | — | PASS (one non-blocking recharts container-width warning on /dashboard) |

## 8. E2E Results

| Check | Result |
|---|---|
| Backend boots without DB (dev) | **PASS** — warning logged, `/health` → `{"status":"degraded","database":"disconnected"}` |
| Backend boots in production without DB | **PASS (unit)** — `test_lifespan_production_fails_when_db_unavailable` |
| Scan pipeline on real repo (octocat/Hello-World): validate → clone → walk → rules → score → summary | **PASS** — clone OK (git 2.54, network OK); 0 scannable files (README-only repo per include rules, matches PLAN.md §6 step 5 expectation); score 100/A; summary generated |
| Temp-dir cleanup on Windows | **PASS (with note)** — transient file lock on first attempt observed; retry succeeded; `_rmtree_retry` (3 attempts) is the implemented mechanism |
| **Full DB-backed E2E** (HTTP submit → queued → running → completed, findings persisted, counts, incidents, list/detail) | **REQUIRES VERIFICATION** — no PostgreSQL/Docker on this machine (localhost:5432 refused; docker not installed). Exact validation performed instead: route → `run_scan` integration simulated against FakeDatabase + real clone/walk steps (see QA-01); 4 new integration tests cover transitions, failures, findings persistence, auto-promote |
| **Rules-only E2E** (OPENAI_API_KEY empty, DB-backed) | **REQUIRES VERIFICATION** — `backend/.env` has an empty `OPENAI_API_KEY`; the no-key branch of `llm_review` is unit-tested (`test_scanner_llm_parse.py`), but the full DB-backed rules-only run could not be exercised without Postgres |
| **LLM review E2E** (key set) | **REQUIRES VERIFICATION** — no key available; mocked-parse tests cover valid/refusal/length/exception branches |
| **Restart recovery / orphan sweep** | **REQUIRES VERIFICATION (E2E)** — real restart mid-scan could not be reproduced without Postgres. Unit coverage: sweep SQL/behavior verified in `test_lifespan_runs_sweep_when_db_available`; status transition code verified by integration tests. Do **not** claim passed |

## 9. Deployment Changes & Security Hardening

- `render.yaml`: backend web service (`rootDir: backend`, uvicorn start, `ENVIRONMENT=production`) + managed PostgreSQL 16; `OPENAI_API_KEY` sync:false.
- `docker-compose.yml`: PostgreSQL 16 + backend service with `DATABASE_URL`.
- Security headers middleware (`X-Content-Type-Options`, `Referrer-Policy`, `X-Frame-Options`) — **verified live via curl** on `/health`.
- CORS: wildcard never allows credentials (`cors_allow_credentials`); production + wildcard logs warning. Verified by tests + live response.
- Input bounds on anomaly params (422). Env-aware startup resilience.
- Scan hardening: allowlist, `--` separator, protocol flags, caps, evidence masking/truncation, retry cleanup, deterministic dedupe, duplicate-submission 409, concurrency semaphore.
- **Secret scan (Prompt 10):** `backend/.env` untracked + gitignored (`git ls-files .env` → empty; `git check-ignore` → hit). All `sk-`/`ghp_`/`AKIA` matches inspected: regex definitions in `scanner.py`, fake fixture values in tests (AWS doc example key, repeated-char tokens), planning docs, `.env.example` placeholder `sk-your-key-here`. **No real secrets committed.**

## 10. Deviations from PLAN.md

| Plan (P#) | Planned | Implemented | Impact |
|---|---|---|---|
| P6 Task 6.2 | `run_scan(scan_id, repo_url)`; route adds task with `(run["id"], repo_url)` | Originally implemented `run_scan(repo_url, name=None)` that inserted its own run — **signature/route mismatch** | **Critical integration bug (QA-01)** — fixed in Prompt 10 to the plan shape |
| P6 Task 6.2 | `sweep_orphaned_scans(db)` | `sweep_orphaned_scans()` fetches its own `get_db()` | Cosmetic; caller in `main.py` matches |
| P6 Task 6.2 | inline promote in run_scan loop | extracted `_finalize_scan` helper (findings persist + dedupe + promote + metadata) | Structure only; behavior equivalent |
| P6 Task 6.1 | LLM prompt per RESEARCH.md verbatim + max_tokens 4000 | Prompt summarized (same orientation), `max_tokens=4096`, `LLMReview` has no summary field | Prompt drift is minor; Structured Outputs contract identical |
| P8 Task 8.3 | 14 API tests with mocked run_scan | 14 API tests + 4 new real-run_scan integration tests (Prompt 10) | Added coverage |

## 11. QA Findings (Prompt 10)

| # | Issue | Severity | Affected file/feature | Reproduction / verification | Status | Blocks release |
|---|---|---|---|---|---|---|
| QA-01 | **Scan background task never runs the submitted scan.** Route calls `run_scan(run["id"], repo_url)` but implementation was `run_scan(repo_url, name=None)` → the UUID was validated as a URL and failed; a spurious duplicate failed run was created; the real run stayed `queued` forever (frontend would poll endlessly) | **Critical** | `backend/app/services/scanner.py` `run_scan`; `routes/scans.py` | Simulated route→run_scan call against FakeDatabase: reproduced (duplicate row, misleading "repo URL must use https" error). Fixed signature to `run_scan(scan_id, repo_url)`; re-ran simulation: single run, queued→completed, no duplicate; added 4 integration tests | **FIXED** (Prompt 10) | Was: yes. Now: no |
| QA-02 | Non-blocking warning during `next build`: recharts `width(-1)/height(-1)` on /dashboard chart container | Low | `frontend/src/app/dashboard/page.tsx` (MiniChart) | Reproduced in build output | Documented only (styling; no functional impact; would require frontend work beyond release-prep scope) | No |
| QA-03 | Topbar profile drawer items "My Account", "Notifications", "Security", "Sign Out" are `href="#"` mock placeholders (Settings → `/settings` is real) | Low | `frontend/src/components/layout/Topbar.tsx` | Code inspection | Documented only (mock demo UI, not broken routes) | No |
| QA-04 | Dashboard "Quick Actions" buttons (New Incident, Run Postmortem, …) have no handlers | Low | `frontend/src/components/dashboard/QuickActions.tsx` | Code inspection | Documented only (decorative demo UI) | No |
| QA-05 | Homepage marketing copy mentions "automated postmortems"; no postmortem feature exists | Low | `frontend/src/app/page.tsx`, README (fixed) | Code inspection | README corrected; homepage copy left as marketing text | No |
| QA-06 | `backend/.env.example` contained stale `SUPABASE_URL`/`SUPABASE_KEY` and missing scan knobs | Medium (docs) | `backend/.env.example` | Inspection vs `config.py` | **FIXED** — now matches `config.py` exactly (DATABASE_URL, CORS_ORIGINS, all 9 scan vars) | No |
| QA-07 | README/QUICK_START/AGENTS contained Supabase, LangChain, postmortem, root-level `cp .env.example .env`, nonexistent test instructions | Medium (docs) | root docs | Inspection vs implementation | **FIXED** — see §12 | No |
| QA-08 | No PostgreSQL/Docker on QA machine | N/A (environment) | E2E infrastructure | `localhost:5432` refused; no docker/postgres binaries | Documented — DB-backed E2E, rules-only E2E, restart sweep E2E → **REQUIRES VERIFICATION** | No (unit/integration coverage + manual verification path documented) |

## 12. Documentation Sync (Prompt 10)

- **README.md** — rewritten to the actual implementation: PostgreSQL+asyncpg stack, real routes, Security Scan usage, env vars (Supabase/LangChain/pgvector/postmortem/RAG removed), correct quick-start commands, testing commands (backend pytest; frontend tsc/lint/build, no JS test framework), deployment (render.yaml + frontend), security limitations, startup-resilience behavior. Removed fabricated license/performance/cost claims.
- **QUICK_START_GUIDE.md** — rewritten: correct env-file location (`backend/.env.example` → `backend/.env`), correct dependency manifests (`backend/requirements.txt`, `frontend/package.json`), correct commands, scan usage, pitfalls table.
- **AGENTS.md** — stack (PostgreSQL 16 via asyncpg), structure (routes/services/middleware/tests), `python -m pytest -q` (163 tests), frontend `npx tsc --noEmit`/`npm run lint`/`npm run build`, scan feature status, CORS_ORIGINS, no-Jest note, no-auth limitation.
- **ARCHITECT.md** — NOT rewritten; added a status note that it is the reference design with a dark theme while the implemented UI is light (tokens in `globals.css`); rest preserved.
- **DATABASE_SCHEMA.md** — inspected; §4/§5 scan tables match `database.py` SCHEMA_SQL exactly (TEXT ids/timestamps documented). Left unmodified per instructions.

## 13. Items Requiring Verification (not claimed as passed)

1. Full DB-backed scan E2E on octocat/Hello-World (status transitions, findings counts, persistence, temp-dir cleanup via real `run_scan`) — needs PostgreSQL.
2. Rules-only E2E with empty `OPENAI_API_KEY` through the full HTTP flow.
3. LLM deep-review E2E with a real key (score/grade + `metadata.llm_status: "ok"`).
4. Restart-mid-scan orphan sweep E2E (`queued/running → failed`, "server restarted mid-scan").
5. Findings-path E2E against a repo that actually contains rule hits (auto-incident creation visible on `/incidents`).

All five have unit/integration coverage; §8 lists the exact validation performed.

## 14. Final Verification Summary (Prompt 10)

| Check | Result |
|---|---|
| Backend `python -m pytest -q` | **PASS** — 163 passed |
| Backend import/start with DB env (dev, DB down) | **PASS** — boots, warns, `/health` degraded |
| Backend route groups (health/logs/incidents/anomalies/search/scans) | **PASS** — all 17 paths registered; scans 4 routes present |
| Frontend `npx tsc --noEmit` / `npm run lint` / `npm run build` | **PASS** / **PASS** / **PASS** |
| Frontend pages (/, /dashboard, /incidents, /incidents/[id], /logs, /scans, /analytics, /settings) | **PASS** — all build; sidebar + homepage + dashboard + incident links resolve |
| Scan E2E (full) | **REQUIRES VERIFICATION** (no Postgres) |
| Rules-only E2E | **REQUIRES VERIFICATION** (no Postgres); no-key unit path PASS |
| Restart recovery / orphan sweep | **REQUIRES VERIFICATION** (no Postgres); unit coverage PASS |
| Security: `.env` untracked, no secrets (`sk-`/`ghp_`/`AKIA` inspected) | **PASS** |
| Security headers live | **PASS** (curl verified) |
| CORS safe (wildcard ⇒ no credentials) | **PASS** |
| Auth limitation documented | **PASS** (README + AGENTS.md) |

## 15. Final Project Completion Audit (Prompt: release audit)

Executed 2026-08-14 after commit `faa0041`. Re-ran every validation command, re-inspected
routes/tests/components, re-grepped for secrets and `dangerouslySetInnerHTML`, and
traced each checklist item against the implementation. No code changes were required —
the audit confirmed the Prompt 10 state. One new non-blocking observation (QA-09).

### Audit checklist results

| Checklist item | Result | Evidence |
|---|---|---|
| Scan submit/list/detail/promote E2E | **PASS** (code+tests); DB E2E **REQUIRES VERIFICATION** | 18 tests in `test_scans_api.py`: 201+queued, background in queued order, list w/ finding_count, detail w/ findings, promote 201/409-twice/404-wrong-scan/404-missing |
| Rules-only degradation | **PASS** (unit) | 7 tests in `test_scanner_llm_parse.py`: refusal, missing parsed, OpenAIError, generic exception, empty key (no request), empty files (no request) |
| Critical/high auto-incident | **PASS** (unit) | `test_run_scan_persists_findings_and_auto_promotes`; dedupe via `_scan_findings` unique hash |
| Deterministic finding IDs / rescan dedupe | **PASS** (unit) | SHA1-based `_scan_finding_id`; completed rescans don't conflict (test), duplicate incident creation deduped by unique constraint + `_dedup_incident` logic |
| Orphan sweep | **PASS** (unit) + **REQUIRES VERIFICATION** (E2E) | registered `main.py:22` lifespan; `sweep_orphaned_scans` `scanner.py:859` |
| Empty log upload no 500 | **PASS** | `logs.py:43-103` returns 200/0/0 for empty & whitespace files; `test_upload_empty_file_*`, `test_upload_whitespace_only_file_*` |
| Search preserves per-row service/level | **PASS** | `test_search_uses_each_rows_own_service_and_level` + filter test |
| Incident detail page | **PASS** | full loading/404/error(retry)/success states, plain-text fields, `<pre>` metadata |
| `/scans` page + ScanForm/ScanList/ScanDetail | **PASS** | all four compile (build route table); ScanForm client validation mirrors server (https, host allowlist, credentials, `..`, length, leading `-`); loading/empty/error/success states in both lists; sub-scores from `metadata`; evidence in `<details><pre>` plain text |
| No broken nav / 404 routes | **PASS** | all 8 pages build; `_not-found` present; sidebar/homepage/topbar links resolve (QA-03 placeholders documented, non-broken) |
| TS / lint / build | **PASS** / **PASS** / **PASS** | re-run this audit; build emits only the known recharts `width(-1)` stderr warning |
| Scoring functions | **PASS** | 12 tests: 100→A, 75→B, 50→C, 25→D, 0→F, grade boundaries, sub-scores per category + floor at 0 |
| LLM Structured Outputs | **PASS** | `llm_review` uses `response_format=LLMReview` (asserted in test), `refusal` honored |
| `run_scan` async Shape B | **PASS** | `async def run_scan(scan_id: str, repo_url: str) -> dict` in-place transition (QA-01 fix, commit `faa0041`) |
| 4 scan endpoints + router + startup sweep registered | **PASS** | `scans.py` (POST/GET /scans, GET /scans/{id}, POST /scans/{id}/findings/{fid}/promote); router in `main.py` |
| CORS safe | **PASS** | `allow_origins` from settings; `allow_credentials` = False when wildcard (`config.py:29`) |
| Security headers | **PASS** | `SecurityHeadersMiddleware` (`main.py:65`); curl-verified headers |
| Anomaly params bounded | **PASS** | `anomalies.py` bounds: window 1–24h, contamination 0.01–0.5, n_neighbors 5–100 (422 on violation) |
| Schema auto-creation / 5 tables | **REQUIRES VERIFICATION** (no Postgres) | `database.py` SCHEMA_SQL has all 5 tables; `DATABASE_SCHEMA.md` matches; not run against real PG |
| No unintended SQLite app.db | **PASS** | `git ls-files` + filesystem: no `app.db`/sqlite anywhere in repo |
| Scan API contract (201/400/404/409) | **PASS** | 18 tests incl. 400 invalid URL, 409 duplicate active, 404 missing scan/finding, 409 promote-twice, 422 missing URL |
| Health/logs/incidents/anomalies/search endpoints | **PASS** | route inventory (17 paths) + existing suites (`test_logs_search_routes.py` 7 tests; `test_security.py` 17; health verified live) |
| No-auth posture documented | **PASS** | README/AGENTS limitation; production guidance = VPN/SSO/access layer; auth + RLS listed as roadmap |
| URL allowlist enforced server-side | **PASS** | `validate_repo_url` in scanner; 11 tests incl. `%2e%2e`, trailing dot, credentials, unknown host, length, leading dash, https-only |
| Evidence truncation + masking | **PASS** | `_truncate` (12k/file, 600k total) + `_mask_secrets`; tests in `test_scanner_rules.py` (masking verified earlier) |
| Encoded traversal / unsafe schemes / creds in URL rejected | **PASS** | URL validation tests + ValueError paths |
| No avoidable 500s on invalid input | **PASS** | Pydantic bounds + validation-tests; `errors[:20]` on upload; LLM exceptions never crash scan |
| Scan failures → `failed` w/ readable message | **PASS** | `run_scan` try/except sets `failed` + `error` (invalid URL, clone failure tests) |
| DB-down startup env-aware | **PASS** | dev: warns + continues, `/health` degraded; prod: fails hard (verified code + earlier run) |
| LLM failure doesn't crash scans | **PASS** | fallback matrix tests |
| No secrets in tracked files / `.env` ignored | **PASS** | `git check-ignore backend/.env` hit; `git ls-files` no `.env`; all `sk-`/`ghp_`/`AKIA` matches benign (placeholder `sk-your-key-here`, regex defs, AWS doc-example fixtures, planning docs) |
| No `dangerouslySetInnerHTML` in scan UI (or anywhere) | **PASS** | repo-wide grep: only planning docs + the scanner rule regex |
| SSRF protections intact | **PASS** | allowlist + https-only + `..`/`%2e%2e` + credential checks in `_build_clone_cmd`/validation; `test_scanner_url_validation.py` |
| No secrets printed in tests/logging | **PASS** | fake key `sk-test-key` in one test; no logging of key values in app code |
| pytest suite ≥45, offline | **PASS** | 163 tests, `pytest -q` green in 1.03s, no DB/network |
| Every rule +/− coverage | **PASS** | 20 rules × (positive + negative) = 41 tests in `test_scanner_rules.py` |
| LLM fallback matrix / URL validation / scoring boundaries | **PASS** | covered above |
| Perf caps (50MB / 2000 files / 10 LLM files / 600k chars / 2 concurrent) | **PASS** | `config.py` defaults wired into walker/LLM/semaphore; `_abort_if_over_limits` tested |
| Polling stops at terminal state | **PASS** | `hooks.ts:58-60` (list) + `67-70` (detail) — interval off when completed/failed |
| Temp dir cleanup | **PASS** (DB-free path, retry) / **REQUIRES VERIFICATION** (full E2E) | `_rmtree_retry` exercised live; unit coverage |
| Responsive scan UI | **PASS** | `flex-col sm:flex-row`, `grid-cols-2 sm:grid-cols-3 lg:grid-cols-6`, `overflow-x-auto`, `flex-wrap` everywhere |
| Semantic controls / labels / keyboard | **PASS** (with QA-09) | form + `aria-label` on input, `role="alert"` errors, real `<button>`s, native `<details>/<summary>`; status text + badge (not color-only) |
| render.yaml | **PASS** | `rootDir: backend`, `pip install -r requirements.txt`, `uvicorn app.main:app --host 0.0.0.0 --port $PORT`, managed PG, `OPENAI_API_KEY` sync:false |
| Production doesn't serve raw Next source | **PASS** | frontend deployed separately (documented in README); backend image copies only `app/` |
| Docker config | **PASS** (inspection) / **REQUIRES VERIFICATION** (build/run) | `Dockerfile` + `docker-compose.yml` structurally valid; no docker binary on QA machine |
| Final commit + clean tree | **PASS** | `faa0041` "feat: finalize security scan MVP"; `git status` clean |

### New observation (non-blocking)

| ID | Finding | Severity | Where | Status |
|---|---|---|---|---|
| QA-09 | `ScanList` rows select via `<tr onClick>` only — mouse-driven, not keyboard-focusable | Low (a11y) | `frontend/src/components/scans/ScanList.tsx:78` | Documented only. Follow-up: wrap row content in a focusable button/link or add `onKeyDown` + `tabIndex`. Not a release blocker (list remains usable via mouse/touch; form and detail interactions are keyboard-accessible). |