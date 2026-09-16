# Incident Manager Mock Data — Questions

This questionnaire helps define realistic mock data for the **Incident Manager** in AI Incident Copilot.

## How the Incident Manager works today

Before generating any data, these are the facts from the current implementation (the source of truth):

**Incident record fields** (from the `incidents` table and API):
- `id` — UUID (auto-generated)
- `title` — short incident title (required)
- `description` — free-text details
- `severity` — one of `low`, `medium`, `high`, `critical`
- `status` — one of `open`, `investigating`, `resolved`, `closed`
- `start_time` — when the incident began (required)
- `end_time` — when it was resolved (null while still open)
- `affected_services` — JSON list of service names (e.g. `["api-gateway", "db-primary"]`)
- `root_cause` — identified cause text (only set via PATCH/update, stays null on creation)
- `resolution` — how it was fixed (only set via PATCH/update)
- `metadata` — JSON blob; the only key currently read by the UI is `metadata.timeline` (activity history)
- `created_at` / `updated_at` — auto timestamps

**Statuses:** `open` → `investigating` → `resolved` → `closed` (all four valid; any value can be set via PATCH)

**What the UI displays:**
- **List page** — table of incidents with severity/status badges, first affected service, and start date; filters by status and severity
- **New Incident** — wizard collecting title, service, severity, start time, description, suspected root cause, planned resolution
- **Detail page** — full record plus a **Timeline** (rendered from `metadata.timeline` entries shaped like `{ action, from?, to?, timestamp, note? }`; status changes are the only event auto-recorded by the API today)
- **Dashboard** — KPIs: Active Incidents (`open`/`investigating`), Critical Alerts (open/investigating + `critical`), Resolved Today (resolved with `updated_at` today), MTTR (currently hardcoded); a "Recent Incidents" table (top 5)
- **Log Explorer** — a separate `logs` table; the incident manager never links incidents to log events today

**Known constraints:**
- There is **no users / roles / assignment model** in the schema or UI — no reporters, assignees, or on-call owners exist yet
- Incidents have no relationship to logs, deployments, or locations today
- Any new field or table would be a change to the existing data model and needs explicit approval

---

## Questions

### 1. Purpose
What should the mock data help you test or demonstrate?

- Example answers: "see realistic rows on the Incidents list", "test the detail-page timeline", "show off the dashboard KPIs", "a demo for stakeholders/usability testing"

### 2. Volume
How many incidents do you want? (Plus, if relevant: how many log entries for the Log Explorer?)

- Example answers: "about 10 incidents, no logs", "20 incidents + 40 log lines", "enough to make the dashboard KPIs non-zero"

### 3. Incident types
What kinds of incidents should appear, so they look realistic for this product?

- Example answers: "production outages and API timeouts", "database connection issues", "deploy regressions", "security-related incidents", "one of each common infra failure"

### 4. Incident details
How detailed should each incident be? Which fields matter most?

- Examples to choose from per incident:
  - `title` only
  - `title` + `description`
  - `title` + `description` + `root_cause` + `resolution` (complete records)
  - Complete records **plus** a multi-step `metadata.timeline`

### 5. Severity and status
Which severity/status values should be used, and in what mix?

- Severities: `low`, `medium`, `high`, `critical`
- Statuses: `open`, `investigating`, `resolved`, `closed`
- Example answers: "roughly half resolved, half active; at least one critical", "a full table one of each status + severity", "you decide the realistic mix"

### 6. Users and roles
The project has **no user model today**. Do you want to stay within the current model (no users), or should the mock data include a fictional team so incident texts mention reporters/owners?

- Example answers: "stay within the current model", "write descriptive text mentioning fictional team members (names only, no schema change)", "add a users field to the data model (needs schema/API changes)"

### 7. Timeline
Should incidents include realistic activity histories?

- Within a single incident's `metadata.timeline`, events can use `{ action, from?, to?, timestamp, note? }`.
- Actions you might want: `status_changed`, `note_added`, `acknowledged`, `escalated`, `root_cause_identified`, `resolved`.
- Example answers: "yes — 3–5 events per resolved incident", "just `status_changed` events", "timeline only for a few incidents, empty for the rest"

### 8. Relationships
Should incidents connect to other existing records?

- Today incidents only reference **services** (`affected_services`). The dashboard and list show the first one.
- The Log Explorer uses the separate `logs` table; the two are **not** linked.
- Example answers: "use a consistent set of service names across incidents + matching log entries", "incidents only, no logs", "services only, no log data"

### 9. Scenarios
Which special cases should the data cover?

- Examples: open incidents, resolved incidents, an **overdue/really old** open incident, a **critical active** incident, missing `end_time` on resolved rows, incident without description, incident whose service list is empty, a resolved-today incident (to drive the dashboard KPI)

### 10. Format
How should the mock data be stored and loaded?

- Options that fit this project:
  - **JSON seed file** + a small loader script that inserts via the API or directly into the database (recommended — matches the TEXT/JSON storage the app uses)
  - **SQL seed** (`psql` script inserting rows into `incidents`/`logs`)
  - Loaded **through the API** (POST `api/v1/incidents`, POST `api/v1/logs/batch`) — exercises the real endpoints

### 11. Environment and reset
Where should the data live, and how should it be reset?

- Examples: "local PostgreSQL via docker-compose", "the dev database", "load into a scratch database and truncate `incidents`/`logs` before each reload", "add a `reset` step that deletes only the seeded rows"

### 12. Additional requirements
Anything else you specifically want to show?

- Examples: "make the dashboard look healthy with a nice mix", "demo the 'Resolve Incident' button", "show filtering by severity/status", "identical to a real week at a small startup"