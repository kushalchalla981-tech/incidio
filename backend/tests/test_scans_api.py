import uuid
from pathlib import Path

from app.services.scanner import _finding_id

REPO_URL = "https://github.com/acme/app"


def _finding_id_for(rule_id, file, line):
    return _finding_id(REPO_URL, rule_id, file, line)


def _patch_scan_steps(monkeypatch, fake_db, tmp_path, findings=None, texts=None):
    """Point the real run_scan at a fake DB with stubbed clone/scan steps."""
    async def fake_get_db():
        return fake_db

    monkeypatch.setattr("app.services.scanner.get_db", fake_get_db)
    monkeypatch.setattr(
        "app.services.scanner.clone_repo",
        lambda url, scan_id: Path(tmp_path),
    )
    monkeypatch.setattr(
        "app.services.scanner.scan_repo",
        lambda repo_path, scanned=None: (findings or [], [], texts or {}, 0),
    )


async def test_run_scan_transitions_submitted_run_in_place(monkeypatch, fake_db, tmp_path):
    """The background task must complete the exact run the route created."""
    run = await fake_db.insert_scan_run(REPO_URL, "acme")
    _patch_scan_steps(monkeypatch, fake_db, tmp_path)

    from app.services.scanner import run_scan

    result = await run_scan(run["id"], REPO_URL)

    runs = await fake_db.get_scan_runs()
    assert len(runs) == 1
    assert runs[0]["id"] == run["id"]
    assert runs[0]["status"] == "completed"
    assert runs[0]["score"] == 100
    assert runs[0]["grade"] == "A"
    assert result["id"] == run["id"]
    assert result["status"] == "completed"


async def test_run_scan_marks_invalid_url_run_failed_in_place(monkeypatch, fake_db, tmp_path):
    run = await fake_db.insert_scan_run(REPO_URL)
    _patch_scan_steps(monkeypatch, fake_db, tmp_path)

    from app.services.scanner import run_scan

    await run_scan(run["id"], "file:///etc/passwd")

    runs = await fake_db.get_scan_runs()
    assert len(runs) == 1
    assert runs[0]["id"] == run["id"]
    assert runs[0]["status"] == "failed"
    assert "https" in runs[0]["error"]


async def test_run_scan_failed_clone_marks_run_failed(monkeypatch, fake_db, tmp_path):
    from app.services.scanner import ScanAbortError

    run = await fake_db.insert_scan_run(REPO_URL)
    async def fake_get_db():
        return fake_db

    monkeypatch.setattr("app.services.scanner.get_db", fake_get_db)
    monkeypatch.setattr(
        "app.services.scanner.clone_repo",
        lambda url, scan_id: (_ for _ in ()).throw(ScanAbortError("git clone failed (exit 128)")),
    )

    from app.services.scanner import run_scan

    await run_scan(run["id"], REPO_URL)

    runs = await fake_db.get_scan_runs()
    assert len(runs) == 1
    assert runs[0]["status"] == "failed"
    assert "git clone failed" in runs[0]["error"]


async def test_run_scan_persists_findings_and_auto_promotes(monkeypatch, fake_db, tmp_path):
    run = await fake_db.insert_scan_run(REPO_URL, "acme")
    findings = [
        {
            "rule_id": "SECRET_AWS_KEY",
            "severity": "critical",
            "category": "secrets",
            "file": "creds.py",
            "line": 2,
            "evidence": "AKIA****",
            "description": "AWS access key exposed in source",
            "remediation": "Rotate the key immediately and remove it from the repo",
        }
    ]
    _patch_scan_steps(monkeypatch, fake_db, tmp_path, findings=findings, texts={"creds.py": "x"})

    from app.services.scanner import run_scan

    await run_scan(run["id"], REPO_URL)

    saved = await fake_db.get_scan_findings(run["id"])
    assert len(saved) == 1
    assert saved[0]["rule_id"] == "SECRET_AWS_KEY"
    assert saved[0]["severity"] == "critical"
    assert saved[0]["scan_id"] == run["id"]
    assert saved[0]["promoted_to_incident"] is True

    incidents = list(fake_db.tables["incidents"].values())
    assert len(incidents) == 1
    assert incidents[0]["metadata"]["finding_id"] == _finding_id_for("SECRET_AWS_KEY", "creds.py", 2)
    assert incidents[0]["metadata"]["scan_id"] == run["id"]

    runs = await fake_db.get_scan_runs()
    assert runs[0]["score"] == 75
    assert runs[0]["grade"] == "B"


def test_create_scan_returns_201_and_queued(client, fake_run_scan):
    resp = client.post(
        "/api/v1/scans",
        json={"repo_url": REPO_URL, "name": "nightly"},
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["repo_url"] == REPO_URL
    assert body["name"] == "nightly"
    assert body["status"] == "queued"
    assert body["finding_count"] == 0
    assert len(fake_run_scan.calls) == 1
    assert fake_run_scan.calls[0] == (body["id"], REPO_URL)


async def test_create_scan_runs_background_scan_in_queued_order(client, fake_db, fake_run_scan):
    resp = client.post("/api/v1/scans", json={"repo_url": REPO_URL})

    assert resp.status_code == 201
    runs = await fake_db.get_scan_runs()
    assert len(runs) == 1
    assert runs[0]["id"] == resp.json()["id"]
    assert runs[0]["status"] == "queued"
    assert fake_run_scan.calls == [(runs[0]["id"], REPO_URL)]


async def test_create_scan_invalid_url_returns_400(client, fake_run_scan, fake_db):
    resp = client.post("/api/v1/scans", json={"repo_url": "https://evil.example.com/repo"})

    assert resp.status_code == 400
    assert "host not allowed" in resp.json()["detail"]
    assert fake_run_scan.calls == []
    assert await fake_db.get_scan_runs() == []


async def test_create_scan_duplicate_active_returns_409(client, fake_db, fake_run_scan):
    await fake_db.insert_scan_run(REPO_URL)

    resp = client.post("/api/v1/scans", json={"repo_url": REPO_URL})

    assert resp.status_code == 409
    assert fake_run_scan.calls == []


async def test_create_scan_completed_scan_does_not_conflict(client, fake_db):
    run = await fake_db.insert_scan_run(REPO_URL)
    await fake_db.update_scan_status(run["id"], "completed", score=90, grade="A")

    resp = client.post("/api/v1/scans", json={"repo_url": REPO_URL})

    assert resp.status_code == 201


def test_create_scan_missing_url_returns_422(client):
    resp = client.post("/api/v1/scans", json={})
    assert resp.status_code == 422


async def test_list_scans_returns_finding_count(client, fake_db):
    run_one = await fake_db.insert_scan_run("https://github.com/acme/one")
    run_two = await fake_db.insert_scan_run("https://github.com/acme/two")
    await fake_db.insert(
        "scan_findings",
        {
            "id": str(uuid.uuid4()),
            "scan_id": run_one["id"],
            "severity": "high",
            "category": "secrets",
            "rule_id": "SECRET_AWS_KEY",
            "file": "secrets.py",
            "line": 2,
            "evidence": "AKIA****",
            "description": "AWS Access Key",
        },
    )

    resp = client.get("/api/v1/scans")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    by_id = {row["id"]: row for row in data}
    assert by_id[run_one["id"]]["finding_count"] == 1
    assert by_id[run_two["id"]]["finding_count"] == 0


async def test_get_scan_returns_scan_and_findings(client, fake_db):
    run = await fake_db.insert_scan_run(REPO_URL, "acme")
    finding = await fake_db.insert(
        "scan_findings",
        {
            "id": str(uuid.uuid4()),
            "scan_id": run["id"],
            "severity": "critical",
            "category": "secrets",
            "rule_id": "SECRET_OPENAI_KEY",
            "file": "env.py",
            "line": 3,
            "evidence": "sk-****",
            "description": "OpenAI API key exposed in source",
            "remediation": "Revoke the key",
        },
    )

    resp = client.get(f"/api/v1/scans/{run['id']}")

    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == run["id"]
    assert body["repo_url"] == REPO_URL
    assert body["finding_count"] == 1
    assert len(body["findings"]) == 1
    assert body["findings"][0]["id"] == finding["id"]
    assert body["findings"][0]["severity"] == "critical"
    assert body["findings"][0]["file"] == "env.py"
    assert body["findings"][0]["promoted_to_incident"] is False


def test_get_scan_missing_returns_404(client):
    resp = client.get(f"/api/v1/scans/{uuid.uuid4()}")
    assert resp.status_code == 404


async def test_promote_finding_returns_201_and_sets_promoted_flag(client, fake_db):
    run = await fake_db.insert_scan_run(REPO_URL, "acme")
    finding_id = _finding_id_for("SECRET_AWS_KEY", "secrets.py", 7)
    await fake_db.insert(
        "scan_findings",
        {
            "id": finding_id,
            "scan_id": run["id"],
            "severity": "high",
            "category": "secrets",
            "rule_id": "SECRET_AWS_KEY",
            "file": "secrets.py",
            "line": 7,
            "evidence": "AKIA****",
            "description": "AWS Access Key",
            "remediation": "Rotate the key",
        },
    )

    resp = client.post(f"/api/v1/scans/{run['id']}/findings/{finding_id}/incident")

    assert resp.status_code == 201
    incident = resp.json()
    assert incident["title"] == "AWS Access Key in secrets.py"
    assert incident["severity"] == "high"
    assert incident["status"] == "open"
    assert incident["metadata"]["finding_id"] == finding_id
    assert incident["metadata"]["scan_id"] == run["id"]
    assert incident["metadata"]["repo_url"] == REPO_URL

    findings = await fake_db.get_scan_findings(run["id"])
    assert findings[0]["promoted_to_incident"] is True
    assert await fake_db.finding_has_incident(finding_id) is True


async def test_promote_finding_twice_returns_409(client, fake_db):
    run = await fake_db.insert_scan_run(REPO_URL)
    finding_id = _finding_id_for("SECRET_AWS_KEY", "secrets.py", 7)
    await fake_db.insert(
        "scan_findings",
        {
            "id": finding_id,
            "scan_id": run["id"],
            "severity": "high",
            "category": "secrets",
            "rule_id": "SECRET_AWS_KEY",
            "file": "secrets.py",
            "line": 7,
            "evidence": "AKIA****",
            "description": "AWS Access Key",
        },
    )

    first = client.post(f"/api/v1/scans/{run['id']}/findings/{finding_id}/incident")
    second = client.post(f"/api/v1/scans/{run['id']}/findings/{finding_id}/incident")

    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json()["detail"] == "Finding already promoted to an incident"


async def test_promote_finding_of_another_scan_returns_404(client, fake_db):
    run_one = await fake_db.insert_scan_run("https://github.com/acme/one")
    run_two = await fake_db.insert_scan_run("https://github.com/acme/two")
    finding_id = _finding_id("https://github.com/acme/two", "SECRET_AWS_KEY", "secrets.py", 7)
    await fake_db.insert(
        "scan_findings",
        {
            "id": finding_id,
            "scan_id": run_two["id"],
            "severity": "high",
            "category": "secrets",
            "rule_id": "SECRET_AWS_KEY",
            "file": "secrets.py",
            "line": 7,
            "evidence": "AKIA****",
            "description": "AWS Access Key",
        },
    )

    resp = client.post(f"/api/v1/scans/{run_one['id']}/findings/{finding_id}/incident")

    assert resp.status_code == 404
    assert resp.json()["detail"] == "Finding not found"


async def test_promote_finding_missing_scan_returns_404(client, fake_db):
    resp = client.post(
        f"/api/v1/scans/{uuid.uuid4()}/findings/{uuid.uuid4()}/incident"
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Scan not found"


async def test_promote_finding_missing_finding_returns_404(client, fake_db):
    run = await fake_db.insert_scan_run(REPO_URL)
    resp = client.post(
        f"/api/v1/scans/{run['id']}/findings/{uuid.uuid4()}/incident"
    )
    assert resp.status_code == 404
