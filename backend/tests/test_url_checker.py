import pytest
import httpx

from app.services import url_checker


class FakeResp:
    def __init__(self, status_code=200, headers=None, text=""):
        self.status_code = status_code
        self.headers = httpx.Headers(headers or {})
        self.text = text
        self.url = "https://example.com/"


class FakeClient:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def close(self):
        pass

    def get(self, url, **kwargs):
        self.calls.append(url)
        if url in ("https://example.com", "https://example.com/"):
            return FakeResp(200)
        if url.startswith("http://"):
            return FakeResp(200)
        if url.endswith("/.env"):
            return FakeResp(200, {}, "API_KEY=secret123\nDB_PASS=xyz\n")
        if url.endswith("/.git/config"):
            return FakeResp(200, {}, "[core]\n\trepositoryformatversion = 0\n")
        if url.endswith("/admin"):
            return FakeResp(401)
        if url.endswith("/health"):
            return FakeResp(200, {}, '{"status":"ok"}')
        return FakeResp(404)


@pytest.fixture
def fake_httpx(monkeypatch):
    monkeypatch.setattr(url_checker.httpx, "Client", FakeClient)
    return FakeClient


def _fake_resolve(host):
    return [(2, 1, 6, "", ("93.184.216.34", 443))]


def _private_resolve(host):
    return [(2, 1, 6, "", ("127.0.0.1", 443))]


def test_validate_live_url_ok(monkeypatch):
    monkeypatch.setattr(url_checker, "_resolve_host", _fake_resolve)
    assert url_checker.validate_live_url("https://example.com/") == "https://example.com/"


def test_validate_live_url_rejects_http(monkeypatch):
    monkeypatch.setattr(url_checker, "_resolve_host", _fake_resolve)
    with pytest.raises(ValueError, match="https"):
        url_checker.validate_live_url("http://example.com")


def test_validate_live_url_rejects_credentials(monkeypatch):
    monkeypatch.setattr(url_checker, "_resolve_host", _fake_resolve)
    with pytest.raises(ValueError, match="credentials"):
        url_checker.validate_live_url("https://user:pass@example.com")


def test_validate_live_url_rejects_private_ip(monkeypatch):
    monkeypatch.setattr(url_checker, "_resolve_host", _private_resolve)
    with pytest.raises(ValueError, match="non-public"):
        url_checker.validate_live_url("https://example.com")


def test_validate_live_url_allow_private_flag(monkeypatch):
    monkeypatch.setattr(url_checker, "_resolve_host", _private_resolve)
    monkeypatch.setattr(url_checker.settings, "URL_ALLOW_PRIVATE_IP", True)
    assert url_checker.validate_live_url("https://example.com") == "https://example.com"


def test_validate_live_url_rejects_dotdot(monkeypatch):
    monkeypatch.setattr(url_checker, "_resolve_host", _fake_resolve)
    with pytest.raises(ValueError, match="\\.\\."):
        url_checker.validate_live_url("https://example.com/../../etc/passwd")


def test_validate_live_url_empty():
    with pytest.raises(ValueError):
        url_checker.validate_live_url("   ")


def test_run_url_checks_finds_issues(fake_httpx):
    findings = url_checker.run_url_checks("https://example.com")
    by_rule = {f["rule_id"]: f for f in findings}
    assert by_rule["URL_HEADER_CSP"]["severity"] == "medium"
    assert by_rule["URL_HEADER_HSTS"]["severity"] == "medium"
    assert by_rule["URL_NO_HTTPS_REDIRECT"]["severity"] == "medium"
    assert by_rule["URL_PATH_ENV_CONFIG"]["severity"] == "critical"
    assert by_rule["URL_PATH_GIT_CONFIG"]["severity"] == "critical"
    assert by_rule["URL_PATH_ADMIN_CONSOLE"]["severity"] == "informational"
    assert by_rule["URL_PATH_HEALTH_ENDPOINT"]["severity"] == "informational"
    assert all(f["source"] == "url_check" for f in findings)
    assert by_rule["URL_PATH_ENV_CONFIG"]["confidence"] == "confirmed"


def test_run_url_checks_secure_site(fake_httpx):
    class SecureFakeClient(FakeClient):
        def get(self, url, **kwargs):
            if url.startswith("http://"):
                return FakeResp(301)
            if url.endswith(("/.env", "/.git/config", "/.git/HEAD", "/actuator",
                             "/actuator/env", "/admin", "/health", "/robots.txt")):
                return FakeResp(404)
            headers = {
                "content-security-policy": "default-src 'self'",
                "strict-transport-security": "max-age=31536000",
                "x-content-type-options": "nosniff",
                "x-frame-options": "DENY",
                "referrer-policy": "strict-origin-when-cross-origin",
                "server": "nginx",
            }
            return FakeResp(200, headers)
    fake_httpx.get = SecureFakeClient.get
    findings = url_checker.run_url_checks("https://example.com")
    by_rule = {f["rule_id"]: f for f in findings}
    assert "URL_HEADER_CSP" not in by_rule
    assert "URL_HEADER_HSTS" not in by_rule
    assert "URL_HEADER_X_CONTENT_TYPE_OPTIONS" not in by_rule
    assert "URL_HEADER_X_FRAME_OPTIONS" not in by_rule
    assert "URL_HEADER_REFERRER_POLICY" not in by_rule
    assert "URL_NO_HTTPS_REDIRECT" not in by_rule
    assert "URL_PATH_ENV_CONFIG" not in by_rule
    assert "URL_PATH_GIT_CONFIG" not in by_rule
    assert by_rule["URL_INFO_SERVER_HEADER"]["severity"] == "informational"


def test_run_url_checks_unreachable(fake_httpx):
    class DownClient(FakeClient):
        def get(self, url, **kwargs):
            raise httpx.ConnectError("refused")
    fake_httpx.get = DownClient.get
    findings = url_checker.run_url_checks("https://example.com")
    assert len(findings) == 1
    assert findings[0]["rule_id"] == "URL_REQUEST_FAILED"


def test_run_url_checks_http_error(fake_httpx):
    class ErrorClient(FakeClient):
        def get(self, url, **kwargs):
            return FakeResp(503)
    fake_httpx.get = ErrorClient.get
    findings = url_checker.run_url_checks("https://example.com")
    assert len(findings) == 1
    assert findings[0]["rule_id"] == "URL_UNREACHABLE"


def test_run_url_checks_cookie_flags(fake_httpx):
    class CookieClient(FakeClient):
        def get(self, url, **kwargs):
            headers = {"set-cookie": "session=abc123; Path=/"}
            return FakeResp(200, headers)
    fake_httpx.get = CookieClient.get
    findings = url_checker.run_url_checks("https://example.com")
    rules = {f["rule_id"] for f in findings}
    assert "URL_COOKIE_NO_SECURE" in rules
    assert "URL_COOKIE_NO_HTTPONLY" in rules