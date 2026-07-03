import tempfile
import json
import os
from pathlib import Path
from unittest.mock import patch

import config
from database import get_conn, init_db, now_iso
from services.usage_dashboard import get_total_cost
from services.usage_tracker import log_llm_usage, log_apollo_usage


def test_total_cost_uses_custom_pricing_from_settings():
    """Test that get_total_cost reads LLM pricing from settings store."""
    # Create a temporary settings file with custom pricing
    with tempfile.TemporaryDirectory() as tmpdir:
        settings_path = Path(tmpdir) / "settings.json"
        custom_settings = {
            "llm_pricing": {
                "gpt-4o-mini": {"input": 1.0, "output": 1.0}  # Custom pricing
            },
            "apollo_credit_costs": {"email": 1, "phone": 8},  # Keep defaults for Apollo
            "apollo_credit_cost_usd": 0.0206  # Keep default
        }

        with open(settings_path, "w") as f:
            json.dump(custom_settings, f)

        # Mock the settings path to point to our temporary file
        with patch('config.SETTINGS_PATH', settings_path):
            # Initialize a test database in the temp directory
            db_path = Path(tmpdir) / "test_campaigns.db"
            with patch('config.DATABASE_PATH', str(db_path)):
                init_db()  # Initialize the database

                # Clear any existing data to ensure clean state
                with get_conn() as conn:
                    conn.execute("DELETE FROM campaigns")
                    conn.execute("DELETE FROM usage_log")
                    conn.execute("DELETE FROM leads")
                    conn.commit()

                    # Log some usage
                    conn.execute(
                        "INSERT INTO campaigns (url, created_at) VALUES (?, ?)",
                        ("https://example.com/article", now_iso())
                    )
                    campaign_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

                # Log LLM usage: 1M input tokens, 0 output tokens for gpt-4o-mini
                # With custom pricing: (1M/1M)*1.0 + 0 = 1.0 USD
                log_llm_usage(campaign_id, "gpt-4o-mini", "context_extraction", 1000000, 0)

                # Test get_total_cost uses custom pricing from settings
                cost = get_total_cost(campaign_id=campaign_id)
                assert cost["openai_usd"] == 1.0  # Should use custom pricing, not hardcoded


def test_apollo_usage_uses_custom_credit_costs_from_settings():
    """Test that log_apollo_usage reads Apollo credit costs from settings store."""
    # Create a temporary settings file with custom pricing
    with tempfile.TemporaryDirectory() as tmpdir:
        settings_path = Path(tmpdir) / "settings.json"
        custom_settings = {
            "llm_pricing": {
                "gpt-4o-mini": {"input": 0.15, "output": 0.60}  # Keep defaults for LLM
            },
            "apollo_credit_costs": {"email": 3, "phone": 8},  # Custom pricing: email=3 credits
            "apollo_credit_cost_usd": 0.0206  # Keep default
        }

        with open(settings_path, "w") as f:
            json.dump(custom_settings, f)

        # Mock the settings path to point to our temporary file
        with patch('config.SETTINGS_PATH', settings_path):
            # Initialize a test database in the temp directory
            db_path = Path(tmpdir) / "test_campaigns.db"
            with patch('config.DATABASE_PATH', str(db_path)):
                init_db()  # Initialize the database

                # Clear any existing data to ensure clean state
                with get_conn() as conn:
                    conn.execute("DELETE FROM campaigns")
                    conn.execute("DELETE FROM usage_log")
                    conn.execute("DELETE FROM leads")
                    conn.commit()

                    # Log some usage
                    conn.execute(
                        "INSERT INTO campaigns (url, created_at) VALUES (?, ?)",
                        ("https://example.com/article", now_iso())
                    )
                    campaign_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

                # Log Apollo usage: 2 emails, 0 phones
                # With custom pricing: 2 * 3 + 0 * 8 = 6 credits
                log_apollo_usage(campaign_id=1, operation="lead_search", emails=2, phones=0)

                # Check that Apollo usage was logged correctly using custom pricing
                with get_conn() as conn:
                    row = conn.execute(
                        "SELECT credits_used FROM usage_log WHERE service = 'apollo'"
                    ).fetchone()
                assert row["credits_used"] == 6  # Should use custom pricing, not hardcoded