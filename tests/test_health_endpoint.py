from fastapi.testclient import TestClient

import config
import main


def test_health_keys_reports_present_when_both_set(monkeypatch):
    monkeypatch.setattr(config, "OPENAI_API_KEY", "sk-fake")
    monkeypatch.setattr(config, "APOLLO_API_KEY", "apollo-fake")
    monkeypatch.setattr(main, "OPENAI_API_KEY", "sk-fake", raising=False)
    monkeypatch.setattr(main, "APOLLO_API_KEY", "apollo-fake", raising=False)

    client = TestClient(main.app)
    resp = client.get("/health/keys")
    assert resp.status_code == 200
    assert resp.json() == {"openai": True, "apollo": True}


def test_health_keys_reports_missing_when_unset(monkeypatch):
    monkeypatch.setattr(config, "OPENAI_API_KEY", "")
    monkeypatch.setattr(config, "APOLLO_API_KEY", "")
    monkeypatch.setattr(main, "OPENAI_API_KEY", "", raising=False)
    monkeypatch.setattr(main, "APOLLO_API_KEY", "", raising=False)

    client = TestClient(main.app)
    resp = client.get("/health/keys")
    assert resp.status_code == 200
    assert resp.json() == {"openai": False, "apollo": False}


def test_health_keys_never_returns_key_value(monkeypatch):
    monkeypatch.setattr(main, "OPENAI_API_KEY", "sk-super-secret", raising=False)
    monkeypatch.setattr(main, "APOLLO_API_KEY", "apollo-super-secret", raising=False)

    client = TestClient(main.app)
    resp = client.get("/health/keys")
    body = resp.text
    assert "sk-super-secret" not in body
    assert "apollo-super-secret" not in body