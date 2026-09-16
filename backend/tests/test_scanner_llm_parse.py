from types import SimpleNamespace

import pytest
from openai import OpenAIError

import app.services.scanner as scanner_module


class FakeCompletions:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.response


class FakeChat:
    def __init__(self, response=None, error=None):
        self.completions = FakeCompletions(response=response, error=error)


class FakeBeta:
    def __init__(self, response=None, error=None):
        self.chat = FakeChat(response=response, error=error)


class FakeClient:
    def __init__(self, response=None, error=None):
        self.beta = FakeBeta(response=response, error=error)

    @property
    def completions(self):
        return self.beta.chat.completions


def make_response(parsed=None, refusal=None):
    message = SimpleNamespace(parsed=parsed, refusal=refusal)
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def make_llm_review(*findings):
    return scanner_module.LLMReview(findings=list(findings))


def make_finding(**overrides):
    fields = {
        "file": "app.py",
        "line": 3,
        "severity": "high",
        "category": "secrets",
        "description": "Hardcoded API key",
        "evidence": "sk-****",
        "remediation": "Rotate the key",
    }
    fields.update(overrides)
    return scanner_module.LLMFinding(**fields)


FILES = [("app.py", "# app.py\napi_key = 'x'")]


@pytest.fixture(autouse=True)
def _fake_llm_client(monkeypatch):
    fake = FakeClient()
    monkeypatch.setattr(scanner_module, "_llm_client", fake)
    return fake


@pytest.fixture(autouse=True)
def _fake_api_key(monkeypatch):
    monkeypatch.setattr(scanner_module.settings, "OPENAI_API_KEY", "sk-test-key")


def test_valid_structured_response_returns_ok(monkeypatch):
    fake = FakeClient(
        response=make_response(
            parsed=make_llm_review(make_finding(description="Hardcoded API key"))
        )
    )
    monkeypatch.setattr(scanner_module, "_llm_client", fake)

    findings, status = scanner_module.llm_review(FILES)

    assert status == "ok"
    assert len(findings) == 1
    assert findings[0]["file"] == "app.py"
    assert findings[0]["severity"] == "high"
    assert findings[0]["category"] == "secrets"
    assert findings[0]["description"] == "Hardcoded API key"
    assert fake.completions.calls, "the fake client must have been called once"
    call = fake.completions.calls[0]
    assert call["model"] == scanner_module.settings.LLM_MODEL
    assert call["response_format"] is scanner_module.LLMReview
    assert call["messages"][0]["role"] == "system"
    assert call["messages"][1]["role"] == "user"


def test_refusal_returns_rules_only(monkeypatch):
    fake = FakeClient(response=make_response(refusal="I cannot review this code."))
    monkeypatch.setattr(scanner_module, "_llm_client", fake)

    findings, status = scanner_module.llm_review(FILES)

    assert findings == []
    assert status == "rules_only"
    assert len(fake.completions.calls) == 1


def test_missing_parsed_field_returns_rules_only(monkeypatch):
    fake = FakeClient(response=make_response(parsed=None))
    monkeypatch.setattr(scanner_module, "_llm_client", fake)

    findings, status = scanner_module.llm_review(FILES)

    assert findings == []
    assert status == "rules_only"


def test_client_exception_returns_rules_only(monkeypatch):
    fake = FakeClient(error=OpenAIError("connection refused"))
    monkeypatch.setattr(scanner_module, "_llm_client", fake)

    findings, status = scanner_module.llm_review(FILES)

    assert findings == []
    assert status == "rules_only"


def test_generic_exception_returns_rules_only(monkeypatch):
    fake = FakeClient(error=RuntimeError("boom"))
    monkeypatch.setattr(scanner_module, "_llm_client", fake)

    findings, status = scanner_module.llm_review(FILES)

    assert findings == []
    assert status == "rules_only"


def test_missing_api_key_returns_rules_only_without_request(monkeypatch):
    fake = FakeClient(
        response=make_response(parsed=make_llm_review(make_finding()))
    )
    monkeypatch.setattr(scanner_module, "_llm_client", fake)
    monkeypatch.setattr(scanner_module.settings, "OPENAI_API_KEY", "")

    findings, status = scanner_module.llm_review(FILES)

    assert findings == []
    assert status == "rules_only"
    assert fake.completions.calls == [], "no OpenAI request should be made"


def test_no_files_returns_rules_only_without_request(monkeypatch):
    fake = FakeClient(
        response=make_response(parsed=make_llm_review(make_finding()))
    )
    monkeypatch.setattr(scanner_module, "_llm_client", fake)

    findings, status = scanner_module.llm_review([])

    assert findings == []
    assert status == "rules_only"
    assert fake.completions.calls == []