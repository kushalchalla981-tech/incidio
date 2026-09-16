import io
import uuid
import zipfile

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.scanner import _finding_id
from tests.conftest import FakeDatabase


class FakeSecurityRun:
    """Inert stub for app.api.v1.routes.security.run_security_scan that records calls."""

    def __init__(self):
        self.calls: list[tuple] = []

    async def run(self, scan_id, source_type, source_ref, options):
        self.calls.append((scan_id, source_type, source_ref, options))


@pytest.fixture
def security_client(monkeypatch, fake_db):
    async def override_get_db():
        return fake_db

    runner = FakeSecurityRun()
    monkeypatch.setattr("app.api.v1.routes.security.get_db", override_get_db)
    monkeypatch.setattr("app.api.v1.routes.security.run_security_scan", runner.run)
    client = TestClient(app)
    client.runner = runner
    return client


def _zip_bytes() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("app/main.py", "print('hi')\n")
    return buf.getvalue()


def _finding(scan_id, rule, file, line, status="open", severity="high"):
    return {
        "id": _finding_id("", rule, file, line),
        "scan_id": scan_id, "rule_id": rule, "severity": severity,
        "category": "code", "file": file, "line": line, "title": rule,
        "status": status, "confidence": "confirmed", "source": "code",
        "evidence": f"{rule} found in {file}",
        "description": f"Finding {rule} in {file}",
    }


def _complete(fake_db, scan_id, project_id=None):
    import asyncio
    asyncio.run(fake_db.update_scan_status(scan_id, "completed", score=72, grade="C"))
    if project_id:
        asyncio.run(fake_db.update_project_last_scan(project_id, scan_id))


def test_create_repo_scan_queues(security_client):
    resp = security_client.post("/api/v1/security/scans", json={
        "source_type": "repo",
        "source_ref": "https://github.com/acme/demo",
        "name": "Demo",
    })
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["status"] == "queued"
    assert data["source_type"] == "repo"
    assert data["scan_version"] == "1.0.0"
    assert security_client.runner.calls[0][1] == "repo"


def test_create_repo_scan_invalid_url(security_client):
    resp = security_client.post("/api/v1/security/scans", json={
        "source_type": "repo",
        "source_ref": "https://evil.example.com/repo",
    })
    assert resp.status_code == 400


def test_create_url_scan_rejects_http(security_client):
    resp = security_client.post("/api/v1/security/scans", json={
        "source_type": "url",
        "source_ref": "http://example.com",
    })
    assert resp.status_code == 400


def test_create_zip_scan_via_json_rejected(security_client):
    resp = security_client.post("/api/v1/security/scans", json={
        "source_type": "zip",
        "source_ref": "bundle.zip",
    })
    assert resp.status_code == 422


def test_create_zip_scan_upload(security_client, fake_db, tmp_path, monkeypatch):
    monkeypatch.setattr("app.api.v1.routes.security.SCAN_TMP", str(tmp_path))
    resp = security_client.post(
        "/api/v1/security/scans/zip",
        files={"file": ("bundle.zip", _zip_bytes(), "application/zip")},
        data={"name": "Bundle"},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["source_type"] == "zip"
    assert (tmp_path / f"{data['id']}.zip").exists()
    project = fake_db.tables["security_projects"][data["project_id"]]
    assert project["source_type"] == "zip"


def test_create_zip_scan_rejects_garbage(security_client):
    resp = security_client.post(
        "/api/v1/security/scans/zip",
        files={"file": ("bundle.zip", b"not a zip file at all", "application/zip")},
    )
    assert resp.status_code == 400


def test_duplicate_active_scan_conflict(security_client, fake_db):
    first = security_client.post("/api/v1/security/scans", json={
        "source_type": "repo",
        "source_ref": "https://github.com/acme/demo2",
        "name": "Demo2",
    })
    assert first.status_code == 201
    second = security_client.post("/api/v1/security/scans", json={
        "source_type": "repo",
        "source_ref": "https://github.com/acme/demo2",
    })
    assert second.status_code == 409


def test_list_projects(security_client, fake_db):
    created = security_client.post("/api/v1/security/scans", json={
        "source_type": "repo",
        "source_ref": "https://github.com/acme/demo3",
        "name": "Demo3",
    }).json()
    _complete(fake_db, created["id"], created["project_id"])
    resp = security_client.get("/api/v1/security/projects")
    assert resp.status_code == 200
    projects = resp.json()
    assert len(projects) == 1
    assert projects[0]["name"] == "Demo3"
    assert projects[0]["last_scan_status"] == "completed"
    assert projects[0]["last_scan_score"] == 72


def test_get_project_with_scans(security_client, fake_db):
    created = security_client.post("/api/v1/security/scans", json={
        "source_type": "repo",
        "source_ref": "https://github.com/acme/demo4",
    }).json()
    resp = security_client.get(f"/api/v1/security/projects/{created['project_id']}")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["scans"]) == 1
    assert data["scans"][0]["id"] == created["id"]


def test_get_project_not_found(security_client):
    assert security_client.get("/api/v1/security/projects/nope").status_code == 404


def test_list_security_scans(security_client):
    security_client.post("/api/v1/security/scans", json={
        "source_type": "repo",
        "source_ref": "https://github.com/acme/demo5",
    })
    resp = security_client.get("/api/v1/security/scans")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_get_security_scan_detail(security_client, fake_db):
    created = security_client.post("/api/v1/security/scans", json={
        "source_type": "repo",
        "source_ref": "https://github.com/acme/demo6",
    }).json()
    finding_id = str(uuid.uuid4())
    rec = _finding(created["id"], "HARDCODED_SECRET", "app/main.py", 3)
    rec["id"] = finding_id
    fake_db.tables["scan_findings"][finding_id] = rec
    resp = security_client.get(f"/api/v1/security/scans/{created['id']}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["finding_count"] == 1
    assert data["findings"][0]["id"] == finding_id


def test_scan_not_found(security_client):
    assert security_client.get("/api/v1/security/scans/nope").status_code == 404


def test_update_finding_status(security_client, fake_db):
    created = security_client.post("/api/v1/security/scans", json={
        "source_type": "repo",
        "source_ref": "https://github.com/acme/demo7",
    }).json()
    finding_id = str(uuid.uuid4())
    fake_db.tables["scan_findings"][finding_id] = _finding(
        created["id"], "X", "a.py", 1, severity="low"
    )
    resp = security_client.patch(f"/api/v1/security/findings/{finding_id}", json={
        "status": "accepted",
        "note": "false positive",
    })
    assert resp.status_code == 200
    assert resp.json()["status"] == "accepted"
    assert resp.json()["status_note"] == "false positive"
    assert security_client.patch("/api/v1/security/findings/nope", json={"status": "open"}).status_code == 404


def test_query_findings_filters(security_client, fake_db):
    created = security_client.post("/api/v1/security/scans", json={
        "source_type": "repo",
        "source_ref": "https://github.com/acme/demo8",
    }).json()
    fake_db.tables["scan_findings"][str(uuid.uuid4())] = _finding(
        created["id"], "A", "a.py", 1, severity="critical"
    )
    fake_db.tables["scan_findings"][str(uuid.uuid4())] = {
        **_finding(created["id"], "B", "b.py", 2, status="resolved", severity="low"),
        "category": "url",
        "source": "url_check",
        "file": "",
        "line": None,
    }
    crit = security_client.get("/api/v1/security/findings?severity=critical").json()
    assert len(crit) == 1 and crit[0]["rule_id"] == "A"
    opened = security_client.get("/api/v1/security/findings?status=open").json()
    assert len(opened) == 1 and opened[0]["rule_id"] == "A"
    url = security_client.get("/api/v1/security/findings?category=url").json()
    assert len(url) == 1 and url[0]["rule_id"] == "B"
    assert len(security_client.get("/api/v1/security/findings").json()) == 2


def test_rerun_scan(security_client, fake_db):
    created = security_client.post("/api/v1/security/scans", json={
        "source_type": "repo",
        "source_ref": "https://github.com/acme/demo9",
        "name": "Demo9",
    }).json()
    _complete(fake_db, created["id"])
    resp = security_client.post(f"/api/v1/security/scans/{created['id']}/rerun")
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["source_ref"] == "https://github.com/acme/demo9"
    assert data["project_id"] == created["project_id"]
    assert security_client.runner.calls[-1][2] == "https://github.com/acme/demo9"


def test_rerun_missing_scan(security_client):
    assert security_client.post("/api/v1/security/scans/nope/rerun").status_code == 404


def test_compare_scans(security_client, fake_db):
    base = security_client.post("/api/v1/security/scans", json={
        "source_type": "repo", "source_ref": "https://github.com/acme/compare",
    }).json()
    _complete(fake_db, base["id"])
    target = security_client.post("/api/v1/security/scans", json={
        "source_type": "repo", "source_ref": "https://github.com/acme/compare",
    }).json()
    _complete(fake_db, target["id"])
    project_id = base["project_id"]

    fake_db.tables["scan_findings"][f"{base['id']}:{_finding_id('', 'SECRET', 'a.py', 1)}"] = _finding(base["id"], "SECRET", "a.py", 1)
    fake_db.tables["scan_findings"][f"{base['id']}:{_finding_id('', 'FIXED', 'b.py', 2)}"] = _finding(base["id"], "FIXED", "b.py", 2)
    fake_db.tables["scan_findings"][f"{target['id']}:{_finding_id('', 'SECRET', 'a.py', 1)}"] = _finding(target["id"], "SECRET", "a.py", 1)
    fake_db.tables["scan_findings"][f"{target['id']}:{_finding_id('', 'FIXED', 'b.py', 2)}"] = _finding(target["id"], "FIXED", "b.py", 2, status="resolved")
    fake_db.tables["scan_findings"][f"{target['id']}:{_finding_id('', 'NEW', 'c.py', 3)}"] = _finding(target["id"], "NEW", "c.py", 3)

    resp = security_client.get(f"/api/v1/security/projects/{project_id}/compare",
                               params={"base": base["id"], "target": target["id"]})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert [i["title"] for i in data["added"]] == ["NEW"]
    assert [i["title"] for i in data["removed"]] == []
    assert [i["title"] for i in data["status_changed"]] == ["FIXED"]
    assert data["unchanged"] == 1


def test_compare_rejects_cross_project(security_client, fake_db):
    a = security_client.post("/api/v1/security/scans", json={
        "source_type": "repo", "source_ref": "https://github.com/acme/pa",
    }).json()
    b = security_client.post("/api/v1/security/scans", json={
        "source_type": "repo", "source_ref": "https://github.com/acme/pb",
    }).json()
    resp = security_client.get(f"/api/v1/security/projects/{a['project_id']}/compare",
                               params={"base": a["id"], "target": b["id"]})
    assert resp.status_code == 400


def _incident(incident_id: str, service: str = "api") -> dict:
    return {
        "id": incident_id, "title": "T", "service": service, "status": "open",
        "severity": "high", "description": "desc", "start_time": "2026-01-01T00:00:00Z",
        "end_time": None, "resolution": None, "affected_services": [service],
        "root_cause": "cause", "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z", "metadata": {},
    }


def test_incident_services_endpoint(monkeypatch, fake_db):
    async def override_get_db():
        return fake_db

    monkeypatch.setattr("app.api.v1.routes.incidents.get_db", override_get_db)
    client = TestClient(app)
    id1, id2 = str(uuid.uuid4()), str(uuid.uuid4())
    fake_db.tables["incidents"][id1] = _incident(id1, "api-gateway")
    fake_db.tables["incidents"][id2] = _incident(id2, "auth-service")
    fake_db.tables["incidents"][id2]["severity"] = "low"
    resp = client.get("/api/v1/incidents/services")
    assert resp.status_code == 200
    services = resp.json()
    assert sorted(services) == ["api-gateway", "auth-service"]


def test_incident_status_change_records_timeline(monkeypatch, fake_db):
    async def override_get_db():
        return fake_db

    monkeypatch.setattr("app.api.v1.routes.incidents.get_db", override_get_db)
    client = TestClient(app)
    incident_id = str(uuid.uuid4())
    fake_db.tables["incidents"][incident_id] = _incident(incident_id)
    resp = client.patch(f"/api/v1/incidents/{incident_id}", json={"status": "resolved", "resolution": "fixed"})
    assert resp.status_code == 200, resp.text
    metadata = resp.json()["metadata"]
    assert len(metadata["timeline"]) == 1
    entry = metadata["timeline"][0]
    assert entry["from"] == "open"
    assert entry["to"] == "resolved"
    assert entry["action"] == "status_changed"

    resp = client.patch(f"/api/v1/incidents/{incident_id}", json={"status": "open"})
    metadata = resp.json()["metadata"]
    assert len(metadata["timeline"]) == 2


def test_incident_patch_no_status_change_no_timeline(monkeypatch, fake_db):
    async def override_get_db():
        return fake_db

    monkeypatch.setattr("app.api.v1.routes.incidents.get_db", override_get_db)
    client = TestClient(app)
    incident_id = str(uuid.uuid4())
    fake_db.tables["incidents"][incident_id] = _incident(incident_id)
    resp = client.patch(f"/api/v1/incidents/{incident_id}", json={"severity": "medium"})
    assert resp.status_code == 200
    assert resp.json()["metadata"] == {}