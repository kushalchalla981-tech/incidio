import hashlib
import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app

SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def _is_valid_uuid(value) -> bool:
    try:
        uuid.UUID(str(value))
        return True
    except (ValueError, AttributeError, TypeError):
        return False


class _FakePool:
    """Minimal pool stub so _finalize_scan's finding-dedupe query works."""

    def __init__(self, db):
        self._db = db

    async def fetch(self, query: str, *args):
        if "scan_findings" in query:
            return []
        return []


class FakeDatabase:
    """In-memory replacement for app.database.Database used by the scan API."""

    def __init__(self):
        self.tables = {"scan_runs": {}, "scan_findings": {}, "incidents": {}, "security_projects": {}}
        self.pool = _FakePool(self)

    def _table(self, table: str) -> dict:
        if table not in self.tables:
            self.tables[table] = {}
        return self.tables[table]

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    def _normalize_id(self, table: str, record: dict) -> dict:
        result = dict(record)
        if "id" not in result:
            result["id"] = str(uuid.uuid4())
        if table == "incidents" and not _is_valid_uuid(result["id"]):
            digest = hashlib.md5(str(result["id"]).encode("utf-8")).hexdigest()
            result["id"] = str(uuid.UUID(digest))
        return result

    async def insert(self, table: str, data: dict) -> dict:
        record = self._normalize_id(table, data)
        if table == "scan_runs":
            now = self._now()
            record.setdefault("status", "queued")
            record.setdefault("total_files", 0)
            record.setdefault("finding_count", 0)
            record.setdefault("metadata", {})
            record.setdefault("created_at", now)
            record.setdefault("updated_at", now)
        elif table == "scan_findings":
            record.setdefault("promoted_to_incident", False)
        elif table == "incidents":
            now = self._now()
            record.setdefault("status", "open")
            record.setdefault("end_time", None)
            record.setdefault("resolution", None)
            record.setdefault("created_at", now)
            record.setdefault("updated_at", now)
        elif table == "security_projects":
            now = self._now()
            record.setdefault("created_at", now)
            record.setdefault("updated_at", now)
        self._table(table)[record["id"]] = record
        return dict(record)

    async def insert_batch(self, table: str, records: list[dict]) -> int:
        for record in records:
            await self.insert(table, record)
        return len(records)

    async def get_by_id(self, table: str, id: str):
        record = self._table(table).get(id)
        return dict(record) if record is not None else None

    async def update_by_id(self, table: str, id: str, data: dict):
        record = self._table(table).get(id)
        if record is None:
            return None
        record.update(data)
        self._table(table)[id] = record
        return dict(record)

    async def insert_scan_run(self, repo_url: str, name=None) -> dict:
        return await self.insert(
            "scan_runs", {"repo_url": repo_url, "name": name, "status": "queued"}
        )

    async def update_scan_status(
        self,
        scan_id: str,
        status: str,
        *,
        score=None,
        grade=None,
        summary=None,
        error=None,
        total_files=None,
        metadata=None,
    ) -> None:
        data = {"status": status, "updated_at": self._now()}
        if score is not None:
            data["score"] = score
        if grade is not None:
            data["grade"] = grade
        if summary is not None:
            data["summary"] = summary
        if error is not None:
            data["error"] = error
        if total_files is not None:
            data["total_files"] = total_files
        if metadata is not None:
            data["metadata"] = metadata
        await self.update_by_id("scan_runs", scan_id, data)

    async def get_scan_runs(self, limit: int = 50, offset: int = 0) -> list[dict]:
        runs = sorted(
            self._table("scan_runs").values(),
            key=lambda r: r.get("created_at") or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )
        result = []
        for run in runs[offset : offset + limit]:
            record = dict(run)
            record["finding_count"] = sum(
                1
                for f in self._table("scan_findings").values()
                if f.get("scan_id") == record["id"]
            )
            result.append(record)
        return result

    async def get_scan_run(self, scan_id: str):
        return await self.get_by_id("scan_runs", scan_id)

    async def get_scan_findings(self, scan_id: str) -> list[dict]:
        findings = [
            f for f in self._table("scan_findings").values() if f.get("scan_id") == scan_id
        ]
        findings.sort(key=lambda f: (SEVERITY_RANK.get(f.get("severity"), 9), f.get("file") or ""))
        return [dict(f) for f in findings]

    async def mark_finding_promoted(self, finding_id: str) -> None:
        record = self._table("scan_findings").get(finding_id)
        if record is not None:
            record["promoted_to_incident"] = True

    async def finding_has_incident(self, finding_id: str) -> bool:
        return any(
            incident.get("metadata", {}).get("finding_id") == finding_id
            for incident in self._table("incidents").values()
        )

    async def active_scan_for_repo(self, repo_url: str):
        for run in self._table("scan_runs").values():
            if run.get("repo_url") == repo_url and run.get("status") in ("queued", "running"):
                return dict(run)
        return None

    async def find_project(self, source_type: str, source_ref: str):
        for project in self._table("security_projects").values():
            if project.get("source_type") == source_type and project.get("source_ref") == source_ref:
                return dict(project)
        return None

    async def insert_project(self, name, source_type, source_ref):
        return await self.insert("security_projects", {
            "name": name,
            "source_type": source_type,
            "source_ref": source_ref,
        })

    async def get_project(self, project_id: str):
        return await self.get_by_id("security_projects", project_id)

    async def get_projects(self, limit=50, offset=0):
        projects = sorted(
            self._table("security_projects").values(),
            key=lambda p: p.get("updated_at") or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )
        result = []
        for p in projects[offset:offset + limit]:
            record = dict(p)
            last_scan = self._table("scan_runs").get(record.get("last_scan_id"))
            if last_scan:
                record["last_scan_status"] = last_scan.get("status")
                record["last_scan_score"] = last_scan.get("score")
                record["last_scan_grade"] = last_scan.get("grade")
                record["last_scan_summary"] = last_scan.get("summary")
                record["last_scan_created_at"] = last_scan.get("created_at")
            result.append(record)
        return result

    async def update_project_last_scan(self, project_id: str, scan_id: str) -> None:
        project = self._table("security_projects").get(project_id)
        if project is not None:
            project["last_scan_id"] = scan_id
            project["updated_at"] = self._now()

    async def get_scan_runs_for_project(self, project_id: str, limit=50, offset=0):
        runs = [
            r for r in self._table("scan_runs").values()
            if r.get("project_id") == project_id
        ]
        runs.sort(key=lambda r: r.get("created_at") or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
        result = []
        for run in runs[offset:offset + limit]:
            record = dict(run)
            record["finding_count"] = sum(
                1 for f in self._table("scan_findings").values()
                if f.get("scan_id") == record["id"]
            )
            result.append(record)
        return result

    async def update_finding_status(self, finding_id: str, status: str, note=None):
        return await self.update_by_id("scan_findings", finding_id, {"status": status, "status_note": note})

    async def query_findings(self, severity=None, category=None, status=None, project_id=None, limit=100, offset=0):
        findings = []
        for f in self._table("scan_findings").values():
            if severity and f.get("severity") != severity:
                continue
            if category and f.get("category") != category:
                continue
            if status and f.get("status") != status:
                continue
            if project_id:
                scan = self._table("scan_runs").get(f.get("scan_id"))
                if not scan or scan.get("project_id") != project_id:
                    continue
            findings.append(dict(f))
        findings.sort(key=lambda f: (SEVERITY_RANK.get(f.get("severity"), 9), f.get("file") or ""))
        return findings[offset:offset + limit]

    async def get_distinct_services(self) -> list[str]:
        return sorted({
            i.get("service")
            for i in self._table("incidents").values()
            if i.get("service")
        })


class FakeRunScan:
    """Async stub for app.api.v1.routes.scans.run_scan that records its calls."""

    def __init__(self):
        self.calls: list[tuple] = []

    async def run(self, repo_url, name=None):
        self.calls.append((repo_url, name))


@pytest.fixture
def fake_db():
    return FakeDatabase()


@pytest.fixture
def fake_run_scan():
    return FakeRunScan()


@pytest.fixture
def client(monkeypatch, fake_db, fake_run_scan):
    async def override_get_db():
        return fake_db

    monkeypatch.setattr("app.api.v1.routes.scans.get_db", override_get_db)
    monkeypatch.setattr("app.api.v1.routes.scans.run_scan", fake_run_scan.run)
    return TestClient(app)