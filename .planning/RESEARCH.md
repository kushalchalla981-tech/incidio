# Vibe-Code Security Scan — Phase Research

**Researched:** 2026-08-07
**Domain:** Repo cloning safety, static secret/code-pattern scanning, LLM-assisted code review, background jobs in FastAPI
**Confidence:** HIGH (cloning, rules, background jobs, polling) / MEDIUM (LLM model choice, scoring)

---

## Summary

The existing draft plan (`VIBE_SCAN_IMPLEMENTATION_PLAN.md`) is architecturally sound: clone → rules engine → LLM deep-review → score → auto-incident. This research validates the core design against 2025-2026 best practice and **corrects five things the plan gets wrong or under-specifies**:

1. **The AWS and OpenAI key regexes in the plan will produce unacceptable false positives.** Gitleaks' canonical patterns (verified against the live gitleaks repo, March 2025 update) use the base32 alphabet constraint `[A-Z2-7]{16}` for AWS and the `T3BlbkFJ` marker for OpenAI keys. The plan's `AKIA[0-9A-Z]{16}` and `sk-[A-Za-z0-9]{20,}` must be replaced.
2. **The clone command must add transport-hardening flags** (`-c protocol.ext.allow=never -c protocol.file.allow=never` and a `--` separator) plus Windows-specific process-tree kill on timeout. On Windows, `subprocess.run(timeout=...)` kills only the direct child — git's helper processes survive, hold file locks, and break temp-dir cleanup (verified: Python bug #43346, multiple 2025-2026 fixes).
3. **BackgroundTasks is the right MVP choice** but only with the DB-persisted status + restart-marking pattern. FastAPI's BackgroundTasks **does** support `async def` tasks (verified from official docs), but blocking calls (subprocess clone, sync OpenAI client) inside an async task block the event loop — the scan task should be a plain `def` running in the threadpool, or an async coroutine that offloads blocking work with `asyncio.to_thread()`.
4. **LLM JSON: use Structured Outputs** (`response_format={"type":"json_schema", strict:true}` or the SDK's `client.beta.chat.completions.parse()` with a Pydantic model), not plain `json_object` mode. The installed openai SDK is 2.43.0, which supports it. JSON mode is documented as legacy in 2026 and has a known truncation bug producing invalid JSON.
5. **The scoring model (weighted penalty sum) is defensible** but should borrow SonarQube's worst-finding letter grade as a secondary signal; and the score needs a documented cap/saturation policy.

The frontend approach (React Query `refetchInterval` polling with conditional stop) is confirmed best practice — the codebase already uses this pattern, and TanStack Query v5 supports a function-form `refetchInterval` that stops polling when the scan completes.

**Primary recommendation:** Implement the plan as drafted, with the five corrections above. Rules-only fallback when OpenAI is unavailable is confirmed as the right degradation behavior.

---

## 1. Safe Repo URL Validation & Cloning

### 1.1 URL validation (fail-fast, synchronous, in the route)

Validated against three production implementations (synthorg, AutomatosAI, shipwright) plus OWASP-aligned guidance [VERIFIED: github.com/Aureliolo/synthorg, github.com/AutomatosAI/automatos-ai, github.com/svenroth-ai/shipwright, safeguard.sh 2025-06]:

```python
from urllib.parse import urlparse

ALLOWED_HOSTS = {"github.com", "gitlab.com", "bitbucket.org"}  # from settings.SCAN_ALLOWED_HOSTS

def validate_repo_url(url: str) -> str:
    url = url.strip()
    if not url or len(url) > 2048:
        raise ValueError("Invalid repo URL")
    if url.startswith("-"):                      # git arg-injection (CVE-2017-1000117 class)
        raise ValueError("URL must not start with '-'")
    parsed = urlparse(url)
    if parsed.scheme != "https":                 # reject http://, file://, ssh://, git://, ftp://, ext::
        raise ValueError("Only https:// URLs are allowed")
    if parsed.username or parsed.password:       # credential smuggling
        raise ValueError("URL must not contain embedded credentials")
    host = (parsed.hostname or "").lower()       # urlparse decodes percent-encoding
    if host != host.rstrip("."):                 # reject trailing-dot (FQDN) tricks like "github.com."
        raise ValueError("Invalid host")
    if host not in ALLOWED_HOSTS:                # exact-match allowlist, no subdomain wildcarding
        raise ValueError("Host not in allowed list")
    if ".." in parsed.path:                      # belt-and-braces path traversal
        raise ValueError("Invalid repo path")
    return url
```

**Edge cases that MUST be in unit tests** [VERIFIED: gitleaks/AutomatosAI patterns, plan's test spec]:

| Input | Expected |
|---|---|
| `https://github.com/user/repo.git` | pass |
| `https://gitlab.com/group/repo` | pass |
| `https://github.com.` (trailing dot) | reject |
| `https://github.com.evil.com/...` | reject (allowlist is exact-match) |
| `https://user:pass@github.com/repo` | reject |
| `https://github.com/../etc/passwd` | reject |
| `file:///etc/passwd`, `ssh://git@github.com/...`, `http://github.com/...`, `git://...` | reject |
| `-oProxyCommand=...` style leading dash | reject |
| `https://github.com/%2e%2e/repo` | reject — **urlparse does NOT percent-decode `%2e` in paths** (verified by probe: `urlparse("https://github.com/%2e%2e/repo").path == "/%2e%2e/repo"`), so the traversal check MUST apply to `unquote(parsed.path)` (PLAN P4 Task 4.1) |

**SSRF posture for MVP:** the exact-match host allowlist of three well-known public hosts is the primary SSRF control. Full IP-range blocking (`socket.getaddrinfo` + `ipaddress.is_private` checks) and DNS-pinning (`-c http.curloptResolve=...`) are what serious implementations add on top [VERIFIED: synthorg git_url_validator, defenseclaw ssrf.py]; for this MVP the residual risk (DNS rebinding on github.com/gitlab.com/bitbucket.org specifically) is LOW and can be documented as a known limitation rather than engineered around. **Do not skip** the `protocol.file/ext.allow` flags below — they are the cheap, effective part.

### 1.2 Cloning (subprocess, no shell, hardened)

Concrete command [VERIFIED: shipwright clone.py; AutomatosAI git_sanitizer.py]:

```
git clone
  -c protocol.ext.allow=never          # blocks ext:: transport tricks
  -c protocol.file.allow=never         # blocks file:// transport
  --depth 1 --single-branch --no-tags  # shallow; plan already has depth/single-branch
  --no-recurse-submodules              # submodule URL bypass would skip our validation
  -- <url> <dest>
```

- `-c` flags must come **before** the `clone` subcommand (global config).
- The `--` separator guarantees the URL can never be parsed as a flag [VERIFIED: AutomatosAI `build_git_clone_cmd`].
- **Never** `shell=True`, never f-string the URL into a command string. List args only.

**Windows-critical timeout handling** [VERIFIED: Python docs + bug bpo-43346; CursorTouch/Windows-MCP PR #151 2026-03; daintree issue #3180]:

- `subprocess.run(timeout=60)` on Windows kills the direct child only; `git` spawns `git-remote-https`, `git-remote-http`, `git index-pack`, etc. If a grandchild holds stdout/stderr pipe handles open, the post-timeout pipe drain in `communicate()` **blocks indefinitely** — the timeout is effectively ignored.
- **Mitigation (required on this codebase — it runs on Windows):** use `subprocess.Popen` with stdout/stderr redirected to files or `DEVNULL` (NOT `PIPE`), and on `TimeoutExpired` kill the whole tree with `taskkill /F /T /PID <pid>` on win32 (plain `proc.kill()` on POSIX). Recommended helper:

```python
import os, subprocess, sys

def _run_git(args: list[str], timeout: int = 60) -> subprocess.CompletedProcess:
    proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        _, _ = proc.communicate(timeout=timeout)
        return subprocess.CompletedProcess(args, proc.returncode)
    except subprocess.TimeoutExpired:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                           capture_output=True)  # /T = kill process tree
        else:
            proc.kill()
        proc.wait(timeout=10)
        raise TimeoutError(f"git clone timed out after {timeout}s")
```

- Clone failure detection: `returncode != 0` OR `not (dest / ".git").exists()` [VERIFIED: shipwright].

### 1.3 Size measurement and caps

- **During clone:** `--depth 1` limits history; consider `--filter=blob:limit=1m` to skip downloading blobs >1MB during clone (partial clone, git ≥ 2.19; supported on GitHub/GitLab) — but note the checkout then lazily fetches the missing blobs, so the savings only materialize if the walker skips them first. **MVP recommendation:** skip the filter (keep semantics simple), rely on post-clone caps. Document as an upgrade path. [VERIFIED: git-scm.com git-clone docs, partial-clone docs]
- **Post-clone size cap:** `du` does not exist on Windows. Use a portable Python walk (`os.scandir` recursion summing sizes) or `git count-objects -vH` for `.git` size. **Recommend the Python walk** because the walker is needed anyway for scanning, and enforce `MAX_REPO_SIZE_MB` + `MAX_SCAN_FILES` **during** the walk (abort scan early, mark failed with a clear error).
- **Cleanup:** `shutil.rmtree(dest, ignore_errors=False)` in `finally`; on Windows wrap in a small retry-on-`PermissionError` loop (file locks from any surviving git helper) and log loudly if it still fails — a leaked temp clone is a disk-exhaustion risk, not a security risk (clone content is public repo data by construction).

### 1.4 Windows compatibility notes

- git 2.54.0 present on PATH (verified in environment). `subprocess` resolves `git.exe` via PATH — fine.
- Long paths: repos with deep nesting can hit Windows MAX_PATH limits when `Path.rglob` walks; Python 3.6+ handles long paths when the system registry longPathAware is enabled — treat a `FileNotFoundError`/`PermissionError` on a walk as skippable per-file (log + continue), not fatal.
- `.scan-tmp` relative path: make it absolute at startup relative to the backend cwd (`Path(settings.SCAN_TMP_DIR).resolve()`), `os.makedirs(exist_ok=True)`, and add `.scan-tmp/` to `.gitignore`.

---

## 2. Secret / Weakness Regex Rules Table

**Sources:** gitleaks rules verified live from the repo (`gitleaks.toml` + `cmd/generate/config/rules/aws.go`, openai.go commit ddcc753 2025-03-27, aws-access-token FP fix #1584/#1577) [VERIFIED]; vibe-coding empirical studies (Invicti 20k-app analysis, LaunchReadyCode June 2026 dataset) [CITED].

Corrected/upgraded rule table (replaces the plan's table — **the plan's AWS and OpenAI patterns are wrong and must be swapped**):

| rule_id | Pattern (Python `re`) | Severity | False-positive guardrails |
|---|---|---|---|
| `SECRET_AWS_KEY` | `\b(?:AKIA\|ASIA\|ABIA\|ACCA)[A-Z2-7]{16}\b` | critical | Base32 alphabet `[A-Z2-7]` excludes 0/1/8/9 (real AWS keys) + `\b` word boundaries [VERIFIED: gitleaks #1584]. Skip if preceded by placeholder markers (`EXAMPLE`, `XXXXXXXX`). |
| `SECRET_OPENAI_KEY` | `\bsk-(?:proj\|svcacct\|admin)-(?:[A-Za-z0-9_-]{74}\|[A-Za-z0-9_-]{58})T3BlbkFJ(?:[A-Za-z0-9_-]{74}\|[A-Za-z0-9_-]{58})\b` OR legacy `\bsk-[a-zA-Z0-9]{20}T3BlbkFJ[a-zA-Z0-9]{20}` | critical | The `T3BlbkFJ` base64 marker is the discriminator — nearly eliminates FPs [VERIFIED: gitleaks commit ddcc753]. |
| `SECRET_GITHUB_TOKEN` | `\b(?:ghp\|gho\|ghu\|ghs\|ghr)_[A-Za-z0-9]{36}\b` and `\bgithub_pat_[A-Za-z0-9_]{22,}\b` | critical | Prefix + length bound; `ghp_` alone (7 chars) is not a token. [ASSUMED — standard, gitleaks-aligned; verify against gitleaks.toml during implementation] |
| `SECRET_PRIVATE_KEY` | `-----BEGIN (?:RSA \|EC \|OPENSSH \|DSA \|PGP )?PRIVATE KEY(?: BLOCK)?-----` | critical | Requires the full PEM banner; near-zero FP. |
| `SECRET_GENERIC_API_KEY` | `(?:api[_-]?key\|apikey\|secret\|token)\s*[=:]\s*["']([^"'\s]{16,})["']` | high | **Entropy gate:** compute Shannon entropy of captured value; report only if ≥ 3.5 bits/char (gitleaks uses min-entropy 3.0 as its secondary filter [VERIFIED: gitleaks rules]). This is what keeps "secret = 'my-cool-secret'" out of the report. |
| `SECRET_DB_URL` | `(?:postgres(?:ql)?\|mysql\|mongo(?:db)?\+srv\|redis\|amqp)://[^\s:@/]+:[^\s:@/]+@` | high | Requires `user:pass@` — bare `postgres://host/db` (no creds) is not flagged. |
| `SECRET_ENV_COMMITTED` | (not regex — filename rule) `.env`, `.env.*`, `.env.example` present in repo root | critical | **Do not flag `.env.example`** — it exists to be committed; flag `.env`, `.env.local`, `.env.production` only. |
| `SECRET_STRIPE` (optional) | `\bsk_live_[0-9a-zA-Z]{24}\b` | critical | `sk_test_` keys are non-production; report as medium or skip. [ASSUMED] |
| `DANGER_EVAL` | `\beval\(\|exec(\|shell_exec(\|os\.system(\|subprocess\.call(\|subprocess\.Popen(` | high | Report bare matches as **medium** when the argument is a literal string; escalate to high only when argument is an identifier/variable (regex cannot tell — heuristic: argument matches `[a-z_]\w*` ⇒ high, else medium). |
| `DANGER_CHILD_PROCESS` | `child_process\.(?:exec\|execSync\|spawn\|spawnSync)\(` | high | Same literal-vs-variable heuristic. |
| `DANGER_XSS_INNERHTML` | `innerHTML\s*=\|outerHTML\s*=\|dangerouslySetInnerHTML\|v-html=` | high | Flag only when RHS is not a compile-time constant string literal — MVP: flag all, mark evidence, let LLM phase confirm. |
| `DANGER_SQL_CONCAT` | In `.py`: `f"` or `+` adjacent to SQL keywords (`SELECT\|INSERT\|UPDATE\|DELETE\|WHERE`) within 3 lines; in `.sql`/`.js`/`.ts`: string concat with SQL keywords | high | Multi-line check; single-line regex `(SELECT\|INSERT\|UPDATE\|DELETE)[\s\S]{0,120}?(\+ \|f"\| % )` has FPs — keep the window tight and treat as high only on `f"`/`%`/`+` with a non-literal operand. |
| `DANGER_UNSAFE_YAML` | `yaml\.load(\|yaml\.unsafe_load(\|pickle\.loads(` | medium | `yaml.safe_load`/`yaml.full_load` NOT flagged. |
| `DANGER_TEMPLATE_ESCAPE_OFF` | `autoescape\s*=\s*False\|mark_safe(\|raw=` (Django/Jinja) | medium | — |
| `CONFIG_CORS_CREDENTIALS` | `allow_origins\s*=\s*["']\*["']` (or `['*']`) **plus** `allow_credentials\s*=\s*True` | high | The combination is the vulnerability; a single `["*"]` without credentials is medium. Two-rule correlation in the scanner (not one regex). |
| `CONFIG_DEBUG_TRUE` | `debug\s*=\s*True\|APP_DEBUG\s*=\s*true\|NODE_ENV\s*=\s*["']development["']` | medium | FP guard: `NODE_ENV` in `.github/workflows` CI config or test files — skip files under `.github/`, `test*/`, `spec*`. |
| `CONFIG_HARDCODED_SECRET_KEY` | `(?:SECRET_KEY\|JWT_SECRET\|signing_key\|SESSION_SECRET)\s*[=:]\s*["']([^"']+)["']` + **blocklist check** on the value | high | **Blocklist of known vibe-coding secrets** (this is the empirically verified FP killer): `supersecretkey`, `supersecretjwt`, `secret`, `changeme`, `password`, `your-secret-key`, `change-me`, `replace_me` [VERIFIED: Invicti — "supersecretkey" appeared in 1,182 of 20,000 vibe-coded apps; "supersecretjwt" is the most common GPT-5-generated secret]. Generic strong values (entropy ≥ 3.5) flagged medium. |
| `CONFIG_DEFAULT_CREDS` | `(?:username\|user\|login)\s*[=:]\s*["']admin["']` with `password\s*[=:]\s*["'](?:admin\|password\|123456)["']` within 3 lines; plus known pairs `admin/admin`, `root/root` | high | Correlation-based; `user: "admin"` alone in a seed file is medium. |

**Two rules the plan should add** (empirically top findings, cheap to detect):

| rule_id | Pattern | Severity | Notes |
|---|---|---|---|
| `CONFIG_SUPABASE_NO_RLS` | Presence of `createClient(...)` with a Supabase URL/anon key in frontend JS **and** absence of `rowLevelSecurity`/`create policy` in any `.sql` file in the repo | high | Detects the #1 real-world vibe-coded failure (Lovable CVE-2025-48757 — 303 vulnerable endpoints across 170 apps) [VERIFIED: CSA research note, CVE-2025-48757]. Cross-file correlation, not a single regex. |
| `SECRET_ENV_NEXT_PUBLIC` | `NEXT_PUBLIC_[A-Z_]*KEY\|NEXT_PUBLIC_[A-Z_]*SECRET\|NEXT_PUBLIC_[A-Z_]*TOKEN\s*=` in `.env*` or config | high | `NEXT_PUBLIC_` vars are compiled into client bundles by design — a key with this prefix is exposed to every visitor [VERIFIED: LaunchReadyCode — exposed keys in client bundles carried the highest CVSS (9.1) in their dataset]. |

**Implementation note:** keep `RULE` as a dataclass (plan's design is correct). Line numbers: use `enumerate(file_iter)` over text lines; binary detection via null-byte check in the first 8000 bytes before reading. Evidence truncation to ≤200 chars with secret masking (`sk-****…`) before persist — plan already has this; keep it.

---

## 3. Background Job Architecture Recommendation

**Recommendation: FastAPI `BackgroundTasks` + DB-persisted status + startup sweep.** Correct for this codebase: no worker infra exists (no Redis, no Celery, requirements.txt is minimal), scan runs are 30-120s, and the job record must survive in the DB for the frontend to poll.

### Tradeoffs

| Option | Restart-survival | Retries | Async support | Infra cost | Fits this codebase? |
|---|---|---|---|---|---|
| **`BackgroundTasks` (recommended MVP)** | ✗ in-process; **recovered by DB status + startup sweep** (see below) | ✗ (no attempt counter) | ✅ — accepts `async def` or `def` (official docs: "It can be an async def or normal def function") [VERIFIED: fastapi.tiangolo.com] | None | ✅ — zero new infra, plan already inserts `scan_runs` row |
| `asyncio.create_task` | ✗ | ✗ | ✅ | None | ⚠️ worse than BackgroundTasks — no reference held by Starlette ⇒ task can be garbage-collected mid-run; must keep a manual registry. Prefer BackgroundTasks. |
| Celery | ✅ durable | ✅ mature | bridged | Redis/RabbitMQ + worker tier | ✗ overkill for MVP |
| ARQ (Redis) | ✅ durable | ✅ `max_tries` | ✅ native | Redis + worker tier | ✗ same |
| DB-outbox + polling worker | ✅ | manual | ✅ | none (uses Postgres) | Option B — the "proper" pattern if scans must survive deploys; can be a later upgrade |

[VERIFIED: FastAPI docs; fastapi-patterns.com BackgroundTasks-vs-Celery-vs-ARQ (2025-2026); SO 79883964; fastapi discussion #7930]

### Key correctness facts

1. **`BackgroundTasks` supports async functions** [VERIFIED: official docs], but **blocking work inside an async task blocks the event loop** — the clone (subprocess), file walk, and the sync `OpenAI` client are all blocking. Two correct shapes:
   - **Shape A (simplest):** `run_scan` as a plain `def` (runs in threadpool). Inside it, DB writes need the async pool: create a fresh event loop in the thread (`asyncio.new_event_loop()`) and run async DB calls on it, OR use `asyncio.run_coroutine_threadsafe(coro, loop)` against the main loop. The plan's "call from asyncio.run inside thread" is this shape — fine.
   - **Shape B (cleaner):** `run_scan` as `async def`, with `await asyncio.to_thread(clone_repo, ...)`, `await asyncio.to_thread(scan_files, ...)`, and the LLM call in `to_thread` too (or use `AsyncOpenAI`). DB calls are then native `await db.xxx()`. **Recommend Shape B** — it matches the codebase's async-idiom (all routes are `async def`, database is asyncpg).
2. **Restart loss is real and must be handled honestly:** "Every time you update your code and redeploy, your server processes must restart. If a task is running or waiting to run when that restart happens, it gets killed" [VERIFIED: SO 79883964]. **Mitigation:** in the FastAPI lifespan startup, run `UPDATE scan_runs SET status='failed', error='server restarted mid-scan' WHERE status IN ('queued','running')`. Cheap, honest, keeps the UI consistent. A retry button ("Rescan") is the user-level recovery.
3. **Gunicorn worker timeout:** if deployed with gunicorn, its default `--timeout 30` kills workers running long background tasks [VERIFIED: fastapi discussion #7930]. Dev uses `uvicorn --reload` (fine). Document: production must either raise gunicorn timeout ≥ 300s or accept that scans die at 30s.
4. **One task per process, bounded concurrency:** BackgroundTasks shares the request worker. With `--workers N`, concurrent scans are bounded by N; a 120s scan occupies the slot. For MVP scale (personal tool) acceptable. Add a simple in-process semaphore (e.g., max 2 concurrent scans) to avoid pile-up, and return 409/429 if a scan for the same repo_url is already `queued`/`running` (duplicate-submission guard — cheap and useful).
5. **Route shape (per plan):** validate URL synchronously (fail fast, 400) → `insert_scan_run` (status `queued`) → `background_tasks.add_task(run_scan, scan_id, repo_url)` → return 201 with the queued run. Client polls `GET /scans/{id}`.

---

## 4. LLM Deep-Review Approach

### 4.1 Structured Outputs (not JSON mode)

- **Best practice 2025-2026: Structured Outputs** — `response_format={"type": "json_schema", "json_schema": {...}, "strict": True}` guarantees schema adherence via constrained decoding (required fields, enum severity, no extra keys). JSON mode (`json_object`) only guarantees "parses as JSON" and is documented as the legacy option; a documented 2025 bug produced truncated/invalid JSON with `finish_reason=stop` [VERIFIED: OpenAI cookbook; Respan 2026-05 comparison; OpenAI community bug report 1083001; toolchew 2026-06].
- **SDK:** installed openai SDK is **2.43.0** (verified in venv). Use the Pydantic-integrated path:

```python
from openai import OpenAI
from pydantic import BaseModel

class LLMFinding(BaseModel):
    category: str
    severity: str  # enum via Literal["critical","high","medium","low"]
    file: str
    line: int | None
    description: str
    remediation: str
    evidence: str

class LLMReview(BaseModel):
    findings: list[LLMFinding]
    summary: str | None

client = OpenAI(api_key=settings.OPENAI_API_KEY, timeout=60.0)  # or reuse _get_client() pattern from embeddings.py
resp = client.beta.chat.completions.parse(
    model=settings.LLM_MODEL,
    messages=[...],          # prompt below
    response_format=LLMReview,
    max_tokens=4000,
)
if resp.choices[0].message.refusal:      # model declined — treat as empty review, don't crash
    return []
result = resp.choices[0].message.parsed   # already a validated LLMReview
```

- `client.beta.chat.completions.parse` with Pydantic models is the documented recommended path [VERIFIED: OpenAI cookbook structured_outputs_intro]. The codebase's `embeddings.py` `_get_client()` pattern (module-level singleton) should be mirrored for the chat client.
- **Failure handling:** SDK retries 429/5xx automatically (`max_retries`, default 2). Set `timeout=60.0` on the client. Check `finish_reason == "length"` (truncation bypasses the schema guarantee — SDK raises `LengthFinishReasonError` in recent versions) → treat as failure, degrade. Wrap everything in try/except; on ANY exception → **rules-only mode** (log warning, continue) — exactly as the plan specifies. This guarantees the scan never hard-fails on an OpenAI outage. [VERIFIED: toolchew; jsonic 2026-05]

### 4.2 Model choice

| Model | Input/Output $/MTok | Coding index (Artificial Analysis) | Context | Verdict |
|---|---|---|---|---|
| `gpt-4o-mini` (plan default) | $0.15 / $0.60 | 11.4 | 128K | Cheapest; fine for 10-file review; supports Structured Outputs [VERIFIED: OpenAI API docs pricing page] |
| `gpt-4.1-mini` | $0.40 / $1.60 | 20.2 (2.7× input cost) | 1M | **Quality upgrade**: ~2.7× pricier but measurably better at coding (LiveCodeBench 48.3% vs 23.4%) [VERIFIED: OpenAI docs + llmbase.ai comparison] |
| `gpt-4.1-nano` | $0.10 / $0.40 | — | 1M | Cheapest 2025 option; likely too weak for security judgment — not recommended [ASSUMED] |

**Recommendation:** keep `LLM_MODEL` default `gpt-4o-mini` (plan's choice is cost-sane for MVP), make it configurable (already is, via settings), and note `gpt-4.1-mini` as the one-line upgrade for better review quality. Budget: 10 files × ~12k chars ≈ ~30-40k input tokens ≈ $0.006-0.02 per scan with 4o-mini — negligible.

### 4.3 Prompt structure

System prompt (kept close to plan, tightened for Structured Outputs — the "JSON only" instruction is now unnecessary, which removes a whole class of prompt-vs-schema conflicts):

```
You are a security auditor for AI-generated ("vibe-coded") web applications.
Review the provided files for OWASP Top 10 (2021) issues and common AI-generated
code malpractice: exposed secrets, missing auth/authorization, SQL injection via
string interpolation, unsafe eval/exec of variable input, XSS via innerHTML,
CORS misconfiguration, insecure defaults (debug on, predictable secrets),
hardcoded credentials, and IDOR patterns.

For each finding: assign severity (critical/high/medium/low), cite the exact
file and line, quote a short evidence snippet, and give a concrete remediation.
Do not report issues that are not present. Report at most 20 findings.
Prefer precision over recall — a false positive is worse than a miss.
```

- **File selection:** plan says rank by rule hits then size — correct. Also **strongly prefer** files not covered by any rule (the LLM adds most value on logic/auth flaws rules can't see: missing auth middleware, IDOR, business-logic). Mix: top rule-hit files + a few zero-hit files.
- **Truncation:** 12k chars/file cap per plan; include `path:line` headers so the model reports locations.
- **Post-processing (keep plan's):** clamp severity to allowed set (Pydantic enum does this), dedupe against rule findings by `(file, line, category)`, drop LLM findings that duplicate a rule finding, mask secrets in evidence.

---

## 5. Top Vibe-Coded Security Weaknesses (empirical, 2025-2026)

Ranked by evidence strength across the 2025-2026 studies. Regex-detectable in MVP marked ✅, LLM-assisted ⚠️:

| # | Weakness | Evidence | Detectable in MVP |
|---|---|---|---|
| 1 | **Hardcoded secrets / API keys in client-side code** (Supabase anon key, Stripe, OpenAI in JS bundles) | 308 of 1,072 live vibe-coded apps exposed the Supabase anon key in JS [CITED: symbioticsec.ai 2026-04]; 23% of 127 apps had exposed keys in client bundles, highest CVSS in dataset (9.1) [CITED: launchreadycode.com 2026-06]; 197,092 hardcoded secrets in 72% of 38,630 AI Android apps [CITED: Cybernews via CSA 2026-04] | ✅ `SECRET_*` + `SECRET_ENV_NEXT_PUBLIC` |
| 2 | **Missing RLS / open database access** | Lovable CVE-2025-48757: 303 vulnerable endpoints in 170 apps (no RLS, anon key in client JS) [CITED: CSA research note, CVE-2025-48757]; 172 sites allowed unauthenticated DELETE, 39 fully readable [CITED: symbioticsec]; 47% RLS disabled [CITED: launchreadycode]; Moltbook 4.75M records exposed (Jan 2026) [CITED: CSA] | ✅ `CONFIG_SUPABASE_NO_RLS` (cross-file) |
| 3 | **Missing auth / authorization (auth bypass, open endpoints, IDOR)** | 69 vulnerabilities across 15 apps from 5 agent platforms; most common class = API authorization logic [CITED: CSO Online 2026-01 / Tenzai]; Base44 auth bypass (Wiz, 2025-07); 2,000 of 5,000 corporate vibe apps with no auth at all [CITED: Red Access via TechTarget 2026-06]; IDOR 14% [CITED: launchreadycode] | ⚠️ LLM-only (no auth middleware can't be regexed) |
| 4 | **Predictable hardcoded JWT/secret keys** (`supersecretkey`, `supersecretjwt`) | "supersecretkey" in 1,182 of 20,000 apps; per-model common secrets; JWT forgery demonstrated [CITED: Invicti 20k-app analysis] | ✅ `CONFIG_HARDCODED_SECRET_KEY` blocklist |
| 5 | **Common hardcoded credentials** (`user@example.com:password123`, `admin/admin`) | [CITED: Invicti] | ✅ `CONFIG_DEFAULT_CREDS` |
| 6 | **CORS misconfiguration** (`*` + credentials, origin reflection) | 197 sites [CITED: symbioticsec]; 31% [CITED: launchreadycode] | ✅ `CONFIG_CORS_CREDENTIALS` |
| 7 | **No rate limiting on auth endpoints** | 68% of apps [CITED: launchreadycode] | ⚠️ LLM-only |
| 8 | **Missing HTTP security headers (CSP, HSTS, X-Frame-Options)** | 84% [CITED: launchreadycode]; 1,039/1,072 missing CSP [CITED: symbioticsec] | ⚠️ LLM-only (headers not in repo) |
| 9 | **`eval()`/`exec()` of dynamic input** | "dangerous optimization shortcuts such as use of eval() for dynamic execution" [CITED: CSA 2026-04] | ✅ `DANGER_EVAL` |
| 10 | **SQL injection via string interpolation** | Missing query parameterization 18%, CVSS 9.3 [CITED: launchreadycode]; Tenzai found SQLi/XSS much rarer than auth flaws but present [CITED: CSO] | ✅ `DANGER_SQL_CONCAT` |
| 11 | **XSS via `innerHTML` / `dangerouslySetInnerHTML` / `v-html`** | Present but declining [CITED: Invicti, CSO] | ✅ `DANGER_XSS_INNERHTML` |
| 12 | **Sensitive data in localStorage** | 29% [CITED: launchreadycode] | ⚠️ weak signal — LLM-only |
| 13 | **Debug flags / verbose stack traces / missing error boundaries** | 41% missing error boundary [CITED: launchreadycode] | ✅ `CONFIG_DEBUG_TRUE` (partial) |
| 14 | **Open signup / predictable auth endpoints** (`/api/login`, `/api/register`) | 220 sites open signup [CITED: symbioticsec]; predictable endpoints [CITED: Invicti] | ⚠️ LLM-only |
| 15 | **Insecure default storage rules (Firebase/cloud)** | Chat & Ask AI: Firebase `allow read: if true` exposed 406M records (Jan 2026); Tea App two breaches [CITED: CSA] | ⚠️ LLM-only (external config) |

**Context for design:** studies agree modern LLMs have largely stopped generating classic SQLi/XSS *in new code*, but systematically omit *security control layers* (auth, RLS, rate limiting, headers, secrets hygiene) [CITED: Invicti, CSA, launchreadycode]. This is why the plan's split is right: **regex rules catch the visible malpractice (secrets, unsafe APIs, config), and the LLM review catches the missing-control class** — the prompt should be explicitly oriented toward "what security control is MISSING" as much as "what bad pattern is present."

---

## 6. Scoring Model Recommendation

**Keep the plan's weighted penalty model** — it is defensible and matches how lightweight scanners behave:

```
score = max(0, 100 - (critical_count×25 + high_count×15 + medium_count×7 + low_count×3))
```

**Evidence from real scanners:**
- **Snyk Code Priority Score:** per-issue 0-1000 where severity ≈ 50% of the score (High=500, Medium=250, Low=100 points), plus additive points for occurrence, hotfiles, fix availability [VERIFIED: docs.snyk.io + snyk.io blog]. Additive severity-weighted — same family as the plan's model.
- **SonarQube:** A-E letter rating driven by the **worst single issue** (A = none, B = low, C = medium, D = high, E = blocker) — a max-based model, not additive [VERIFIED: docs.sonarsource.com].
- **npm audit:** severity counts, no aggregate number.
- **CVSS:** designed for single-vulnerability scoring with a fixed formula; not an aggregate-of-many-findings tool — using it to sum a repo report is a category error.

**Refinements (cheap, add defensibility):**
1. **Saturation:** document that 4+ criticals floors the score at 0 — that's intended behavior (a repo with 4 criticals is not "more broken than" one with 10, from a user's perspective; the finding count tells the rest).
2. **Add a letter grade as a secondary display** (SonarQube-style: A ≥ 90, B ≥ 75, C ≥ 50, D ≥ 25, F < 25 — tuned so one critical ≈ D). Gives users a familiar anchor without changing the math.
3. **Persist per-category sub-scores** (secrets_score, code_score, config_score) in `scan_runs.metadata` — enables the radar-style breakdown UI cheaply and makes the number explainable. Explainability matters more than precision here.
4. **Do NOT mix in LLM finding count naively:** LLM findings are capped at 20 and duplicated findings are deduped — apply the same severity weights to LLM findings so the model is consistent across both sources.

**Bottom line:** weighted penalty sum is the right MVP. It is additive like Snyk's, bounded like a percentage, and trivially testable (no findings = 100; one critical = 75; floor at 0). Any CVSS-style or ML-scored model is out of scope and lower defensibility-per-effort for a heuristic scan.

---

## 7. Frontend Polling Recommendation

**Use React Query v5 `refetchInterval` in function form** — this is the documented, idiomatic pattern and the codebase already uses `refetchInterval` (5s logs, 15s incidents, 30s health in `hooks.ts`) [VERIFIED: tanstack.com/query polling guide; existing hooks.ts].

```ts
export function useScan(id: string) {
  return useQuery({
    queryKey: ["scan", id],
    queryFn: () => getScan(id),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "completed" || status === "failed" ? false : 3000;
    },
  });
}
```

- Returning `false` clears the interval — polling auto-stops when the scan finishes [VERIFIED: TanStack docs].
- `useScans()` list: `refetchInterval: (query) => query.state.data?.some(s => s.status === "queued" || s.status === "running") ? 5000 : false` (plan says 3000 — either is fine; 3-5s matches the "user watching a spinner" guidance from 2026 polling articles).
- **No WebSockets/SSE for MVP** — unanimous 2025-2026 guidance: "If 'real-time' means 'within thirty seconds,' a refetchInterval on an existing query is the entire feature" [CITED: ma-x.im 2026-05, kenodo.com 2026-04, medium polling-vs-websockets 2025]. A scan takes 30-120s; 3-5s polling lag is invisible.
- After `useCreateScan` succeeds: `queryClient.invalidateQueries({ queryKey: ["scans"] })` and navigate to detail (plan's F3 behavior is correct).
- `refetchOnWindowFocus` (default true in v5) covers the "user came back from lunch" freshness case for free [VERIFIED: wolf-tech.io 2026-07].

---

## 8. Key Risks & Pitfalls with Mitigations

| # | Risk | Likelihood | Mitigation |
|---|---|---|---|
| R1 | **Regex FPs flood the report** (the #1 UX killer for a scanner) | High | gitleaks-verified patterns (AWS base32 alphabet, OpenAI `T3BlbkFJ` marker), entropy gate ≥3.5 for generic keys, blocklist + entropy for hardcoded secrets, `.env.example` exemption, skip `.github/`/test dirs for debug rules. Every rule ships with a unit-test fixture pair (positive + near-miss negative) — plan already specifies this. |
| R2 | **Clone timeout leaves orphaned git processes on Windows** → temp dir cleanup fails, disk fills | Medium | `Popen` + `taskkill /F /T /PID` tree kill (Section 1.2), stdout/stderr → DEVNULL (never PIPE), retry-loop `shutil.rmtree`, log-and-flag if cleanup still fails. |
| R3 | **Server restart kills in-flight scan** → UI stuck on "running" forever | Certain (eventually) | Lifespan startup sweep: mark `queued`/`running` → `failed` with "server restarted" (Section 3.2). Plus client-side polling stop on `failed`. |
| R4 | **Background task blocks the event loop** (subprocess / sync OpenAI inside async task) | High if Shape B ignored | Shape B: `await asyncio.to_thread(...)` for clone/walk/LLM; native async DB calls. Never call blocking IO directly in the async task. |
| R5 | **LLM output breaks the scan** (invalid JSON, refusal, truncation, OpenAI outage) | Medium | Structured Outputs + Pydantic parse; handle `refusal`; check `finish_reason == "length"`; try/except → rules-only fallback. Scan never hard-fails on LLM. |
| R6 | **Repo is huge** → clone+walk blows caps, disk exhaustion | Medium | `--depth 1 --single-branch --no-tags --no-recurse-submodules`, `MAX_REPO_SIZE_MB` + `MAX_SCAN_FILES` enforced *during* walk (abort early), cleanup in `finally`. Optionally `--filter=blob:limit=1m` later. |
| R7 | **Auto-created incidents pollute the existing incident pipeline** (every rescan duplicates incidents) | High | Dedupe: skip auto-create if an incident with `metadata.scan_id`+`finding_id` already exists (check before insert); mark `promoted_to_incident=True` in the same transaction; document that rescans are expected to re-promote only new findings. |
| R8 | **Rescan of the same repo creates duplicate runs** | Medium | 409 on POST if an active (queued/running) scan for the same repo_url exists. |
| R9 | **Secrets leak into logs/DB** (evidence fields contain real keys) | Medium | Evidence truncation ≤200 chars + masking (`sk-****…`); never log URLs with credentials (already rejected at validation); `LOG_LEVEL` respected; note in docs. |
| R10 | **SSRF via clever URL tricks** (encoded hosts, trailing dots, subdomain tricks, `@` smuggling) | Low (allowlist) | Exact-match host allowlist on `urlparse`-decoded hostname, reject credentials, reject trailing dot, `--` separator, protocol transport flags. Document DNS-rebinding residual risk as accepted for MVP. |
| R11 | **False sense of security** (users treat score 95 as "safe") | Certain | UI copy: "heuristic scan, not a guarantee — review findings manually"; score label "risk index"; summary line shows findings breakdown. Plan's docs note already frames the tool as defensive audit of own projects. |
| R12 | **LLM model price/latency creep** (large files → token blowup) | Medium | Caps already in plan (10 files, 12k chars); add a total-input-token budget guard (e.g., abort LLM phase if estimated input > 150k tokens → rules-only + notice). 4o-mini cost per scan ≈ $0.01-0.02. |
| R13 | **Gunicorn default worker timeout kills long tasks in prod** | If prod-deployed | Document gunicorn `--timeout 300` requirement; dev (uvicorn --reload) unaffected. |
| R14 | **Windows long-path errors while walking deep repos** | Medium | Per-file try/except on walk, log + continue; note longPathAware registry. |

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|---|---|---|---|---|
| git | repo clone | ✓ | 2.54.0.windows.1 | — |
| Python | backend | ✓ | 3.14.4 | — |
| openai SDK | LLM review | ✓ | 2.43.0 (venv) | rules-only mode if API key unset |
| Postgres (asyncpg) | scan_runs/scan_findings | ✓ (existing) | — | — |
| taskkill | Windows process-tree kill | ✓ (built into Windows) | — | — |
| `du` | repo size | ✗ (no Windows equivalent) | — | Python walk (Section 1.3) |

**Missing with fallback:** none blocking. `du` is replaced by a portable Python walker.

---

## What the Plan Should Change (deliberate deltas from VIBE_SCAN_IMPLEMENTATION_PLAN.md)

1. **Swap AWS/OpenAI regexes** for the gitleaks-verified patterns (Section 2) — the plan's versions FP badly.
2. **Clone command:** add `-c protocol.ext.allow=never -c protocol.file.allow=never --no-tags --no-recurse-submodules`, `--` separator, and the Windows tree-kill helper (Section 1.2).
3. **run_scan:** async coroutine + `asyncio.to_thread` for blocking stages (Shape B), not `asyncio.run` inside a thread.
4. **Add startup sweep** marking orphaned runs `failed` (Section 3).
5. **LLM:** `client.beta.chat.completions.parse` + Pydantic `response_format` (Structured Outputs) instead of `json_object`; keep rules-only fallback.
6. **Add 3 rules:** `CONFIG_SUPABASE_NO_RLS` (cross-file), `SECRET_ENV_NEXT_PUBLIC`, and a vibe-secrets blocklist for `CONFIG_HARDCODED_SECRET_KEY`.
7. **Score:** keep weighted model; add letter grade + per-category sub-scores in metadata (Section 6).
8. **Frontend:** function-form `refetchInterval` that stops on terminal status (Section 7).
9. **Incident dedupe guard** on auto-promotion (R7).

Everything else in the plan (module layout, DB schema, routes, frontend components, test list, task ordering) is validated as-is.

---

## Sources

### Primary (HIGH confidence)
- gitleaks rules repo — `config/gitleaks.toml`, `cmd/generate/config/rules/aws.go`, openai rule commit `ddcc753` (2025-03-27), AWS FP fix issue #1577/PR #1584: https://github.com/gitleaks/gitleaks
- FastAPI BackgroundTasks docs: https://fastapi.tiangolo.com/tutorial/background-tasks/
- Python subprocess docs (timeout/kill semantics): https://docs.python.org/3/library/subprocess.html ; Windows timeout bug: https://bugs.python.org/issue43346
- TanStack Query polling guide: https://tanstack.com/query/latest/docs/framework/react/guides/polling
- OpenAI Structured Outputs cookbook: https://developers.openai.com/cookbook/examples/structured_outputs_intro ; OpenAI API docs (gpt-4.1-mini pricing/rate limits): https://developers.openai.com/api/docs/models/gpt-4.1-mini
- Snyk Priority/Risk Score docs: https://docs.snyk.io/scan-fix-and-prevent/fix/prioritize-issues-for-fixing/priority-score
- SonarQube metrics docs: https://docs.sonarsource.com/sonarqube-server/user-guide/code-metrics/metrics-definition
- git docs — clone (`--filter`): https://git-scm.com/docs/git-clone ; partial clone: https://git-scm.com/docs/partial-clone.html
- Production clone-hardening implementations: https://github.com/svenroth-ai/shipwright (`scripts/lib/clone.py`), https://github.com/AutomatosAI/automatos-ai (`orchestrator/core/security/git_sanitizer.py`), https://github.com/Aureliolo/synthorg (`tools/_git_clone.py`, SSRF commit `492dd0d`)

### Secondary (MEDIUM confidence)
- CSA research note — AI-generated vulnerability debt (2026-04): https://labs.cloudsecurityalliance.org/research/csa-research-note-ai-codegen-vulnerability-debt-20260406-csa/ (covers CVE-2025-48757, Moltbook, Red Access numbers)
- CSO Online / Tenzai 5-platform study (2026-01): https://www.csoonline.com/article/4116923/output-from-vibe-coding-tools-prone-to-critical-security-flaws-study-finds.html
- SymbioticSec 1,072 vibe-coded apps study (2026-04): https://www.symbioticsec.ai/blog/we-scanned-1-072-vibe-coded-apps-98-had-security-flaws
- LaunchReadyCode State of Vibe Code Security (2026-06): https://launchreadycode.com/resources/state-of-vibe-code-security-june-2026
- Invicti 20,000 vibe-coded apps analysis: https://www.invicti.com/blog/security-labs/security-issues-in-vibe-coded-web-apps-analyzed
- Wiz Base44 advisory (2025-07): https://www.wiz.io/blog/critical-vulnerability-base44
- fastapi-patterns.com — BackgroundTasks vs Celery vs ARQ: https://fastapi-patterns.com/async-background-tasks-observability/background-task-processing/fastapi-backgroundtasks-vs-celery-vs-arq/ ; fastapi discussion #7930: https://github.com/fastapi/fastapi/discussions/7930
- Respan — Structured Outputs vs JSON mode (2026-05): https://www.respan.ai/articles/openai-structured-outputs-vs-json-mode
- Safeguard.sh Python URL validator / SSRF (2025-06): https://safeguard.sh/resources/blog/python-url-validator
- CursorTouch/Windows-MCP PR #151 — two-stage subprocess timeout on Windows (2026-03): https://github.com/CursorTouch/Windows-MCP/pull/151

### Tertiary (LOW confidence — used as context, not load-bearing)
- arXiv 2512.03262 (SUSVIBES benchmark) — vibe coding security evaluation
- TechTarget/Red Access coverage (2026-06); llmbase.ai model comparison (benchmark numbers only)

## Assumptions Log

| # | Claim | Status |
|---|-------|--------|
| A1 | GitHub PAT regexes (`ghp_[A-Za-z0-9]{36}`, `github_pat_[A-Za-z0-9_]{22,}`) | [ASSUMED] — standard formats; verify against current gitleaks.toml during implementation (one web check) |
| A2 | Stripe/SendGrid/Twilio key regexes | [ASSUMED] — optional MVP rules; confirm against gitleaks if added |
| A3 | gpt-4.1-nano unsuitable for security review | [ASSUMED] — no direct benchmark for security-judgment tasks |
| A4 | Letter-grade thresholds (A≥90/B≥75/C≥50/D≥25/F<25) | [ASSUMED] — tuned proposal, trivially adjustable |
| A5 | Scan duration 30-120s | [ASSUMED] — estimate; clone 5-60s + walk + LLM 10-40s for typical repos within caps |

## Open Questions (RESOLVED — decisions adopted by PLAN.md)

1. **Score severity weights (25/15/7/3)** — reasonable, but no empirical calibration source. [RESOLVED] Ship as-is (PLAN P4 Task 4.3), revisit after first 20 real scans (log score distribution).
2. **`gpt-4o-mini` vs `gpt-4.1-mini` default** — cost vs quality. [RESOLVED] Keep 4o-mini default (PLAN P1 Task 1.1), expose env var, document upgrade path (Section 4.2).
3. **Subdomain hosts** (e.g., self-hosted GitLab) — [RESOLVED] Out of MVP scope per plan's allowlist; revisit if requested.

---

## Metadata

**Confidence breakdown:**
- Cloning/URL validation: HIGH — verified against multiple production implementations + official docs
- Regex rules: HIGH for AWS/OpenAI (gitleaks-verified); MEDIUM for blocklist/entropy thresholds
- Background architecture: HIGH — official docs + multiple 2025-2026 sources agree
- LLM approach: HIGH for Structured Outputs choice; MEDIUM for model pick
- Scoring: HIGH for "weighted penalty is defensible"; LOW for specific weights
- Frontend polling: HIGH — official TanStack docs + codebase precedent
- Vibe-coded weakness ranking: MEDIUM — multiple 2025-2026 studies agree on the top classes, but methodology varies

**Research date:** 2026-08-07
**Valid until:** ~2026-09-07 (gitleaks/OpenAI move fast; regex and model tables should be re-verified before production hardening)
