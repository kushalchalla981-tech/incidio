# PLAN-CHECK — Vibe-Code Security Scan

**Plan reviewed:** `.planning/PLAN.md` (8 sub-plans P1–P8, waves 1–5, 21 tasks)
**Method:** goal-backward analysis against the phase goal; cross-checked every file/line claim against actual code (models.py, database.py, config.py, main.py, embeddings.py, incidents.py, hooks.ts, api.ts, types.ts, requirements.txt, package.json, Badge/Sidebar/Topbar/RecentIncidents, .gitignore, .env.example, docker-compose.yml); behavioral probes run against the venv (Python 3.14.4, openai 2.43.0, fastapi 0.136.1, httpx 0.28.1, react-query 5.101.0, git 2.54.0).
**Date:** 2026-08-07

---

## 1. Goal Coverage Matrix

| # | Goal element | Supporting task(s) | Status |
|---|---|---|---|
| 1 | Safe URL validation (SSRF/arg-injection/traversal) | P4 Task 4.1 (9 checks, fail-fast) + P7 Task 7.1 (400) + P8 test_scanner_url_validation | ⚠️ FAIL as written (encoded-traversal case — see B1) |
| 2 | Hardened git clone | P4 Task 4.1 (list-args, `--` separator, protocol flags, DEVNULL pipes, taskkill tree-kill, FileNotFoundError→ScanAbortError, retry rmtree) | ✅ PASS |
| 3 | Heuristic regex rules engine | P4 Task 4.2 (walker caps, binary detection, 20-rule table, 7 handlers, correlation rules) | ⚠️ PASS with defects (count + severity expectations — B2, B3) |
| 4 | OpenAI LLM deep-review | P6 Task 6.1 (Structured Outputs `parse`, refusal/length/exception → rules-only) | ✅ PASS (verify snippet env-dependent — W3) |
| 5 | Scored report: 0-100 + letter grade + per-category sub-scores | P4 Task 4.3 (weights 25/15/7/3, grade thresholds, sub-scores) + P6 Task 6.2 (metadata persist) + P5 Task 5.2 (sub-score display) + P8 test_scanner_score | ✅ PASS |
| 6 | Auto-create incidents for critical/high | P6 Task 6.2 `promote_finding_to_incident` + dedupe guard | ✅ PASS (rescan dedupe ineffective — W2) |
| 7 | Persist scan runs + findings to Postgres | P2 Tasks 2.1–2.3 (2 tables, 8 CRUD methods, SCHEMA_SQL append, JSON/TIMESTAMP registration, doc) | ✅ PASS |
| 8 | Frontend /scans page: form, polled list, detail, promote | P3 Tasks 3.1–3.3 + P5 Tasks 5.1–5.3 (fn-form refetchInterval, invalidation, onCreated/onSelect) | ✅ PASS (onCreated wiring underspecified — I1) |
| 9 | Regression: existing features keep working | Additive-only changes (config/models/database/main appends); P7 Task 7.2 route-registration assertion; §6 target #3 | ✅ PASS (no existing code path modified) |
| 10 | pytest modules pass | P8 Tasks 8.1–8.3 (conftest + 5 modules, FakeDatabase, TestClient w/o lifespan) | ⚠️ FAIL as written (B1 guaranteed test failure) |
| 11 | npm run lint + npm run build | P3/P5 verify blocks | ✅ PASS |
| 12 | E2E scan of sample repo | §6 steps 1–9 (Hello-World, rules-only path, sweep proof, promote) | ✅ PASS |

**Requirements frontmatter:** SCAN-01..04 declared on the single plan file (monolith with P1–P8 sections — acceptable for this repo's layout; note: no ROADMAP.md/CONTEXT.md exist in `.planning/`, so requirement IDs are self-declared; the goal as given in the task brief is fully decomposed).

---

## 2. Internal Consistency Findings

**B1 (BLOCKER) — Encoded path traversal test WILL fail.** P4 Task 4.1's `validate_repo_url` checks `".." in parsed.path`, and P8 test_scanner_url_validation asserts `https://github.com/%2e%2e/repo` is rejected. **Probe result (executed):** `urlparse("https://github.com/%2e%2e/repo").path == "/%2e%2e/repo"` — contains no literal `..`, so the validator as specified ACCEPTS it and the test FAILS. RESEARCH.md:69's claim "urlparse normalizes %2e in path" is factually wrong (urlparse does not percent-decode paths). This guarantees failure of the "pytest modules pass" verification target. Fix: check `".." in unquote(parsed.path)` (import `unquote` from urllib.parse) or reject on decoded segments; correct the RESEARCH claim.

**B2 (BLOCKER) — Rule count 19 vs 20.** Task 4.2 verify asserts `len(RULES) == 19`, but the table defines **20** rules (9 SECRET_*, 6 DANGER_*, 5 CONFIG_* incl. SUPABASE_NO_RLS). Verify command fails at execution. Fix: assert 20, or drop SECRET_STRIPE (RESEARCH §2 marks it optional) and say so.

**B3 (BLOCKER) — DANGER_EVAL severity contradiction.** Task 4.2 verify expects `DANGER_EVAL high` for fixture `os.system("ls")`, but the rule's own `_literal_or_variable` handler maps a *literal string* argument to **medium** (P8's test correctly asserts medium for `os.system("ls -la")`). P4's verify will fail and may tempt the executor to "fix" the wrong side. Fix: change the P4 verify expectation to `DANGER_EVAL medium`.

**W1 — `scan_repo` signature staleness (3-tuple vs 4-tuple).** P4 Task 4.2 specifies `-> tuple[list[dict], list[Path], int]` with a 3-value unpack in its verify; P6 Task 6.2's coordination note freezes `-> tuple[list[dict], list[tuple[str,int]], dict[str,str], int]`, yet Task 6.2's code block unpacks 3 values (`findings, scanned_files, total_bytes`) and references `texts_of_files`, which is undefined in the block. The plan acknowledges the change ("must be adjusted") but leaves the text stale — an executor following P4 literally builds a 3-tuple that breaks P6. Fix: edit P4 Task 4.2 text + verify and P6 Task 6.2 code block to the frozen 4-tuple; define `texts_of_files` in the code block. Also align `select_llm_files(scanned_files: list[tuple[Path, int]])` with the frozen `list[tuple[str,int]]`.

**W2 — Rescan duplicate-incident dedupe is ineffective.** Plan §7 R8 claims "Duplicate incidents on rescan → 409/skip" via `finding_has_incident(finding_id)`. But `insert_batch` generates a **fresh uuid4 per finding on every scan**, so the `metadata.finding_id` containment check can never match a previous scan — the guard only protects the manual double-promote path. RESEARCH flagged rescan duplication as HIGH likelihood (R7). Fix: derive a deterministic finding id (e.g., sha1 of `repo_url|rule_id|file|line`) or dedupe on `(rule_id, file, line)` + `source='vibe-scan'`; update the plan's R8 text to match the mechanism.

**W3 — P6 Task 6.1 verify is environment-dependent.** `assert s.llm_review([("a.py","x")]) == ([], "rules_only")` only holds when `OPENAI_API_KEY` is empty. Per AGENTS.md, `backend/.env` contains a key — with a valid key the assertion FAILS (real API call returns `(findings, "ok")`). Fix: clear `settings.OPENAI_API_KEY` via monkeypatch before the assert (mirror the P8 pattern).

**I1 — ScanForm `onCreated` wiring unspecified.** P3's `useCreateScan` `onSuccess` only invalidates queries; nothing delivers the created `ScanRun` to `onCreated`. Task 5.1 must call `createScan.mutate(data, { onSuccess: (scan) => onCreated?.(scan) })`. As written, selecting the new run for detail view works only by luck of the next list poll.

**I2 — P2 Task 2.1 verify block** contains a broken first snippet (nonsense lambda) before "instead, run:" — harmless but will waste executor time if run verbatim.

**I3 — RESEARCH.md `## Open Questions`** lacks the `(RESOLVED)` suffix; each question does carry a recommendation the plan adopts (weights as-is, gpt-4o-mini default, subdomains excluded) — housekeeping.

---

## 3. Codebase Realism Findings

All spot-checked line references are **accurate**:
- `config.py:5-17` Settings; CORS_ORIGINS at line 11 — append point correct. `SCAN_ALLOWED_HOSTS: list[str]` parses comma-separated env via pydantic-settings v2. ✅
- `models.py`: Incident triple 47-93, `id: UUID` convention, HealthResponse at 154, `from typing import Optional, List` at line 3 — the planned `Literal` import extension and `Field(default_factory=...)` usage match Pydantic v2 (2.13.4). UUID-from-TEXT coercion is already proven by the incidents path. ✅
- `database.py`: SCHEMA_SQL 23-70, JSON_COLUMNS/TIMESTAMP_COLUMNS 11-21, insert/insert_batch/get_by_id/update_by_id 125-171, update_embedding 247-250, query_incidents 270-293, `_db` at 296 — all match. Planned SQL is valid Postgres: `GROUP BY s.id` with `s.*` is legal (functional dependency on PK), `metadata::jsonb @> $1::jsonb` valid on TEXT column. `get_scan_findings` severity DESC lexical ordering (critical>high>medium>low) is correct. ✅
- `main.py`: lifespan 14-19, import line 10, router registration 37-41, static mount 43-44 — matches. Sweep-in-lifespan and router append are non-invasive. ✅
- `embeddings.py:8-16` lazy singleton — correct analog for `_get_llm_client`. ✅
- Frontend: hooks.ts useIncidents 37-43 / useBackfill 31-35 / enabled 23-29 ✅; api.ts fetchJSON 5-15 / list 45-53 / POST 59-70 ✅; types.ts IncidentFilters ends at 113 ✅; Badge variants include `info` ✅; Sidebar links 11-17, lucide import 7-9, active-state 47 ✅; Topbar input 33-40 ✅; RecentIncidents severity map line 8 ✅; LoadingSkeleton exists ✅. React Query 5.101.0 supports function-form `refetchInterval`; returning `false` stops polling ✅.
- `requirements.txt`: 14 lines, no pytest — plan's install step correct. **Factual error (W4):** P1 Task 1.2 claims "httpx NOT installed" — verified httpx **0.28.1 IS installed** in the venv. Adding `httpx>=0.27.0` to requirements.txt is still correct for reproducibility; only the justification is wrong.
- Env/infra: `.env.example` has 5 vars ✅; `.gitignore` has no `.scan-tmp` entry ✅; docker-compose.yml exists ✅; git 2.54.0 on PATH ✅; `backend/tests/` and `pytest.ini` do not exist (as the plan states) ✅.

**AGENTS.md compliance:** pytest under `backend/tests/` ✅, type hints/Pydantic ✅, `npm run lint`+`npm run build` ✅, no `.env` commits (scan-tmp gitignored) ✅, no forbidden patterns introduced. The plan's own AGENTS.md edits (env var docs, pytest command) are consistent with its conventions.

---

## 4. Testability Findings

- **Feasible.** No tests dir/config today — P8 creates both; `asyncio_mode = auto` + pytest-asyncio is the standard combination. The 5-module split (url / rules / score / llm-parse / api) correctly isolates pure logic from I/O.
- **FakeDatabase approach is sound** and the plan shows correct reasoning: routes do `from app.database import get_db` at import time, so monkeypatching `app.api.v1.routes.scans.get_db` (not `app.database.get_db`) is the right target.
- **TestClient without context manager** is the documented way to skip lifespan (which would otherwise call real `get_db()` with empty DATABASE_URL) — correct.
- **`fake_run_scan` stub** works: TestClient executes BackgroundTasks synchronously post-response, so the recorded-call assertion is deterministic. Async stub avoids DB entirely.
- Module-import safety: `scanner.py`'s import-time `SCAN_TMP.resolve()` and `asyncio.Semaphore()` are loop-free and side-effect-free on Python 3.14 — safe under pytest collection.
- LLM-parse tests monkeypatch the module-level `_llm_client` and settings — workable; the no-key/refusal/length/exception matrix covers RESEARCH R5 completely.
- **Minor (I4):** pytest-asyncio 1.x may emit `asyncio_default_fixture_loop_scope` warnings with `asyncio_mode=auto`; not fatal (warnings don't fail unless `-W error`), but pinning or adding the ini key would make the suite warning-clean.
- **B1 is the one genuinely broken test** (see §2) — everything else is implementable as specced.

---

## 5. Risk Assessment

| Risk | Status |
|---|---|
| git binary missing at runtime | Mitigated: FileNotFoundError → ScanAbortError → scan failed with clear error (P4 Task 4.1); verified on dev PATH |
| DB unavailable during tests | Mitigated: FakeDatabase, zero DB/network/OpenAI dependency in suite |
| LLM key absent / outage / refusal / truncation | Mitigated: every failure → `([], "rules_only")`; tested (P8 llm module) |
| Orphaned scans after restart (UI stuck "running") | Mitigated: startup sweep + client polling stop on terminal status |
| Windows orphan git processes / long paths / disk caps | Mitigated: taskkill tree-kill, DEVNULL pipes, retry rmtree, per-file try/except, size+count caps during walk |
| Duplicate incidents across rescans | **UNMITIGATED (W2)** — claimed dedupe cannot fire across scans (fresh finding ids). Real-world impact: incident list pollution on rescan; feature still functions |
| Encoded traversal `%2e%2e` accepted | Validation-fidelity gap, not SSRF (host allowlist + fixed dest contain it) — but it fails a unit test and breaks the plan's own acceptance criterion (B1) |

No unmitigated critical risk blocks the feature itself; two deterministic test/verify failures (B1, B2, B3) block the "pytest modules pass" verification target.

---

## 6. Final Verdict: **BLOCK** (revision required — small, enumerated fixes)

The plan is structurally excellent: every goal element maps to concrete tasks with files, actions, verify commands, and done criteria; wave/dependency ordering is correct (P6 same-file append after P4, P8 after P7); SSRF/clone/Windows handling is research-grade; the test strategy (FakeDatabase + module-symbol monkeypatch + TestClient-without-lifespan) is technically correct; frontend patterns match the codebase exactly; regression risk is minimal (all changes additive). **However, as written, three items deterministically fail during execution**, which fails the phase goal's own verification target ("pytest modules pass" + P4 verify commands). BLOCK with the following checklist:

### Checklist for planner (fix all, re-verify)

- [ ] **B1:** `validate_repo_url` — reject encoded traversal via `".." in unquote(parsed.path)` (add `unquote` import). Update RESEARCH.md:69 claim ("urlparse does NOT decode %2e in path"). P8's `%2e%2e` reject case then passes.
- [ ] **B2:** Rule table defines 20 rules — fix Task 4.2 verify to `len(RULES) == 20` (or remove SECRET_STRIPE and document it, keeping 19).
- [ ] **B3:** P4 Task 4.2 verify fixture `os.system("ls")` (literal arg) → expect `DANGER_EVAL medium`, not high.
- [ ] **W1:** Reconcile `scan_repo` signature everywhere: P4 Task 4.2 text + verify, P6 Task 6.2 code block (4-tuple unpack, define `texts_of_files`), `select_llm_files` param type (`list[tuple[str,int]]`).
- [ ] **W2:** Make rescan dedupe real — deterministic finding id (sha1 of repo_url+rule_id+file+line) or dedupe on `(rule_id, file, line)` + source; update §7 R8 wording.
- [ ] **W3:** P6 Task 6.1 verify — clear `settings.OPENAI_API_KEY` first (or monkeypatch) so it is environment-independent.
- [ ] **W4:** P1 Task 1.2 — correct the "httpx not installed" claim (0.28.1 present); keep the requirements.txt addition.
- [ ] **I1:** Task 5.1 — specify per-call `mutate(data, { onSuccess: (scan) => onCreated?.(scan) })`.
- [ ] **I2:** Clean the P2 Task 2.1 verify snippet; **I3:** mark RESEARCH Open Questions `(RESOLVED)`; **I4:** consider `asyncio_default_fixture_loop_scope` in pytest.ini.

After the fixes, all 12 goal-coverage rows go green and execution can proceed to `/gsd-execute-phase`.

---

## 7. Re-verification addendum (2026-08-07) — all checklist items FIXED

| Item | Fix applied in PLAN.md |
|---|---|
| B1 | `validate_repo_url` now rejects `".." in unquote(parsed.path)` (`unquote` added to urllib.parse import); RESEARCH.md:69 claim corrected ("urlparse does NOT percent-decode `%2e`"). `%2e%2e` reject case in P8 passes. |
| B2 | Rule count reconciled to **20**: table header ("20-rule table"), Task 4.2 verify (`expect 20`), Done line, success checklist all updated. |
| B3 | Task 4.2 verify expectation changed to `DANGER_EVAL medium` for the literal-arg `os.system("ls")` fixture, with a note explaining variable args → high. |
| W1 | `scan_repo` frozen as 4-tuple `(findings, files_with_hits, texts, total_bytes)` in P4 (texts pre-truncated during read); P4 verify unpacks 4 values; P6 Task 6.2 code block unpacks `findings, scanned_files, texts_of_files, total_bytes`; `select_llm_files(scanned_files: list[tuple[str, int]], texts: dict[str, str])` aligned. |
| W2 | Deterministic finding ids: sha1 of `repo_url|rule_id|file|line` assigned before `insert_batch` (P6 Task 6.2 code block + R8 row) — `finding_has_incident` containment now fires across rescans. |
| W3 | P6 Task 6.1 verify clears `s.settings.OPENAI_API_KEY = ""` before the rules-only assert — environment-independent. |
| W4 | P1 Task 1.2 corrected: httpx 0.28.1 verified installed; re-added to requirements.txt for reproducibility only. |
| I1 | Task 5.1: per-call `createScan.mutate(data, { onSuccess: (scan) => { setRepoUrl(""); onCreated?.(scan); } })` specified. |
| I2 | P2 Task 2.1 verify: broken first snippet removed; only the working `to_regclass` check remains. |
| I3 | RESEARCH.md `## Open Questions (RESOLVED — decisions adopted by PLAN.md)` with per-item [RESOLVED] markers. |
| I4 | `asyncio_default_fixture_loop_scope = function` added to pytest.ini (Task 8.1). |

**Re-verdict: PASS.** All 12 goal-coverage rows green; deterministic test/verify failures eliminated; no remaining blockers.
