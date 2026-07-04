import pytest
from unittest.mock import Mock, patch

import streamlit as st
from streamlit.testing.v1 import AppTest

import app_pages.new_campaign


def test_new_campaign_renders_without_exception():
    at = AppTest.from_file("app_pages/new_campaign.py")
    at.run(timeout=10)
    assert not at.exception


def test_new_campaign_handles_backend_error_during_run():
    with patch("api_client.run_campaign",
               side_effect=Exception("Backend error")):
        at = AppTest.from_file("app_pages/new_campaign.py")
        at.run(timeout=10)
        # Debug: print number of buttons
        print(f"[DEBUG] Number of buttons: {len(at.button)}")
        if len(at.button) == 0:
            # If no buttons, we fail the test with a message
            assert False, "No button found in the app. Check the layout."

        # FIRST: Set the URL in the text input
        # Find the text input and set its value
        if len(at.text_input) > 0:
            at.text_input[0].set_value("https://example.com/article")
            at.run(timeout=10)  # Run again to update the value

        # THEN: Click the run button
        at.button[0].click()
        at.run(timeout=10)
        assert not at.exception
        # Should show error message
        assert len(at.error) > 0


def test_new_campaign_shows_manual_paste_option_when_paywalled():
    mock_response = {
        "status": "paywalled",
        "context": None
    }
    with patch("api_client.run_campaign",
               return_value=mock_response):
        at = AppTest.from_file("app_pages/new_campaign.py")
        at.run(timeout=10)
        # Debug: print number of buttons
        print(f"[DEBUG] Number of buttons: {len(at.button)}")
        if len(at.button) == 0:
            # If no buttons, we fail the test with a message
            assert False, "No button found in the app. Check the layout."

        # FIRST: Set the URL in the text input
        # Find the text input and set its value
        if len(at.text_input) > 0:
            at.text_input[0].set_value("https://example.com/paywalled-article")
            at.run(timeout=10)  # Run again to update the value

        # THEN: Click the run button
        at.button[0].click()
        at.run(timeout=10)
        assert not at.exception
        # Should show text area for manual paste
        assert len(at.text_area) > 0