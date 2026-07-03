import json

import pytest

import config


@pytest.fixture
def isolated_settings(tmp_path, monkeypatch):
    path = tmp_path / "settings.json"
    monkeypatch.setattr(config, "SETTINGS_PATH", path)
    return path


def test_load_settings_returns_defaults_when_file_missing(isolated_settings):
    settings = config.load_settings()
    assert settings == config.DEFAULT_SETTINGS


def test_save_then_load_round_trips(isolated_settings):
    settings = config.load_settings()
    settings["approve_threshold"] = 80
    config.save_settings(settings)

    reloaded = config.load_settings()
    assert reloaded["approve_threshold"] == 80
    assert json.loads(isolated_settings.read_text())["approve_threshold"] == 80


def test_get_approve_threshold_reflects_saved_value(isolated_settings):
    settings = config.load_settings()
    settings["approve_threshold"] = 55
    config.save_settings(settings)
    assert config.get_approve_threshold() == 55


def test_get_review_threshold_default(isolated_settings):
    assert config.get_review_threshold() == 40


def test_get_max_lead_fetch_companies_default_is_none(isolated_settings):
    assert config.get_max_lead_fetch_companies() is None


def test_get_max_lead_fetch_companies_reflects_saved_value(isolated_settings):
    settings = config.load_settings()
    settings["max_lead_fetch_companies"] = 5
    config.save_settings(settings)
    assert config.get_max_lead_fetch_companies() == 5


def test_get_llm_pricing_default_has_known_models(isolated_settings):
    pricing = config.get_llm_pricing()
    assert pricing["gpt-4o-mini"] == {"input": 0.15, "output": 0.60}


def test_get_apollo_credit_cost_usd_default(isolated_settings):
    assert config.get_apollo_credit_cost_usd() == 0.0206


def test_load_settings_merges_missing_keys_from_defaults(isolated_settings):
    # A settings.json saved before a new setting key was introduced should
    # not crash getters for the new key -- missing keys fall back to defaults.
    isolated_settings.write_text(json.dumps({"approve_threshold": 90}))
    settings = config.load_settings()
    assert settings["approve_threshold"] == 90
    assert settings["review_threshold"] == config.DEFAULT_SETTINGS["review_threshold"]
