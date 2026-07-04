import pytest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

import app_pages.history


def test_history_renders_without_exception():
    """Test that the history page renders without crashing."""
    with patch("api_client.list_campaigns", return_value=[]):
        at = AppTest.from_file("app_pages/history.py")
        at.run(timeout=10)
        assert not at.exception


def test_history_shows_empty_state():
    """Test that an empty message is shown when no campaigns exist."""
    with patch("api_client.list_campaigns", return_value=[]):
        at = AppTest.from_file("app_pages/history.py")
        at.run(timeout=10)
        assert not at.exception
        assert len(at.info) > 0


def test_history_shows_campaigns_when_available():
    """Test that campaigns are displayed when they exist."""
    mock_campaigns = [
        {
            "id": 1,
            "url": "https://example.com/article1",
            "status": "generated",
            "created_at": "2026-07-03T12:00:00",
            "lead_count": 5
        }
    ]

    with patch("api_client.list_campaigns", return_value=mock_campaigns):
        at = AppTest.from_file("app_pages/history.py")
        at.run(timeout=10)
        assert not at.exception
        # Should show campaigns in table or expanded view
        assert len(at.dataframe) > 0 or len(at.expander) > 0
