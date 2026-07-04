import pytest
from unittest.mock import Mock, patch

import streamlit as st
from streamlit.testing.v1 import AppTest

import app_pages.review_queue


def test_review_queue_renders_without_exception():
    """Test that the review queue page renders without crashing when no campaigns exist."""
    with patch("api_client.list_campaigns", return_value=[]):
        at = AppTest.from_file("app_pages/review_queue.py")
        at.run(timeout=10)
        assert not at.exception


def test_review_queue_shows_empty_state():
    """Test that an empty message is shown when no candidates need review."""
    with patch("api_client.list_campaigns", return_value=[]):
        at = AppTest.from_file("app_pages/review_queue.py")
        at.run(timeout=10)
        assert not at.exception
        # Should show info message about no campaigns
        assert len(at.info) > 0


def test_review_queue_shows_candidates_when_available():
    """Test that candidates are displayed when they exist."""
    mock_campaigns = [
        {"id": 1, "url": "https://example.com/article1", "status": "generated"}
    ]
    mock_campaign_detail = {
        "campaign_id": 1,
        "candidates": [
            {
                "id": 1,
                "company_name": "Tech Corp",
                "domain": "techcorp.com",
                "bucket": "needs_review",
                "score": 65,
                "score_reason": "Good thematic alignment but needs human verification",
                "human_override": None
            }
        ]
    }

    with patch("api_client.list_campaigns", return_value=mock_campaigns), \
         patch("api_client.get_campaign", return_value=mock_campaign_detail):
        at = AppTest.from_file("app_pages/review_queue.py")
        at.run(timeout=10)
        assert not at.exception
        # Should show candidate cards via expanders
        assert len(at.expander) > 0