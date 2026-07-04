import pytest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

import app_pages.usage


def test_usage_renders_without_exception():
    """Test that the usage page renders without crashing."""
    with patch("api_client.health_keys", return_value={"openai": True, "apollo": True}):
        at = AppTest.from_file("app_pages/usage.py")
        at.run(timeout=10)
        assert not at.exception


def test_usage_shows_metrics():
    """Test that cost metrics are displayed."""
    with patch("api_client.health_keys", return_value={"openai": True, "apollo": True}):
        at = AppTest.from_file("app_pages/usage.py")
        at.run(timeout=10)
        assert not at.exception
        # Should show metrics for total cost, OpenAI, Apollo
        assert len(at.metric) > 0


def test_usage_shows_empty_state():
    """Test that an empty state is shown when no usage data."""
    with patch("api_client.health_keys", return_value={"openai": True, "apollo": True}):
        at = AppTest.from_file("app_pages/usage.py")
        at.run(timeout=10)
        assert not at.exception
        # Should show info or warning about no campaigns
        assert len(at.info) > 0 or len(at.warning) > 0
