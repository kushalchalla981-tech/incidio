#!/usr/bin/env python3
r"""
Load realistic mock incidents into the Incident Manager.

The loader:
  1. Truncates the `incidents` table (reset step) so re-running yields a
     clean, identical dataset.
  2. Creates each incident through the real API (POST /api/v1/incidents).
  3. Advances the status through the API's PATCH /api/v1/incidents/{id},
     which records realistic `status_changed` timeline events.
  4. Verifies the seeded data by listing incidents through the API.

Requirements:
  - Backend running at the API base URL (default http://127.0.0.1:8000).
  - PostgreSQL reachable at the DATABASE_URL in backend/.env (used only for
    the truncate/reset step).

Usage:
  cd backend && .\venv\Scripts\Activate.ps1        # or use the venv python directly
  python ../mock-data/load_mock_data.py

Optional:
  python ../mock-data/load_mock_data.py --no-reset     # skip truncating incidents
  python ../mock-data/load_mock_data.py --base http://127.0.0.1:8000
  python ../mock-data/load_mock_data.py --seed mock-data/incidents.seed.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
DEFAULT_SEED = PROJECT_ROOT / "mock-data" / "incidents.seed.json"
DEFAULT_BASE = "http://127.0.0.1:8000"

SEVERITIES = {"low", "medium", "high", "critical"}
STATUSES = {"open", "investigating", "resolved", "closed"}
# Status progression used for PATCHing; each step records one timeline event.
STATUS_CHAIN = {
    "open": [],
    "investigating": ["investigating"],
    "resolved": ["investigating", "resolved"],
    "closed": ["investigating", "resolved", "closed"],
}


def load_database_url() -> str | None:
    env_file = BACKEND_DIR / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                if key.strip() == "DATABASE_URL":
                    return value.strip()
    return os.environ.get("DATABASE_URL")


async def truncate_incidents(database_url: str) -> None:
    import asyncpg

    conn = await asyncpg.connect(database_url)
    try:
        await conn.execute("TRUNCATE TABLE incidents")
        print("[reset] incidents table truncated.")
    finally:
        await conn.close()


def resolve_record(record: dict, now: datetime) -> dict:
    """Add absolute start_time/end_time computed from the relative offsets."""
    start = now - timedelta(hours=record["start_hours_ago"])
    end = None
    if record.get("duration_hours") is not None:
        end = start + timedelta(hours=record["duration_hours"])
    return {
        **record,
        "start_time": start.isoformat(),
        "end_time": end.isoformat() if end else None,
    }


def build_create_payload(r: dict) -> dict:
    payload = {
        "title": r["title"],
        "severity": r["severity"],
        "start_time": r["start_time"],
    }
    if r.get("description"):
        payload["description"] = r["description"]
    if r.get("affected_services"):
        payload["affected_services"] = r["affected_services"]
    return payload


def build_final_patch(r: dict) -> dict:
    patch = {}
    if r.get("end_time"):
        patch["end_time"] = r["end_time"]
    if r.get("root_cause"):
        patch["root_cause"] = r["root_cause"]
    if r.get("resolution"):
        patch["resolution"] = r["resolution"]
    return patch


def validate(records: list[dict]) -> None:
    errors = []
    if not records:
        errors.append("Seed file contains no incidents.")
    for i, r in enumerate(records):
        if not r.get("title"):
            errors.append(f"[{i}] missing title")
        if r.get("severity") not in SEVERITIES:
            errors.append(f"[{i}] invalid severity: {r.get('severity')!r}")
        if r.get("status") not in STATUSES:
            errors.append(f"[{i}] invalid status: {r.get('status')!r}")
        if r.get("severity") in SEVERITIES and r.get("status") in ("resolved", "closed"):
            if r.get("duration_hours") is None:
                errors.append(f"[{i}] resolved/closed incident needs duration_hours")
            if not r.get("root_cause") or not r.get("resolution"):
                errors.append(f"[{i}] resolved/closed incident needs root_cause and resolution")
        if int(r.get("start_hours_ago", 0)) < 0:
            errors.append(f"[{i}] start_hours_ago must be >= 0")
    if errors:
        print("Seed validation failed:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        raise SystemExit(1)


async def main() -> None:
    parser = argparse.ArgumentParser(description="Load Incident Manager mock data")
    parser.add_argument("--seed", default=str(DEFAULT_SEED), help="Path to the seed JSON file")
    parser.add_argument("--base", default=DEFAULT_BASE, help="Backend API base URL")
    parser.add_argument("--no-reset", action="store_true", help="Skip truncating the incidents table")
    args = parser.parse_args()

    seed_path = Path(args.seed)
    if not seed_path.exists():
        print(f"Seed file not found: {seed_path}", file=sys.stderr)
        raise SystemExit(1)

    with seed_path.open(encoding="utf-8") as fh:
        records = json.load(fh)
    validate(records)

    client = httpx.Client(base_url=args.base.rstrip("/"), timeout=15.0)

    try:
        health = client.get("/health")
        health.raise_for_status()
        print(f"[api] backend reachable at {args.base} (status={health.json().get('status')})")
    except httpx.HTTPError as e:
        print(
            f"[api] could not reach the backend at {args.base} ({e}).\n"
            "Start the backend first, e.g. `uvicorn app.main:app --reload` from backend/.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    if not args.no_reset:
        database_url = load_database_url()
        if not database_url:
            print(
                "DATABASE_URL not found in backend/.env or environment; cannot reset. "
                "Re-run with --no-reset to skip truncation.",
                file=sys.stderr,
            )
            raise SystemExit(1)
        await truncate_incidents(database_url)
    else:
        print("[reset] skipped (--no-reset).")

    now = datetime.now(timezone.utc)
    created = []
    failures = []

    for record in records:
        resolved = resolve_record(record, now)
        try:
            resp = client.post("/api/v1/incidents", json=build_create_payload(resolved))
            resp.raise_for_status()
            incident = resp.json()
            incident_id = incident["id"]

            chain = STATUS_CHAIN[resolved["status"]]
            for idx, status in enumerate(chain):
                patch = {"status": status}
                if idx == len(chain) - 1:
                    patch.update(build_final_patch(resolved))
                patch_resp = client.patch(f"/api/v1/incidents/{incident_id}", json=patch)
                patch_resp.raise_for_status()

            created.append(incident_id)
            print(f'[ok] {resolved["severity"]:8s} {resolved["status"]:13s} {resolved["title"]}')
        except (httpx.HTTPError, ValueError) as e:
            failures.append((resolved["title"], str(e)))
            print(f"[fail] {resolved['title']}: {e}", file=sys.stderr)

    print("-" * 70)
    if failures:
        print(f"Created {len(created)} of {len(records)} incidents; {len(failures)} failed.")
        for title, err in failures:
            print(f"  - {title}: {err}", file=sys.stderr)
        raise SystemExit(1)

    verify = client.get("/api/v1/incidents", params={"limit": 500})
    verify.raise_for_status()
    rows = verify.json()
    by_status = {}
    by_severity = {}
    for r in rows:
        by_status[r["status"]] = by_status.get(r["status"], 0) + 1
        by_severity[r["severity"]] = by_severity.get(r["severity"], 0) + 1

    print(f"[verify] {len(rows)} incidents present via GET /api/v1/incidents")
    print(f"[verify] by status : {', '.join(f'{k}={v}' for k, v in sorted(by_status.items()))}")
    print(f"[verify] by severity: {', '.join(f'{k}={v}' for k, v in sorted(by_severity.items()))}")
    print("[done] mock data loaded.")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())