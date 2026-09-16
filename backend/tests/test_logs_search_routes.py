from datetime import datetime, timezone
from uuid import uuid4

import pytest
from openai import OpenAIError

from app.api.v1.routes import logs as logs_route
from app.api.v1.routes import search as search_route

VALID_LOG_LINE = (
    "2026-08-14T10:00:00Z [api-gateway] ERROR "
    "connection refused to downstream service"
)

QUERY_VEC = [1.0, 0.0, 0.0]


class FakeLogsDb:
    def __init__(self):
        self.inserted_batches = 0
        self.templates = set()

    async def insert_batch(self, table, records):
        self.inserted_batches += len(records)
        return len(records)

    async def upsert_template(self, cluster_id, template):
        self.templates.add((cluster_id, template))


class FakeSearchDb:
    def __init__(self, rows):
        self.rows = rows

    async def get_all_embeddings(self):
        return self.rows


def _row(sim, service, level):
    return {
        "id": str(uuid4()),
        "timestamp": datetime(2026, 8, 14, 10, 0, 0, tzinfo=timezone.utc),
        "service": service,
        "level": level,
        "message": f"message for {service}",
        "raw_log": f"raw for {service}",
        "embedding": str([sim, 0.0, 0.0]),
    }


@pytest.fixture
def logs_db(monkeypatch):
    db = FakeLogsDb()

    async def _get_db():
        return db

    monkeypatch.setattr(logs_route, "get_db", _get_db)
    monkeypatch.setattr(logs_route, "parse_log", lambda raw: {
        "cluster_id": 1,
        "template": "template",
    })
    monkeypatch.setattr(logs_route, "extract_params", lambda raw, tpl: [])
    monkeypatch.setattr(logs_route, "batch_get_embeddings", lambda texts: [[0.1] for _ in texts])
    return db


@pytest.fixture
def search_db(monkeypatch):
    monkeypatch.setattr(search_route, "get_embedding", lambda query: QUERY_VEC)
    return monkeypatch


def _patch_search_db(monkeypatch, rows):
    async def _get_db():
        return FakeSearchDb(rows)

    monkeypatch.setattr(search_route, "get_db", _get_db)


def test_upload_empty_file_returns_200_processed_zero(client, logs_db):
    resp = client.post("/api/v1/logs/upload", files={"file": ("empty.log", b"", "text/plain")})

    assert resp.status_code == 200
    body = resp.json()
    assert body["logs_processed"] == 0
    assert body["logs_failed"] == 0
    assert body["errors"] == []


def test_upload_whitespace_only_file_returns_200_processed_zero(client, logs_db):
    resp = client.post(
        "/api/v1/logs/upload",
        files={"file": ("ws.log", b"\n\t \r\n  ", "text/plain")},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["logs_processed"] == 0
    assert body["logs_failed"] == 0
    assert body["errors"] == []


def test_upload_unparseable_lines_returns_failed_count(client, logs_db):
    resp = client.post(
        "/api/v1/logs/upload",
        files={"file": ("bad.log", b"this is not a log line\nneither is this", "text/plain")},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["logs_processed"] == 0
    assert body["logs_failed"] == 2
    assert len(body["errors"]) == 2
    assert all("Could not parse" in e for e in body["errors"])


def test_upload_normal_line_returns_processed_one(client, logs_db):
    resp = client.post(
        "/api/v1/logs/upload",
        files={"file": ("ok.log", VALID_LOG_LINE.encode(), "text/plain")},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["logs_processed"] == 1
    assert body["logs_failed"] == 0
    assert logs_db.inserted_batches == 1


def test_search_uses_each_rows_own_service_and_level(client, search_db):
    rows = [
        _row(0.9, "api-gateway", "error"),
        _row(0.8, "auth-service", "warning"),
        _row(0.7, "worker", "info"),
    ]
    _patch_search_db(search_db, rows)

    resp = client.post(
        "/api/v1/search",
        json={"query": "failure", "limit": 20},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert [r["service"] for r in body["results"]] == ["api-gateway", "auth-service", "worker"]
    assert [r["level"] for r in body["results"]] == ["ERROR", "WARNING", "INFO"]
    assert body["total"] == 3


def test_search_mixed_service_and_level_filter(client, search_db):
    rows = [
        _row(0.9, "api-gateway", "error"),
        _row(0.8, "api-gateway", "info"),
        _row(0.7, "worker", "error"),
    ]
    _patch_search_db(search_db, rows)

    resp = client.post(
        "/api/v1/search",
        json={"query": "failure", "limit": 20, "service": "api-gateway", "level": "error"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert len(body["results"]) == 1
    assert body["results"][0]["service"] == "api-gateway"
    assert body["results"][0]["level"] == "ERROR"


def test_search_no_matches_returns_empty_results(client, search_db):
    rows = [_row(0.9, "api-gateway", "error")]
    _patch_search_db(search_db, rows)

    resp = client.post(
        "/api/v1/search",
        json={"query": "failure", "limit": 20, "service": "nope"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["results"] == []
    assert body["total"] == 0


def test_search_without_api_key_returns_503(client, monkeypatch):
    def _raise_missing_credentials(_query):
        raise OpenAIError(
            "The api_key client option must be set either by passing api_key "
            "to the client or by setting the OPENAI_API_KEY environment variable"
        )

    monkeypatch.setattr(search_route, "get_embedding", _raise_missing_credentials)

    resp = client.post(
        "/api/v1/search",
        json={"query": "failure", "limit": 20},
    )

    assert resp.status_code == 503
    assert "unavailable" in resp.json()["detail"].lower()
