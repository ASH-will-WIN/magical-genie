"""
Environment variable management + product catalog loading.
"""
import json
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
APOLLO_API_KEY = os.getenv("APOLLO_API_KEY", "")
APOLLO_CREDITS_LIMIT = int(os.getenv("APOLLO_CREDITS_LIMIT", "4000"))
DATABASE_PATH = os.getenv("DATABASE_PATH", str(BASE_DIR / "campaigns.db"))
TRACKING_BASE_URL = os.getenv("TRACKING_BASE_URL", "https://track.example.com/r")

SETTINGS_PATH = BASE_DIR / "data" / "settings.json"

DEFAULT_SETTINGS = {
    "approve_threshold": 70,
    "review_threshold": 40,
    "max_lead_fetch_companies": None,
    "max_leads_per_campaign": None,
    "llm_pricing": {
        "gpt-4o-mini": {"input": 0.15, "output": 0.60},
        "gpt-4o": {"input": 5.00, "output": 15.00},
    },
    "apollo_credit_costs": {"email": 1, "phone": 8},
    "apollo_credit_cost_usd": 0.0206,
}


def load_settings() -> dict:
    """Runtime-editable settings (thresholds, testing caps, pricing).
    Falls back to DEFAULT_SETTINGS if the file doesn't exist yet (first run),
    and back-fills any keys missing from an older settings.json so adding a
    new setting never breaks existing installs."""
    if not SETTINGS_PATH.exists():
        return dict(DEFAULT_SETTINGS)
    with open(SETTINGS_PATH, "r") as f:
        saved = json.load(f)
    merged = dict(DEFAULT_SETTINGS)
    merged.update(saved)
    return merged


def save_settings(settings: dict) -> None:
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(SETTINGS_PATH, "w") as f:
        json.dump(settings, f, indent=2)


def get_approve_threshold() -> int:
    return load_settings()["approve_threshold"]


def get_review_threshold() -> int:
    return load_settings()["review_threshold"]


def set_approve_threshold(value: int) -> None:
    settings = load_settings()
    settings["approve_threshold"] = value
    save_settings(settings)


def set_review_threshold(value: int) -> None:
    settings = load_settings()
    settings["review_threshold"] = value
    save_settings(settings)


def get_max_lead_fetch_companies() -> int | None:
    return load_settings()["max_lead_fetch_companies"]


def get_max_leads_per_campaign() -> int | None:
    return load_settings()["max_leads_per_campaign"]


def get_llm_pricing() -> dict:
    return load_settings()["llm_pricing"]


def get_apollo_credit_costs() -> dict:
    return load_settings()["apollo_credit_costs"]


def get_apollo_credit_cost_usd() -> float:
    return load_settings()["apollo_credit_cost_usd"]

PRODUCT_CATALOG_PATH = BASE_DIR / "data" / "product_catalog.json"
ICP_CONFIG_PATH = BASE_DIR / "data" / "icp_config.json"

URGENCY_RUBRIC = """
9-10 = deadline within 3 months
7-8  = deadline within 6 months
5-6  = timeline within 12 months
3-4  = timeline vague or missing
1-2  = no deadline
""".strip()


def load_product_catalog() -> list[dict]:
    with open(PRODUCT_CATALOG_PATH, "r") as f:
        return json.load(f)


def product_ids() -> list[str]:
    return [p["product_id"] for p in load_product_catalog()]


def load_icp_config() -> dict:
    with open(ICP_CONFIG_PATH, "r") as f:
        return json.load(f)
