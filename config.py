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

# Optional lead-fetch testing caps for the Venn (multi-company) pipeline.
# None (unset) = unlimited, i.e. zero effect -- these exist purely to bound
# Apollo credit spend while testing against real campaigns, not a permanent
# product limit.
_max_lead_fetch_companies = os.getenv("MAX_LEAD_FETCH_COMPANIES")
MAX_LEAD_FETCH_COMPANIES = int(_max_lead_fetch_companies) if _max_lead_fetch_companies else None

_max_leads_per_campaign = os.getenv("MAX_LEADS_PER_CAMPAIGN")
MAX_LEADS_PER_CAMPAIGN = int(_max_leads_per_campaign) if _max_leads_per_campaign else None

PRODUCT_CATALOG_PATH = BASE_DIR / "data" / "product_catalog.json"
ICP_CONFIG_PATH = BASE_DIR / "data" / "icp_config.json"

# Phase 7: LLM pricing, per 1M tokens (input, output)
LLM_PRICING = {
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4o": {"input": 5.00, "output": 15.00},
}

# Apollo enrichment credit costs (only relevant if enrichment endpoints are used)
APOLLO_CREDIT_COSTS = {
    "email": 1,
    "phone": 8,
}

# Apollo credit cost in USD (derived from plan: $99/mo for 4,800 credits ≈ $0.0206/credit)
APOLLO_CREDIT_COST_USD = 0.0206

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
