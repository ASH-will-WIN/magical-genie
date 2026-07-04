import pytest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

import app_pages.settings


def test_settings_renders_without_exception():
    """Test that the settings page renders without crashing."""
    with patch("api_client.health_keys", return_value={"openai": True, "apollo": True}):
        at = AppTest.from_file("app_pages/settings.py")
        at.run(timeout=10)
        assert not at.exception


def test_settings_shows_api_status():
    """Test that API connection status is displayed."""
    with patch("api_client.health_keys", return_value={"openai": True, "apollo": False}):
        at = AppTest.from_file("app_pages/settings.py")
        at.run(timeout=10)
        assert not at.exception
        # Should show status indicators
        assert len(at.metric) > 0 or len(at.info) > 0


def test_settings_has_threshold_controls():
    """Test that threshold settings are accessible."""
    with patch("api_client.health_keys", return_value={"openai": True, "apollo": True}):
        at = AppTest.from_file("app_pages/settings.py")
        at.run(timeout=10)
        assert not at.exception
        # Should have sliders or number inputs for thresholds
        assert len(at.slider) > 0 or len(at.number_input) > 0
