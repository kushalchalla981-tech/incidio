import asyncio
from datetime import datetime, timezone

import pytest
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.main import app, lifespan
from app.middleware import SECURITY_HEADERS

POST_PATH = "/api/v1/anomalies/detect"
GET_PATH = "/api/v1/anomalies/detect"


class FakeAnomalyDb:
    def __init__(self, logs):
        self.logs = logs

    async def query_logs_range(self, service=None, start_time=None, end_time=None):
        return self.logs


def _logs():
    return [
        {
            "id": "1",
            "timestamp": datetime(2026, 8, 14, 10, 0, 0, tzinfo=timezone.utc),
            "service": "api",
            "level": "ERROR",
            "template_id": 1,
        },
        {
            "id": "2",
            "timestamp": datetime(2026, 8, 14, 10, 5, 0, tzinfo=timezone.utc),
            "service": "api",
            "level": "INFO",
            "template_id": 2,
        },
        {
            "id": "3",
            "timestamp": datetime(2026, 8, 14, 10, 10, 0, tzinfo=timezone.utc),
            "service": "worker",
            "level": "INFO",
            "template_id": 3,
        },
    ]


def _patch_anomaly_db(monkeypatch, logs):
    async def _get_db():
        return FakeAnomalyDb(logs)

    monkeypatch.setattr("app.api.v1.routes.anomalies.get_db", _get_db)


def _cors_middleware_kwargs():
    for m in app.user_middleware:
        if m.cls is CORSMiddleware:
            return m.kwargs
    return {}


def test_cors_wildcard_disables_credentials():
    kwargs = _cors_middleware_kwargs()
    assert kwargs["allow_origins"] == ["*"]
    assert kwargs["allow_credentials"] is False


def test_cors_explicit_origins_enable_credentials(monkeypatch):
    monkeypatch.setattr(settings, "CORS_ORIGINS", ["https://app.example.com"])
    assert settings.cors_allow_credentials is True


def test_cors_property_default_wildcard_disables_credentials():
    assert "*" in settings.CORS_ORIGINS
    assert settings.cors_allow_credentials is False


def test_cors_preflight_with_wildcard_never_returns_credentials(client):
    resp = client.options(
        POST_PATH,
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == "*"
    assert resp.headers.get("access-control-allow-credentials") is None


def test_security_headers_on_every_response(client):
    resp = client.get("/does-not-exist")
    assert resp.status_code == 404
    for name, value in SECURITY_HEADERS.items():
        assert resp.headers[name.lower()] == value


def test_anomaly_window_minutes_zero_rejected(client):
    resp = client.post(POST_PATH, json={"window_minutes": 0})
    assert resp.status_code == 422


def test_anomaly_window_minutes_over_max_rejected(client):
    resp = client.post(POST_PATH, json={"window_minutes": 1441})
    assert resp.status_code == 422


def test_anomaly_contamination_zero_rejected(client):
    resp = client.post(POST_PATH, json={"contamination": 0})
    assert resp.status_code == 422


def test_anomaly_contamination_over_max_rejected(client):
    resp = client.post(POST_PATH, json={"contamination": 0.51})
    assert resp.status_code == 422


def test_anomaly_get_window_minutes_zero_rejected(client):
    resp = client.get(GET_PATH, params={"window_minutes": 0})
    assert resp.status_code == 422


def test_anomaly_get_contamination_out_of_range_rejected(client):
    resp = client.get(GET_PATH, params={"contamination": 0.51})
    assert resp.status_code == 422


def test_anomaly_post_boundary_values_accepted(client, monkeypatch):
    _patch_anomaly_db(monkeypatch, _logs())
    resp = client.post(
        POST_PATH,
        json={"window_minutes": 1440, "contamination": 0.5},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["contamination"] == 0.5
    assert body["total_windows"] > 0


def test_anomaly_get_lower_boundary_accepted(client, monkeypatch):
    _patch_anomaly_db(monkeypatch, _logs())
    resp = client.get(GET_PATH, params={"window_minutes": 1, "contamination": 0.01})
    assert resp.status_code == 200
    assert resp.json()["contamination"] == 0.01


def test_anomaly_zero_logs_returns_404(client, monkeypatch):
    _patch_anomaly_db(monkeypatch, [])
    resp = client.post(POST_PATH, json={})
    assert resp.status_code == 404
    assert resp.json()["detail"] == "No logs found in the specified range"


class _DummyDb:
    def __init__(self):
        self.closed = False

    async def close(self):
        self.closed = True


def test_lifespan_development_continues_when_db_unavailable(monkeypatch):
    async def _boom():
        raise ConnectionError("db down")

    calls = []
    monkeypatch.setattr("app.main.get_db", _boom)
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")

    async def run():
        async with lifespan(None):
            calls.append("entered")

    asyncio.run(run())
    assert calls == ["entered"]


def test_lifespan_production_fails_when_db_unavailable(monkeypatch):
    async def _boom():
        raise ConnectionError("db down")

    monkeypatch.setattr("app.main.get_db", _boom)
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")

    async def run():
        async with lifespan(None):
            pass

    with pytest.raises(ConnectionError):
        asyncio.run(run())


def test_lifespan_runs_sweep_when_db_available(monkeypatch):
    db = _DummyDb()
    calls = []

    async def _get_db():
        return db

    async def _sweep():
        calls.append("sweep")

    monkeypatch.setattr("app.main.get_db", _get_db)
    monkeypatch.setattr("app.main.sweep_orphaned_scans", _sweep)
    monkeypatch.setattr("app.main.get_miner", lambda: calls.append("miner"))

    async def run():
        async with lifespan(None):
            calls.append("entered")

    asyncio.run(run())
    assert calls == ["sweep", "miner", "entered"]
    assert db.closed is True