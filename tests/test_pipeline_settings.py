import pytest

import config
from services.icp_matching.pipeline import _bucket, _lead_fetch_cap_reason


@pytest.fixture
def isolated_settings(tmp_path, monkeypatch):
    path = tmp_path / "settings.json"
    monkeypatch.setattr(config, "SETTINGS_PATH", path)
    return path


def test_bucket_uses_default_thresholds(isolated_settings):
    assert _bucket(75, exclude=False) == "approved"
    assert _bucket(50, exclude=False) == "needs_review"
    assert _bucket(10, exclude=False) == "rejected"
    assert _bucket(99, exclude=True) == "rejected"


def test_bucket_respects_custom_threshold_from_settings(isolated_settings):
    settings = config.load_settings()
    settings["approve_threshold"] = 90
    config.save_settings(settings)

    # 75 would have been "approved" under the default 70 cutoff -- now needs_review
    assert _bucket(75, exclude=False) == "needs_review"


def test_lead_fetch_cap_reason_none_when_uncapped(isolated_settings, monkeypatch):
    monkeypatch.setattr(
        "services.icp_matching.pipeline._campaign_lead_fetch_counts",
        lambda campaign_id: (0, 0),
    )
    assert _lead_fetch_cap_reason(campaign_id=1) is None


def test_lead_fetch_cap_reason_fires_from_settings(isolated_settings, monkeypatch):
    settings = config.load_settings()
    settings["max_lead_fetch_companies"] = 2
    config.save_settings(settings)
    monkeypatch.setattr(
        "services.icp_matching.pipeline._campaign_lead_fetch_counts",
        lambda campaign_id: (2, 5),
    )
    reason = _lead_fetch_cap_reason(campaign_id=1)
    assert reason is not None
    assert "max_lead_fetch_companies" in reason.lower() or "2" in reason
