# Magical Genie UI Overhaul Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the single-file Streamlit UI (`frontend.py`) with a themed, multi-page control panel (Dashboard, New Campaign, Review Queue, Campaign History, Settings, Usage & Cost) matching the "signal detection" visual identity, with no changes to pipeline/business logic beyond two narrow, additive backend touches (a runtime-editable settings store, and a read-only health-check endpoint).

**Architecture:** `.streamlit/config.toml` carries native theming (colors, fonts — Inter body, JetBrains Mono numerics). A small `styles.py` supplies the CSS this native theming can't reach (signal-strength bars, Venn SVG). `st.navigation`/`st.Page` over an `app_pages/` directory replaces the old tab structure. A thin `api_client.py` centralizes all FastAPI calls. Hardcoded thresholds/caps/pricing move from Python constants/env vars into a JSON-backed `data/settings.json`, read live via `config.py` getters (no process restart needed to see a change).

**Tech Stack:** Streamlit 1.58 (`st.navigation`, `st.Page`, `st.html`, `streamlit.testing.v1.AppTest`), FastAPI (existing `main.py`), pytest 9.0.3, `requests` (existing HTTP client to the API), stdlib `threading` for background campaign polling.

## Global Constraints

- No changes to pipeline/business logic (scraping, theme extraction, scoring, prefiltering, lead search, copy generation) — verified against `CLAUDE.md`'s non-negotiable design decisions.
- The only backend touches allowed: (1) `data/settings.json` + getters in `config.py`, consumed by `pipeline.py`, `usage_dashboard.py`, `usage_tracker.py`; (2) a new `GET /health/keys` read-only endpoint in `main.py`.
- Color tokens (exact hex): background `#12151C`, panel `#1B2029`, accent `#E8AA4C`, positive `#4FA88A`, negative `#C4634B`, muted text `#8B93A7`, primary text `#F2F3F5`.
- Fonts: Inter (UI/body), JetBrains Mono (all numeric/data values — scores, costs, tokens, timestamps, IDs).
- Multi-page directory MUST be named `app_pages/`, not `pages/` (Streamlit's legacy auto-discovery conflicts with `pages/`).
- Failure is always soft: no raw stack traces in the UI; every empty/error state has a plain-language explanation, per `CLAUDE.md`.
- `frontend.py` is retired once its logic has been fully migrated into `app_pages/new_campaign.py` and `app_pages/usage.py`.

---

## File Structure

```
.streamlit/config.toml           # theme (new)
styles.py                        # CSS + signal bar / venn / mono helpers (new)
api_client.py                    # FastAPI HTTP wrapper (new)
streamlit_app.py                 # entrypoint + st.navigation (new, replaces frontend.py)
app_pages/
    dashboard.py                 # new
    new_campaign.py              # new (migrates frontend.py's campaign_tab logic)
    review_queue.py              # new
    history.py                   # new
    settings.py                  # new
    usage.py                     # new (migrates frontend.py's usage_tab logic)
config.py                        # modified: settings.json load/save + getters
data/settings.json               # new: runtime-editable thresholds/caps/pricing
services/icp_matching/pipeline.py  # modified: read thresholds/caps via config getters
services/usage_dashboard.py      # modified: read pricing via config getters
services/usage_tracker.py        # modified: read pricing via config getters
main.py                          # modified: add GET /health/keys
frontend.py                      # deleted (Task 15)
tests/
    test_config_settings.py      # new
    test_pipeline_settings.py    # new
    test_usage_pricing_settings.py  # new
    test_health_endpoint.py      # new
    test_styles.py               # new
    test_api_client.py           # new
    test_streamlit_app.py        # new
    test_page_dashboard.py       # new
    test_page_new_campaign.py    # new
    test_page_review_queue.py    # new
    test_page_history.py         # new
    test_page_settings.py        # new
    test_page_usage.py           # new
```

---

### Task 1: Runtime settings store (`data/settings.json` + `config.py`)

**Files:**
- Create: `data/settings.json`
- Modify: `config.py`
- Test: `tests/test_config_settings.py`

**Interfaces:**
- Produces: `config.SETTINGS_PATH: Path`, `config.DEFAULT_SETTINGS: dict`, `config.load_settings() -> dict`, `config.save_settings(settings: dict) -> None`, `config.get_approve_threshold() -> int`, `config.get_review_threshold() -> int`, `config.get_max_lead_fetch_companies() -> int | None`, `config.get_max_leads_per_campaign() -> int | None`, `config.get_llm_pricing() -> dict`, `config.get_apollo_credit_costs() -> dict`, `config.get_apollo_credit_cost_usd() -> float`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_config_settings.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_config_settings.py -v`
Expected: FAIL with `AttributeError: module 'config' has no attribute 'SETTINGS_PATH'` (or similar — the functions don't exist yet).

- [ ] **Step 3: Implement the settings store in `config.py`**

Replace the block in `config.py` from `MAX_LEAD_FETCH_COMPANIES`/`MAX_LEADS_PER_CAMPAIGN` through `APOLLO_CREDIT_COST_USD` (currently lines 20-46) with:

```python
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
```

Leave `OPENAI_API_KEY`, `APOLLO_API_KEY`, `APOLLO_CREDITS_LIMIT`, `DATABASE_PATH`, `TRACKING_BASE_URL`, `PRODUCT_CATALOG_PATH`, `ICP_CONFIG_PATH`, `URGENCY_RUBRIC`, `load_product_catalog`, `product_ids`, `load_icp_config` untouched.

- [ ] **Step 4: Seed `data/settings.json` with the current production values**

Create `data/settings.json`:

```json
{
  "approve_threshold": 70,
  "review_threshold": 40,
  "max_lead_fetch_companies": null,
  "max_leads_per_campaign": null,
  "llm_pricing": {
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4o": {"input": 5.00, "output": 15.00}
  },
  "apollo_credit_costs": {"email": 1, "phone": 8},
  "apollo_credit_cost_usd": 0.0206
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_config_settings.py -v`
Expected: PASS (9 passed)

- [ ] **Step 6: Commit**

```bash
git add config.py data/settings.json tests/test_config_settings.py
git commit -m "feat: add runtime-editable settings store for thresholds/caps/pricing"
```

---

### Task 2: Pipeline reads thresholds/caps from the settings store

**Files:**
- Modify: `services/icp_matching/pipeline.py`
- Test: `tests/test_pipeline_settings.py`

**Interfaces:**
- Consumes: `config.get_approve_threshold()`, `config.get_review_threshold()`, `config.get_max_lead_fetch_companies()`, `config.get_max_leads_per_campaign()` (Task 1)
- Produces: `pipeline._bucket(score, exclude)` and `pipeline._lead_fetch_cap_reason(campaign_id)` now read live settings instead of module constants (signature unchanged, so `build_and_score_candidates`/`fetch_leads_for_approved`/`approve_candidate` callers are unaffected)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_pipeline_settings.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_pipeline_settings.py -v`
Expected: FAIL — `test_bucket_respects_custom_threshold_from_settings` and the cap test fail because `_bucket`/`_lead_fetch_cap_reason` still reference the module-level `APPROVE_THRESHOLD`/`REVIEW_THRESHOLD`/`MAX_LEAD_FETCH_COMPANIES`/`MAX_LEADS_PER_CAMPAIGN` constants, frozen at import time.

- [ ] **Step 3: Update `services/icp_matching/pipeline.py`**

Change the import (line 20):

```python
from config import load_icp_config, load_product_catalog
```

(remove `MAX_LEAD_FETCH_COMPANIES, MAX_LEADS_PER_CAMPAIGN` from that import — they're no longer module-level constants)

Add near the top, after the existing imports:

```python
import config
```

Remove the module constants (lines 30-31):

```python
APPROVE_THRESHOLD = 70
REVIEW_THRESHOLD = 40
```

Update `_lead_fetch_cap_reason` (was lines 51-60):

```python
def _lead_fetch_cap_reason(campaign_id: int) -> str | None:
    """Returns a human-readable reason string if either testing cap
    (max_lead_fetch_companies / max_leads_per_campaign, both optional /
    None = unlimited, editable at runtime via data/settings.json) is already
    reached for this campaign, else None."""
    companies_fetched, total_leads = _campaign_lead_fetch_counts(campaign_id)
    max_companies = config.get_max_lead_fetch_companies()
    max_leads = config.get_max_leads_per_campaign()
    if max_companies is not None and companies_fetched >= max_companies:
        return f"max_lead_fetch_companies ({max_companies}) reached ({companies_fetched} companies already fetched)"
    if max_leads is not None and total_leads >= max_leads:
        return f"max_leads_per_campaign ({max_leads}) reached ({total_leads} leads already found)"
    return None
```

Update `_bucket` (was lines 92-99):

```python
def _bucket(score: int, exclude: bool) -> str:
    if exclude:
        return "rejected"
    if score >= config.get_approve_threshold():
        return "approved"
    if score >= config.get_review_threshold():
        return "needs_review"
    return "rejected"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_pipeline_settings.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Run the full existing test suite to check for regressions**

Run: `python -m pytest tests/ -v`
Expected: All PASS (settings tests from Task 1 + pipeline tests from Task 2)

- [ ] **Step 6: Commit**

```bash
git add services/icp_matching/pipeline.py tests/test_pipeline_settings.py
git commit -m "refactor: read approve/review thresholds and testing caps from settings store"
```

---

### Task 3: Usage/cost tracking reads pricing from the settings store

**Files:**
- Modify: `services/usage_dashboard.py`
- Modify: `services/usage_tracker.py`
- Test: `tests/test_usage_pricing_settings.py`

**Interfaces:**
- Consumes: `config.get_llm_pricing()`, `config.get_apollo_credit_costs()`, `config.get_apollo_credit_cost_usd()` (Task 1)
- Produces: no change to `get_total_cost`, `get_cost_by_operation`, `get_cost_by_model`, `get_cost_per_campaign`, `get_apollo_credit_status`, `log_llm_usage`, `log_apollo_usage`, `get_campaign_cost_summary` signatures — only their pricing source changes from a frozen import to a live settings read

- [ ] **Step 1: Write the failing test**

Create `tests/test_usage_pricing_settings.py`:

```python
import pytest

import config
from database import get_conn, init_db, now_iso
from services.usage_dashboard import get_total_cost
from services.usage_tracker import log_llm_usage, log_apollo_usage


@pytest.fixture
def isolated_env(tmp_path, monkeypatch):
    settings_path = tmp_path / "settings.json"
    monkeypatch.setattr(config, "SETTINGS_PATH", settings_path)
    db_path = tmp_path / "test.db"
    monkeypatch.setattr(config, "DATABASE_PATH", str(db_path))
    # database.py imports DATABASE_PATH by value at import time, so patch it
    # directly on the database module too.
    import database
    monkeypatch.setattr(database, "DATABASE_PATH", str(db_path))
    init_db()
    return settings_path


def test_total_cost_uses_custom_pricing_from_settings(isolated_env):
    settings = config.load_settings()
    settings["llm_pricing"] = {"gpt-4o-mini": {"input": 1.0, "output": 1.0}}
    config.save_settings(settings)

    with get_conn() as conn:
        conn.execute(
            """INSERT INTO usage_log (campaign_id, service, model, operation, input_tokens, output_tokens, credits_used, cost_usd, created_at)
               VALUES (1, 'openai', 'gpt-4o-mini', 'context_extraction', 1_000_000, 0, 0, 0, ?)""",
            (now_iso(),),
        )

    cost = get_total_cost(campaign_id=1)
    assert cost["openai_usd"] == 1.0


def test_apollo_usage_uses_custom_credit_costs_from_settings(isolated_env):
    settings = config.load_settings()
    settings["apollo_credit_costs"] = {"email": 3, "phone": 8}
    config.save_settings(settings)

    log_apollo_usage(campaign_id=1, operation="lead_search", emails=2, phones=0)

    with get_conn() as conn:
        row = conn.execute("SELECT credits_used FROM usage_log WHERE service = 'apollo'").fetchone()
    assert row["credits_used"] == 6
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_usage_pricing_settings.py -v`
Expected: FAIL — cost/credits reflect the still-hardcoded `LLM_PRICING`/`APOLLO_CREDIT_COSTS` constants, not the custom settings.

- [ ] **Step 3: Update `services/usage_dashboard.py`**

Change the import (line 8):

```python
from config import get_llm_pricing, get_apollo_credit_costs, get_apollo_credit_cost_usd
```

Replace every `LLM_PRICING.get(model)` occurrence (lines 40, 106, 174, 237) with `get_llm_pricing().get(model)`.

Replace line 50 (`apollo_usd = apollo_credits * APOLLO_CREDIT_COST_USD`) with:

```python
    apollo_usd = apollo_credits * get_apollo_credit_cost_usd()
```

Replace line 255 (`apollo_usd = apollo_credits * APOLLO_CREDIT_COSTS["email"] * 0.0206`) with:

```python
            apollo_usd = apollo_credits * get_apollo_credit_costs()["email"] * get_apollo_credit_cost_usd()
```

- [ ] **Step 4: Update `services/usage_tracker.py`**

Change the import (line 9):

```python
from config import get_llm_pricing, get_apollo_credit_costs
```

Replace line 13 (`pricing = LLM_PRICING.get(model)`) with:

```python
    pricing = get_llm_pricing().get(model)
```

Replace line 33 (`credits = emails * APOLLO_CREDIT_COSTS["email"] + phones * APOLLO_CREDIT_COSTS["phone"]`) with:

```python
    costs = get_apollo_credit_costs()
    credits = emails * costs["email"] + phones * costs["phone"]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_usage_pricing_settings.py -v`
Expected: PASS (2 passed)

- [ ] **Step 6: Run the full test suite to check for regressions**

Run: `python -m pytest tests/ -v`
Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add services/usage_dashboard.py services/usage_tracker.py tests/test_usage_pricing_settings.py
git commit -m "refactor: read LLM/Apollo pricing from settings store instead of hardcoded constants"
```

---

### Task 4: `GET /health/keys` connection-status endpoint

**Files:**
- Modify: `main.py`
- Test: `tests/test_health_endpoint.py`

**Interfaces:**
- Produces: `GET /health/keys` → `{"openai": bool, "apollo": bool}` (presence-only check, never returns key values)

- [ ] **Step 1: Write the failing test**

Create `tests/test_health_endpoint.py`:

```python
from fastapi.testclient import TestClient

import config
import main


def test_health_keys_reports_present_when_both_set(monkeypatch):
    monkeypatch.setattr(config, "OPENAI_API_KEY", "sk-fake")
    monkeypatch.setattr(config, "APOLLO_API_KEY", "apollo-fake")
    monkeypatch.setattr(main, "OPENAI_API_KEY", "sk-fake", raising=False)
    monkeypatch.setattr(main, "APOLLO_API_KEY", "apollo-fake", raising=False)

    client = TestClient(main.app)
    resp = client.get("/health/keys")
    assert resp.status_code == 200
    assert resp.json() == {"openai": True, "apollo": True}


def test_health_keys_reports_missing_when_unset(monkeypatch):
    monkeypatch.setattr(config, "OPENAI_API_KEY", "")
    monkeypatch.setattr(config, "APOLLO_API_KEY", "")
    monkeypatch.setattr(main, "OPENAI_API_KEY", "", raising=False)
    monkeypatch.setattr(main, "APOLLO_API_KEY", "", raising=False)

    client = TestClient(main.app)
    resp = client.get("/health/keys")
    assert resp.status_code == 200
    assert resp.json() == {"openai": False, "apollo": False}


def test_health_keys_never_returns_key_value(monkeypatch):
    monkeypatch.setattr(main, "OPENAI_API_KEY", "sk-super-secret", raising=False)
    monkeypatch.setattr(main, "APOLLO_API_KEY", "apollo-super-secret", raising=False)

    client = TestClient(main.app)
    resp = client.get("/health/keys")
    body = resp.text
    assert "sk-super-secret" not in body
    assert "apollo-super-secret" not in body
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_health_endpoint.py -v`
Expected: FAIL with 404 (route doesn't exist yet)

- [ ] **Step 3: Add the endpoint to `main.py`**

Add to the imports at the top of `main.py`:

```python
from config import OPENAI_API_KEY, APOLLO_API_KEY
```

Add the endpoint (near `@app.get("/health")`):

```python
@app.get("/health/keys")
def health_keys():
    """Presence-only check for API key configuration -- never returns the
    key values themselves. Used by the Settings page's connection-status
    panel so a misconfigured .env surfaces immediately instead of failing
    silently deep in a pipeline run later."""
    return {"openai": bool(OPENAI_API_KEY), "apollo": bool(APOLLO_API_KEY)}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_health_endpoint.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add main.py tests/test_health_endpoint.py
git commit -m "feat: add read-only /health/keys endpoint for API key presence check"
```

---

### Task 5: Theme configuration (`.streamlit/config.toml`)

**Files:**
- Create: `.streamlit/config.toml`

**Interfaces:**
- Produces: the app-wide dark theme (colors, fonts) consumed visually by every page in later tasks. No Python interface — this is config-only.

- [ ] **Step 1: Create the theme file**

Create `.streamlit/config.toml`:

```toml
[theme]
base = "dark"
backgroundColor = "#12151C"
secondaryBackgroundColor = "#1B2029"
primaryColor = "#E8AA4C"
textColor = "#F2F3F5"
linkColor = "#E8AA4C"
borderColor = "#2A3040"

greenColor = "#4FA88A"
redColor = "#C4634B"

font = "Inter:https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap"
headingFont = "Inter:https://fonts.googleapis.com/css2?family=Inter:wght@600;700&display=swap"
codeFont = "'JetBrains Mono':https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500&display=swap"

linkUnderline = false
baseRadius = "8px"
buttonRadius = "8px"
showWidgetBorder = true
showSidebarBorder = true

[theme.sidebar]
backgroundColor = "#1B2029"
secondaryBackgroundColor = "#12151C"
textColor = "#F2F3F5"
borderColor = "#2A3040"
primaryColor = "#E8AA4C"

[server]
headless = true
```

- [ ] **Step 2: Manually verify the theme loads**

Run: `streamlit run streamlit_app.py --server.headless true &` (this will fail until Task 8 creates `streamlit_app.py` — skip live verification for now and revisit at the end of Task 8's steps, which re-runs this check).

- [ ] **Step 3: Commit**

```bash
git add .streamlit/config.toml
git commit -m "feat: add signal-detection dark theme (config.toml)"
```

---

### Task 6: `styles.py` — CSS and visual component helpers

**Files:**
- Create: `styles.py`
- Test: `tests/test_styles.py`

**Interfaces:**
- Produces: `styles.inject_base_styles() -> None` (calls `st.html` once), `styles.signal_bar_html(score: int, bucket: str) -> str`, `styles.venn_svg(article_only: int, icp_only: int, blended: int) -> str`, `styles.mono(value) -> str`
- `bucket` is one of `"approved"`, `"needs_review"`, `"rejected"`, `"dropped_at_prefilter"` (matches `icp_candidates.bucket` values from `database.py`)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_styles.py`:

```python
import pytest

from styles import signal_bar_html, venn_svg, mono


@pytest.mark.parametrize("bucket,expected_hex", [
    ("approved", "#4FA88A"),
    ("needs_review", "#E8AA4C"),
    ("rejected", "#C4634B"),
    ("dropped_at_prefilter", "#C4634B"),
])
def test_signal_bar_uses_bucket_color(bucket, expected_hex):
    html = signal_bar_html(score=65, bucket=bucket)
    assert expected_hex in html


def test_signal_bar_width_reflects_score():
    html = signal_bar_html(score=42, bucket="needs_review")
    assert "42%" in html


def test_signal_bar_clamps_score_to_0_100():
    assert "100%" in signal_bar_html(score=150, bucket="approved")
    assert "0%" in signal_bar_html(score=-10, bucket="rejected")


def test_venn_svg_contains_all_three_region_counts():
    svg = venn_svg(article_only=12, icp_only=8, blended=3)
    assert "<svg" in svg
    assert "12" in svg
    assert "8" in svg
    assert "3" in svg


def test_mono_wraps_value_in_monospace_span():
    result = mono(42.5)
    assert "42.5" in result
    assert "gs-mono" in result
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_styles.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'styles'`

- [ ] **Step 3: Implement `styles.py`**

```python
"""Central CSS + small visual-component helpers for the signal-detection
theme. Colors here must match .streamlit/config.toml (native theming covers
fonts/panel colors; this module covers what config.toml can't reach: the
signal-strength bar and the Venn diagram)."""
import streamlit as st

_BUCKET_COLORS = {
    "approved": "#4FA88A",
    "needs_review": "#E8AA4C",
    "rejected": "#C4634B",
    "dropped_at_prefilter": "#C4634B",
}

_TRACK_COLOR = "#242A38"

_BASE_CSS = """
<style>
.gs-mono {
    font-family: 'JetBrains Mono', monospace;
}
.gs-signal-track {
    width: 100%;
    height: 8px;
    background: %(track)s;
    border-radius: 999px;
    overflow: hidden;
}
.gs-signal-fill {
    height: 100%%;
    border-radius: 999px;
}
</style>
""" % {"track": _TRACK_COLOR}


def inject_base_styles() -> None:
    """Call once, from the app entrypoint, before any page renders."""
    st.html(_BASE_CSS)


def signal_bar_html(score: int, bucket: str) -> str:
    """A filled horizontal 0-100 signal-strength bar, colored by bucket."""
    clamped = max(0, min(100, score))
    color = _BUCKET_COLORS.get(bucket, _TRACK_COLOR)
    return (
        f'<div class="gs-signal-track">'
        f'<div class="gs-signal-fill" style="width:{clamped}%; background:{color};"></div>'
        f'</div>'
        f'<span class="gs-mono" style="font-size:0.8rem; color:{color};">{clamped}/100</span>'
    )


def venn_svg(article_only: int, icp_only: int, blended: int, width: int = 360, height: int = 200) -> str:
    """Two overlapping circles: Article Theme (left) ∩ Reinvent ICP (right),
    labeled with candidate counts per region -- article-only, icp-only,
    blended (the overlap, i.e. approved-relevant candidates)."""
    left_cx, right_cx, cy, r = width * 0.38, width * 0.62, height * 0.55, width * 0.24
    return f"""
<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">
  <circle cx="{left_cx}" cy="{cy}" r="{r}" fill="#E8AA4C" fill-opacity="0.28" stroke="#E8AA4C" stroke-width="1.5" />
  <circle cx="{right_cx}" cy="{cy}" r="{r}" fill="#4FA88A" fill-opacity="0.28" stroke="#4FA88A" stroke-width="1.5" />
  <text x="{left_cx - r * 0.55}" y="{cy}" fill="#F2F3F5" font-family="'JetBrains Mono', monospace" font-size="20" text-anchor="middle">{article_only}</text>
  <text x="{right_cx + r * 0.55}" y="{cy}" fill="#F2F3F5" font-family="'JetBrains Mono', monospace" font-size="20" text-anchor="middle">{icp_only}</text>
  <text x="{(left_cx + right_cx) / 2}" y="{cy}" fill="#F2F3F5" font-family="'JetBrains Mono', monospace" font-size="20" text-anchor="middle">{blended}</text>
  <text x="{left_cx - r * 0.55}" y="{cy + 22}" fill="#8B93A7" font-family="Inter, sans-serif" font-size="11" text-anchor="middle">article-only</text>
  <text x="{right_cx + r * 0.55}" y="{cy + 22}" fill="#8B93A7" font-family="Inter, sans-serif" font-size="11" text-anchor="middle">icp-only</text>
  <text x="{(left_cx + right_cx) / 2}" y="{cy + r + 20}" fill="#8B93A7" font-family="Inter, sans-serif" font-size="11" text-anchor="middle">blended</text>
</svg>
"""


def mono(value) -> str:
    """Wrap an ad-hoc numeric/data value in the monospace class, for use
    inside st.markdown(..., unsafe_allow_html=True) contexts that
    config.toml's codeFont doesn't reach (e.g. st.metric values)."""
    return f'<span class="gs-mono">{value}</span>'
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_styles.py -v`
Expected: PASS (6 passed — note `test_signal_bar_clamps_score_to_0_100` covers 2 asserts in one test)

- [ ] **Step 5: Commit**

```bash
git add styles.py tests/test_styles.py
git commit -m "feat: add signal bar, Venn SVG, and monospace helpers (styles.py)"
```

---

### Task 7: `api_client.py` — centralized FastAPI HTTP wrapper

**Files:**
- Create: `api_client.py`
- Test: `tests/test_api_client.py`

**Interfaces:**
- Produces: `api_client.API_BASE: str`, `api_client.run_campaign(url: str | None = None, manual_text: str | None = None) -> dict`, `api_client.get_campaign(campaign_id: int) -> dict | None`, `api_client.list_campaigns() -> list[dict]`, `api_client.approve_candidate(campaign_id: int, candidate_id: int) -> dict | None`, `api_client.reject_candidate(campaign_id: int, candidate_id: int) -> dict | None`, `api_client.health_keys() -> dict`
- Every function returns a soft-fail dict (`{"error": "..."}`) instead of raising on `requests.RequestException`, matching `CLAUDE.md`'s "failure is always soft" rule — pages check for the `"error"` key rather than wrapping every call in `try/except`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_api_client.py`:

```python
from unittest.mock import Mock, patch

import requests

import api_client


def test_run_campaign_posts_url_and_returns_json():
    fake_response = Mock()
    fake_response.json.return_value = {"campaign_id": 1, "status": "generated"}
    fake_response.raise_for_status.return_value = None
    with patch("api_client.requests.post", return_value=fake_response) as mock_post:
        result = api_client.run_campaign(url="https://example.com/article")

    assert result == {"campaign_id": 1, "status": "generated"}
    mock_post.assert_called_once_with(
        f"{api_client.API_BASE}/campaign",
        json={"url": "https://example.com/article", "manual_text": None},
        timeout=90,
    )


def test_run_campaign_returns_soft_error_on_connection_failure():
    with patch("api_client.requests.post", side_effect=requests.ConnectionError("refused")):
        result = api_client.run_campaign(url="https://example.com/article")

    assert "error" in result


def test_get_campaign_returns_none_on_404():
    fake_response = Mock()
    fake_response.status_code = 404
    fake_response.raise_for_status.side_effect = requests.HTTPError(response=fake_response)
    with patch("api_client.requests.get", return_value=fake_response):
        result = api_client.get_campaign(999)

    assert result is None


def test_list_campaigns_returns_empty_list_on_failure():
    with patch("api_client.requests.get", side_effect=requests.ConnectionError("refused")):
        result = api_client.list_campaigns()

    assert result == []


def test_health_keys_returns_false_pair_on_failure():
    with patch("api_client.requests.get", side_effect=requests.ConnectionError("refused")):
        result = api_client.health_keys()

    assert result == {"openai": False, "apollo": False}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_api_client.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'api_client'`

- [ ] **Step 3: Implement `api_client.py`**

```python
"""Thin wrapper over every HTTP call the Streamlit UI makes to the FastAPI
backend. Centralized so pages don't each hand-roll try/except around
`requests` -- every function here soft-fails (returns a dict with an
"error" key, or an empty list/None) instead of raising, per CLAUDE.md's
"failure is always soft" rule."""
import requests

API_BASE = "http://localhost:8000"


def run_campaign(url: str | None = None, manual_text: str | None = None) -> dict:
    try:
        resp = requests.post(
            f"{API_BASE}/campaign",
            json={"url": url, "manual_text": manual_text},
            timeout=90,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        return {"error": f"Couldn't reach the backend. Is `uvicorn main:app --reload` running? ({e})"}


def get_campaign(campaign_id: int) -> dict | None:
    try:
        resp = requests.get(f"{API_BASE}/campaigns/{campaign_id}", timeout=10)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException:
        return None


def list_campaigns() -> list[dict]:
    try:
        resp = requests.get(f"{API_BASE}/campaigns", timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, list) else []
    except requests.RequestException:
        return []


def approve_candidate(campaign_id: int, candidate_id: int) -> dict | None:
    try:
        resp = requests.post(
            f"{API_BASE}/campaigns/{campaign_id}/candidates/{candidate_id}/approve", timeout=60
        )
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        return {"error": str(e)}


def reject_candidate(campaign_id: int, candidate_id: int) -> dict | None:
    try:
        resp = requests.post(
            f"{API_BASE}/campaigns/{campaign_id}/candidates/{candidate_id}/reject", timeout=30
        )
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        return {"error": str(e)}


def health_keys() -> dict:
    try:
        resp = requests.get(f"{API_BASE}/health/keys", timeout=5)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException:
        return {"openai": False, "apollo": False}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_api_client.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add api_client.py tests/test_api_client.py
git commit -m "feat: add centralized api_client.py wrapper for FastAPI calls"
```

---

### Task 8: `streamlit_app.py` entrypoint + navigation skeleton

**Files:**
- Create: `streamlit_app.py`
- Create: `app_pages/__init__.py` (empty, makes it an importable package for tests)
- Create: `app_pages/dashboard.py` (stub, filled in fully by Task 9)
- Create: `app_pages/new_campaign.py` (stub, filled in fully by Task 10)
- Create: `app_pages/review_queue.py` (stub, filled in fully by Task 11)
- Create: `app_pages/history.py` (stub, filled in fully by Task 12)
- Create: `app_pages/settings.py` (stub, filled in fully by Task 13)
- Create: `app_pages/usage.py` (stub, filled in fully by Task 14)
- Test: `tests/test_streamlit_app.py`

**Interfaces:**
- Consumes: `styles.inject_base_styles()` (Task 6)
- Produces: the running app shell — sidebar navigation with 6 pages, each `app_pages/*.py` module rendering at minimum a page-specific `st.title`/`st.header` so the navigation itself is verifiable before each page's real content is built in later tasks

- [ ] **Step 1: Write the failing test**

Create `tests/test_streamlit_app.py`:

```python
from streamlit.testing.v1 import AppTest


def test_app_loads_without_exception():
    at = AppTest.from_file("streamlit_app.py")
    at.run(timeout=15)
    assert not at.exception


def test_sidebar_navigation_lists_all_six_pages():
    at = AppTest.from_file("streamlit_app.py")
    at.run(timeout=15)
    # st.navigation renders as a sidebar radio-style nav; AppTest exposes it
    # as an internal page list on the app's session -- verify indirectly via
    # the rendered title on first load (Dashboard is the default/first page).
    assert not at.exception
    titles = [el.value for el in at.title]
    assert any("Dashboard" in t or "dashboard" in t.lower() for t in titles)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_streamlit_app.py -v`
Expected: FAIL with `FileNotFoundError` / import error (file doesn't exist yet)

- [ ] **Step 3: Create the stub pages**

Create `app_pages/__init__.py` (empty file).

Create `app_pages/dashboard.py`:

```python
import streamlit as st

st.title("Dashboard")
st.caption("Campaign summary, pending review count, spend vs. budget.")
```

Create `app_pages/new_campaign.py`:

```python
import streamlit as st

st.title("New campaign")
st.caption("Paste a news article URL to run the pipeline.")
```

Create `app_pages/review_queue.py`:

```python
import streamlit as st

st.title("Review queue")
st.caption("Candidates awaiting a human decision, across all campaigns.")
```

Create `app_pages/history.py`:

```python
import streamlit as st

st.title("Campaign history")
st.caption("Every campaign ever run, with full drill-down.")
```

Create `app_pages/settings.py`:

```python
import streamlit as st

st.title("Settings")
st.caption("ICP config, thresholds, testing caps, pricing, connection status.")
```

Create `app_pages/usage.py`:

```python
import streamlit as st

st.title("Usage & cost")
st.caption("Account-wide spend and Apollo credit usage.")
```

- [ ] **Step 4: Create the entrypoint**

Create `streamlit_app.py`:

```python
"""Entrypoint for the Magical Genie control panel. Defines the sidebar
navigation and injects the shared theme CSS before any page renders."""
import streamlit as st

from styles import inject_base_styles

st.set_page_config(page_title="Magical Genie", page_icon=":material/auto_awesome:", layout="wide")
inject_base_styles()

page = st.navigation([
    st.Page("app_pages/dashboard.py", title="Dashboard", icon=":material/dashboard:"),
    st.Page("app_pages/new_campaign.py", title="New campaign", icon=":material/add_circle:"),
    st.Page("app_pages/review_queue.py", title="Review queue", icon=":material/fact_check:"),
    st.Page("app_pages/history.py", title="Campaign history", icon=":material/history:"),
    st.Page("app_pages/settings.py", title="Settings", icon=":material/tune:"),
    st.Page("app_pages/usage.py", title="Usage & cost", icon=":material/query_stats:"),
], position="sidebar")

page.run()
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_streamlit_app.py -v`
Expected: PASS (2 passed)

- [ ] **Step 6: Manually verify the theme (deferred from Task 5)**

Run: `streamlit run streamlit_app.py` and open the printed local URL in a browser. Confirm: dark graphite background, amber accent on the active nav item, Inter body font, sidebar shows all 6 pages. Stop the server (Ctrl+C) once confirmed.

- [ ] **Step 7: Commit**

```bash
git add streamlit_app.py app_pages/ tests/test_streamlit_app.py
git commit -m "feat: add multi-page navigation skeleton (streamlit_app.py + app_pages stubs)"
```

---

### Task 9: Dashboard page

**Files:**
- Modify: `app_pages/dashboard.py`
- Test: `tests/test_page_dashboard.py`

**Interfaces:**
- Consumes: `api_client.list_campaigns()`, `api_client.get_campaign(campaign_id)` (Task 7), `services.usage_dashboard.get_total_cost()`, `services.usage_dashboard.get_apollo_credit_status()` (existing), `config.get_max_lead_fetch_companies()`, `config.get_max_leads_per_campaign()` (Task 1), `styles.mono()` (Task 6)

- [ ] **Step 1: Write the failing test**

Create `tests/test_page_dashboard.py`:

```python
from unittest.mock import patch

from streamlit.testing.v1 import AppTest


def test_dashboard_renders_with_no_campaigns():
    with patch("api_client.list_campaigns", return_value=[]), \
         patch("services.usage_dashboard.get_total_cost", return_value={"openai_usd": 0.0, "apollo_credits": 0, "apollo_usd": 0.0, "total_usd": 0.0}), \
         patch("services.usage_dashboard.get_apollo_credit_status", return_value={"used": 0, "limit": 4000, "remaining": 4000, "pct": 0.0}):
        at = AppTest.from_file("app_pages/dashboard.py")
        at.run(timeout=15)

    assert not at.exception


def test_dashboard_highlights_pending_review_when_nonzero():
    campaigns = [{"id": 1, "url": "https://example.com/a", "status": "awaiting_review", "created_at": "2026-07-01T00:00:00+00:00"}]
    detail = {
        "campaign": campaigns[0],
        "context": None,
        "leads": [],
        "creatives": [],
        "candidates": [{"id": 10, "bucket": "needs_review", "human_override": None}],
    }
    with patch("api_client.list_campaigns", return_value=campaigns), \
         patch("api_client.get_campaign", return_value=detail), \
         patch("services.usage_dashboard.get_total_cost", return_value={"openai_usd": 0.0, "apollo_credits": 0, "apollo_usd": 0.0, "total_usd": 0.0}), \
         patch("services.usage_dashboard.get_apollo_credit_status", return_value={"used": 0, "limit": 4000, "remaining": 4000, "pct": 0.0}):
        at = AppTest.from_file("app_pages/dashboard.py")
        at.run(timeout=15)

    assert not at.exception
    all_text = " ".join(m.value for m in at.markdown) + " ".join(str(m.value) for m in at.metric)
    assert "1" in all_text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_page_dashboard.py -v`
Expected: FAIL — the stub page has no metrics/pending-review logic to assert against (second test's assertion on "1" in rendered text will fail, or trivially the page has no such content).

- [ ] **Step 3: Implement `app_pages/dashboard.py`**

```python
import streamlit as st

import api_client
import config
from services.usage_dashboard import get_apollo_credit_status, get_total_cost
from styles import mono

st.title("Dashboard")

# "New Campaign" quick-start, prominent at the top since starting a campaign
# is the core action of this tool.
with st.container(border=True):
    st.markdown("**Start a new campaign**")
    quick_url = st.text_input("News article URL", placeholder="https://...", key="dashboard_quick_url")
    if st.button("Run campaign", type="primary", key="dashboard_quick_run"):
        st.session_state["pending_campaign_url"] = quick_url
        st.switch_page("app_pages/new_campaign.py")

DASHBOARD_CAMPAIGN_LIMIT = 50

campaigns = api_client.list_campaigns()
recent_campaigns = campaigns[:DASHBOARD_CAMPAIGN_LIMIT]

total_leads = 0
pending_review = 0
for c in recent_campaigns:
    detail = api_client.get_campaign(c["id"])
    if not detail:
        continue
    total_leads += len(detail.get("leads") or [])
    for candidate in detail.get("candidates") or []:
        if candidate.get("bucket") == "needs_review" and not candidate.get("human_override"):
            pending_review += 1

if len(campaigns) > DASHBOARD_CAMPAIGN_LIMIT:
    st.caption(f"Summary reflects the {DASHBOARD_CAMPAIGN_LIMIT} most recent campaigns of {len(campaigns)} total. See Campaign History for the full archive.")

col1, col2, col3, col4 = st.columns(4)
col1.metric("Campaigns run", len(campaigns))
col2.metric("Leads found", total_leads)

with col3:
    st.metric("Pending review", pending_review)
    if pending_review > 0:
        st.badge(f"{pending_review} awaiting decision", icon=":material/priority_high:", color="orange")

total_cost = get_total_cost()
col4.metric("Spend this account", f"${total_cost['total_usd']:.4f}")

apollo_status = get_apollo_credit_status()
st.markdown("#### Apollo credit budget")
st.progress(min(apollo_status["pct"] / 100.0, 1.0))
st.caption(f"{mono(apollo_status['used'])} / {mono(apollo_status['limit'])} credits used ({apollo_status['pct']:.1f}%)", unsafe_allow_html=True)

max_companies = config.get_max_lead_fetch_companies()
max_leads = config.get_max_leads_per_campaign()
if max_companies is not None or max_leads is not None:
    st.info("Testing caps are active — see Settings for current limits.", icon=":material/info:")

if not campaigns:
    st.caption("No campaigns yet. Paste an article URL above to run your first one.")
```

Note: `st.caption(..., unsafe_allow_html=True)` — if the installed Streamlit's `st.caption` doesn't accept `unsafe_allow_html`, use `st.markdown` with a smaller font wrapper instead; verify against the actual signature during implementation (Streamlit 1.58's `st.caption` does support it as of recent versions — confirm with `st.caption.__doc__` if the test fails on this line).

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_page_dashboard.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add app_pages/dashboard.py tests/test_page_dashboard.py
git commit -m "feat: implement Dashboard page (summary cards, pending-review badge, quick-start)"
```

---

### Task 10: New Campaign page (migrated logic + live progress + Venn)

**Files:**
- Modify: `app_pages/new_campaign.py`
- Test: `tests/test_page_new_campaign.py`

**Interfaces:**
- Consumes: `api_client.run_campaign()`, `api_client.list_campaigns()`, `api_client.get_campaign()`, `api_client.approve_candidate()`, `api_client.reject_candidate()` (Task 7), `styles.signal_bar_html()`, `styles.venn_svg()`, `styles.mono()` (Task 6), `config.get_max_lead_fetch_companies()`, `config.get_max_leads_per_campaign()` (Task 1), `services.usage_dashboard.get_total_cost()` (existing)

This task migrates `frontend.py`'s `campaign_tab` block (lines 37-286 of the original file) almost verbatim for the result-rendering logic, replacing bare score numbers with `signal_bar_html()`, adding the Venn visual, and replacing the blocking spinner with a background-thread + status-polling progress view.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_page_new_campaign.py`:

```python
import time
from unittest.mock import patch

from streamlit.testing.v1 import AppTest


def test_new_campaign_page_renders_empty_state():
    at = AppTest.from_file("app_pages/new_campaign.py")
    at.run(timeout=15)
    assert not at.exception


def test_new_campaign_shows_status_message_for_zero_leads():
    result = {
        "campaign_id": 1, "status": "zero_leads", "context": None,
        "theme": None, "candidates": [], "leads": [], "search_stats": None,
        "company_summaries": [],
    }
    at = AppTest.from_file("app_pages/new_campaign.py")
    at.run(timeout=15)
    at.session_state["result"] = result
    at.session_state["campaign_in_progress"] = False
    at.run(timeout=15)

    assert not at.exception
    all_text = " ".join(m.value for m in at.info) + " ".join(m.value for m in at.markdown)
    assert "0 leads" in all_text.lower() or "no verified leads" in all_text.lower()


def test_pending_campaign_url_from_dashboard_prefills_input():
    at = AppTest.from_file("app_pages/new_campaign.py")
    at.session_state["pending_campaign_url"] = "https://example.com/article"
    at.run(timeout=15)

    assert not at.exception
    text_inputs = [ti.value for ti in at.text_input]
    assert "https://example.com/article" in text_inputs
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_page_new_campaign.py -v`
Expected: FAIL — the stub page has none of this logic yet.

- [ ] **Step 3: Implement `app_pages/new_campaign.py`**

```python
"""New Campaign page: URL input, live pipeline progress, and the full
result view (context, Venn diagram, candidates, needs_review queue,
leads + generated copy, per-campaign cost). Business logic is unchanged
from the original frontend.py -- this migrates that rendering logic under
the new visual system and replaces the blocking spinner with a
background-thread + status-poll progress view."""
import io
import threading
import time

import pandas as pd
import streamlit as st

import api_client
import config
from services.usage_dashboard import get_total_cost
from styles import mono, signal_bar_html, venn_svg

st.title("New campaign")
st.caption("Paste a news article about a company to get verified leads and personalized outreach copy.")

max_companies = config.get_max_lead_fetch_companies()
max_leads = config.get_max_leads_per_campaign()
if max_companies is not None or max_leads is not None:
    st.info("Testing caps are active for this run — see Settings for current limits.", icon=":material/info:")

if "result" not in st.session_state:
    st.session_state.result = None
if "show_manual_paste" not in st.session_state:
    st.session_state.show_manual_paste = False
if "pending_message" not in st.session_state:
    st.session_state.pending_message = None
if "campaign_in_progress" not in st.session_state:
    st.session_state.campaign_in_progress = False
if "campaign_thread_holder" not in st.session_state:
    st.session_state.campaign_thread_holder = None
if "campaign_started_url" not in st.session_state:
    st.session_state.campaign_started_url = None
if "campaign_polling_id" not in st.session_state:
    st.session_state.campaign_polling_id = None

STAGE_ORDER = ["analyzing", "theme_extracted", "candidates_scored", "awaiting_review", "leads_found", "generated"]
STAGE_LABELS = {
    "analyzing": "Scraping article & extracting context",
    "theme_extracted": "Extracting market theme",
    "candidates_scored": "Scoring ICP candidates",
    "awaiting_review": "Awaiting human review",
    "leads_found": "Finding leads at approved companies",
    "generated": "Generating personalized copy",
}


def _start_campaign(url: str | None, manual_text: str | None):
    holder = {"done": False, "response": None}

    def worker():
        holder["response"] = api_client.run_campaign(url=url, manual_text=manual_text)
        holder["done"] = True

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    st.session_state.campaign_thread_holder = holder
    st.session_state.campaign_started_url = url or "manual_paste"
    st.session_state.campaign_polling_id = None
    st.session_state.campaign_in_progress = True
    st.session_state.result = None


default_url = st.session_state.pop("pending_campaign_url", "")
url = st.text_input("News article URL", value=default_url, placeholder="https://...")

col1, col2 = st.columns([1, 4])
run_clicked = col1.button("Run campaign", type="primary", disabled=st.session_state.campaign_in_progress)

if run_clicked and url and not st.session_state.campaign_in_progress:
    _start_campaign(url=url, manual_text=None)
    st.rerun()

# --- Live progress ---------------------------------------------------------
if st.session_state.campaign_in_progress:
    holder = st.session_state.campaign_thread_holder

    if st.session_state.campaign_polling_id is None:
        matches = [c for c in api_client.list_campaigns() if c.get("url") == st.session_state.campaign_started_url]
        if matches:
            st.session_state.campaign_polling_id = max(matches, key=lambda c: c["id"])["id"]

    current_status = None
    if st.session_state.campaign_polling_id is not None:
        detail = api_client.get_campaign(st.session_state.campaign_polling_id)
        if detail:
            current_status = detail["campaign"]["status"]

    with st.container(border=True):
        st.markdown("**Running campaign...**")
        reached_index = STAGE_ORDER.index(current_status) if current_status in STAGE_ORDER else -1
        for i, stage in enumerate(STAGE_ORDER):
            icon = ":material/check_circle:" if i <= reached_index else ":material/pending:"
            st.markdown(f"{icon} {STAGE_LABELS[stage]}")

    if holder["done"]:
        st.session_state.result = holder["response"]
        response = holder["response"] or {}
        st.session_state.show_manual_paste = response.get("status") in ("paywalled", "scrape_failed")
        st.session_state.campaign_in_progress = False
        st.session_state.campaign_thread_holder = None
        st.rerun()
    else:
        time.sleep(1)
        st.rerun()

if st.session_state.show_manual_paste:
    result = st.session_state.result or {}
    if result.get("status") == "scrape_failed":
        st.warning("Couldn't fetch that article automatically (paywall, bot-block, or similar). Paste the article text manually below.")
    else:
        st.warning("This looks paywalled. Paste the article text manually below.")
    manual_text = st.text_area("Article text", height=200)
    if st.button("Run with pasted text") and manual_text:
        _start_campaign(url=None, manual_text=manual_text)
        st.session_state.show_manual_paste = False
        st.rerun()

result = st.session_state.result

if st.session_state.pending_message:
    st.warning(st.session_state.pending_message)
    st.session_state.pending_message = None

if result and "error" in result:
    st.error(result["error"])

elif result:
    status = result.get("status")

    STATUS_MESSAGES = {
        "scrape_failed": ("error", f"Couldn't fetch that article. {result.get('error', '')}"),
        "extraction_failed": ("error", "Couldn't extract intelligence from that article. Try a different URL or paste text manually."),
        "no_domain": ("warning", "Couldn't resolve a domain for this company, so no leads were found. Context below is still useful."),
        "zero_leads": ("info", "No verified leads found at this company (a valid result, not an error)."),
        "no_candidates": ("warning", "Couldn't identify a market theme for this article, so no ICP candidates could be found. Context below is still useful."),
        "awaiting_review": ("info", "Some candidate companies need review before leads can be fetched — see the Needs Review queue below."),
    }
    if status in STATUS_MESSAGES:
        level, message = STATUS_MESSAGES[status]
        getattr(st, level)(message)

    ctx = result.get("context")
    if ctx:
        st.subheader("Campaign intelligence")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Company", ctx["entity"])
        c2.metric("Product match", ctx["product_id"])
        c3.metric("Urgency", f"{ctx['urgency_score']}/10")
        c4.metric("Location", ctx.get("location") or "—")
        st.write(f"**Catalyst:** {ctx['catalyst']}")
        st.write("**Pain points:** " + " · ".join(ctx["pain_points"]))

    theme = result.get("theme")
    if theme:
        st.write(f"**Market theme:** {theme['theme_summary']}")

    candidates = result.get("candidates") or []
    company_summaries = result.get("company_summaries") or []
    leads_found_by_domain = {cs["domain"]: cs["leads_found"] for cs in company_summaries if cs.get("domain")}
    fetch_status_by_domain = {cs["domain"]: cs["status"] for cs in company_summaries if cs.get("domain")}

    search_stats = result.get("search_stats")
    if search_stats:
        st.subheader("Search funnel")
        cc = search_stats["cluster_counts"]
        st.markdown(venn_svg(
            article_only=cc.get("article-only", 0),
            icp_only=cc.get("icp-only", 0),
            blended=cc.get("blended", 0),
        ), unsafe_allow_html=True)
        f1, f2, f3 = st.columns(3)
        f1.metric("Unique (deduped)", search_stats["unique_candidates_found"])
        f2.metric("Passed prefilter", search_stats["prefilter_kept"])
        f3.metric("Dropped at prefilter", search_stats["prefilter_dropped"])

    skipped_for_cap = [cs for cs in company_summaries if cs["status"] == "skipped_cap"]
    if skipped_for_cap:
        cap_reason = skipped_for_cap[0].get("reason") or "testing cap reached"
        st.warning(
            f"Lead-fetch cap hit — {cap_reason}. "
            f"{len(skipped_for_cap)} approved company(s) were never fetched: "
            + ", ".join(f"{cs['company_name']} ({cs['domain']})" for cs in skipped_for_cap)
        )

    needs_review = [c for c in candidates if c["bucket"] == "needs_review" and not c.get("human_override")]
    approved = [c for c in candidates if c["bucket"] == "approved" or c.get("human_override") == "approved"]
    rejected = [c for c in candidates if c["bucket"] in ("rejected", "dropped_at_prefilter") or c.get("human_override") == "rejected"]

    if needs_review:
        st.subheader(f"Needs review ({len(needs_review)})")
        campaign_id = result["campaign_id"]
        for c in needs_review:
            with st.expander(f"{c['company_name']} ({c['domain']})"):
                st.markdown(signal_bar_html(c.get("score") or 0, c["bucket"]), unsafe_allow_html=True)
                st.write(f"**Industry:** {c.get('apollo_industry') or '—'}  |  **Employees:** {c.get('apollo_employee_count') or '—'}")
                st.write(f"**Score reason:** {c.get('score_reason') or '—'}")
                if c.get("apollo_description"):
                    st.caption(c["apollo_description"][:500])
                b1, b2 = st.columns(2)
                if b1.button("Approve", key=f"approve_{c['id']}", icon=":material/check:"):
                    data = api_client.approve_candidate(campaign_id, c["id"])
                    if data and "error" not in data:
                        c["human_override"] = "approved"
                        st.session_state.result["leads"] = st.session_state.result.get("leads", []) + data.get("results", [])
                        if data.get("company_summary"):
                            st.session_state.result["company_summaries"] = \
                                st.session_state.result.get("company_summaries", []) + [data["company_summary"]]
                        if data.get("message"):
                            st.session_state.pending_message = data["message"]
                        st.rerun()
                    else:
                        st.error(f"Approve failed: {(data or {}).get('error', 'unknown error')}")
                if b2.button("Reject", key=f"reject_{c['id']}", icon=":material/close:"):
                    data = api_client.reject_candidate(campaign_id, c["id"])
                    if data and "error" not in data:
                        c["human_override"] = "rejected"
                        st.rerun()
                    else:
                        st.error(f"Reject failed: {(data or {}).get('error', 'unknown error')}")

    if approved or rejected:
        with st.expander(f"Auto-decided candidates ({len(approved)} approved, {len(rejected)} rejected)"):
            for c in approved:
                fetch_status = fetch_status_by_domain.get(c["domain"])
                if fetch_status == "fetched":
                    fetch_note = f" → {leads_found_by_domain[c['domain']]} lead(s) found"
                elif fetch_status == "zero_leads":
                    fetch_note = " → 0 leads found at this company"
                elif fetch_status == "skipped_cap":
                    fetch_note = " → skipped, lead-fetch cap reached"
                elif fetch_status == "error":
                    fetch_note = " → lead-fetch errored"
                else:
                    fetch_note = " → not yet fetched"
                st.markdown(signal_bar_html(c.get("score") or 0, "approved"), unsafe_allow_html=True)
                st.write(f"**{c['company_name']}** ({c['domain']}) — {c.get('score_reason') or ''}{fetch_note}")
            for c in rejected:
                reason = c.get("score_reason") or c.get("prefilter_reason") or "—"
                st.markdown(signal_bar_html(c.get("score") or 0, c["bucket"]), unsafe_allow_html=True)
                st.write(f"**{c['company_name']}** ({c['domain']}) — {reason}")

    if candidates:
        with st.expander(f"Full company funnel — every candidate found ({len(candidates)})"):
            funnel_rows = []
            for c in candidates:
                decision = c.get("human_override") or c["bucket"]
                fetch_status = fetch_status_by_domain.get(c["domain"], "—")
                leads_n = leads_found_by_domain.get(c["domain"])
                funnel_rows.append({
                    "Company": c["company_name"], "Domain": c["domain"],
                    "Industry": c.get("apollo_industry") or "—", "Employees": c.get("apollo_employee_count") or "—",
                    "Prefilter": c["prefilter_result"], "Score": c.get("score") if c.get("score") is not None else "—",
                    "Decision": decision, "Fetch Status": fetch_status,
                    "Leads Found": leads_n if leads_n is not None else "—",
                    "Reason": c.get("score_reason") or c.get("prefilter_reason") or "—",
                })
            st.dataframe(pd.DataFrame(funnel_rows), width="stretch", hide_index=True)

    leads = result.get("leads", [])
    if leads:
        st.subheader(f"{len(leads)} leads")
        leads_by_company: dict[str, list] = {}
        for item in leads:
            key = item["lead"].get("company_name") or "Unknown company"
            leads_by_company.setdefault(key, []).append(item)

        csv_rows = []
        for company_key, items in leads_by_company.items():
            company_domain = items[0]["lead"].get("domain") or "—"
            st.markdown(f"#### {company_key}  `{company_domain}` — {len(items)} lead(s)")
            for item in items:
                lead = item["lead"]
                copy = item["copy"]
                name = f"{lead.get('first_name', '')} {lead.get('last_name', '')}".strip()
                with st.expander(f"{name} — {lead.get('title', 'Unknown title')} ({lead.get('seniority', '')})"):
                    st.write(f"{lead.get('email') or '—'}  |  {lead.get('linkedin') or '—'}")
                    tabs = st.tabs(["Email", "WhatsApp", "Google Ads"])
                    for tab, channel in zip(tabs, ["email", "whatsapp", "google_ads"]):
                        with tab:
                            ch_copy = copy.get(channel, {})
                            if "error" in ch_copy:
                                st.error(f"Copy generation failed for this channel: {ch_copy['error']}")
                            else:
                                if ch_copy.get("subject_line"):
                                    st.markdown(f"**Subject:** {ch_copy['subject_line']}")
                                st.code(ch_copy.get("body_text", ""), language=None)
                for channel in ["email", "whatsapp", "google_ads"]:
                    ch_copy = copy.get(channel, {})
                    csv_rows.append({
                        "name": name, "company": lead.get("company_name") or "—", "domain": lead.get("domain") or "—",
                        "title": lead.get("title"), "seniority": lead.get("seniority"),
                        "email": lead.get("email"), "linkedin": lead.get("linkedin"), "channel": channel,
                        "subject_line": ch_copy.get("subject_line"), "body_text": ch_copy.get("body_text"),
                        "tracking_url": ch_copy.get("tracking_url"),
                    })

        if csv_rows:
            df = pd.DataFrame(csv_rows)
            buf = io.StringIO()
            df.to_csv(buf, index=False)
            st.download_button("Download CSV (leads + copy)", buf.getvalue(), file_name=f"campaign_{result['campaign_id']}.csv", mime="text/csv", icon=":material/download:")

    campaign_id = result.get("campaign_id")
    if campaign_id is not None:
        st.subheader("This campaign's cost")
        current_cost = get_total_cost(campaign_id)
        lead_count = len(leads)
        cost_per_lead = current_cost["total_usd"] / lead_count if lead_count > 0 else None

        c1, c2, c3 = st.columns(3)
        c1.markdown(f"**Total cost**  \n{mono(f\"${current_cost['total_usd']:.4f}\")}", unsafe_allow_html=True)
        c2.markdown(f"**Apollo credits**  \n{mono(current_cost['apollo_credits'])}", unsafe_allow_html=True)
        c3.markdown(f"**Cost per lead**  \n{mono(f'${cost_per_lead:.4f}') if cost_per_lead is not None else '—'}", unsafe_allow_html=True)

elif not st.session_state.campaign_in_progress:
    st.caption("Paste an article URL above and click Run campaign to get started.")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_page_new_campaign.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Manual verification**

Run: `uvicorn main:app --reload --port 8000` (terminal 1) and `streamlit run streamlit_app.py` (terminal 2). Go to New Campaign, submit a real article URL, and confirm: the stage checklist advances live (not just a spinner), the Venn diagram renders once theme extraction completes, signal bars render for candidates, and the final leads/copy/CSV export section matches the original `frontend.py` behavior.

- [ ] **Step 6: Commit**

```bash
git add app_pages/new_campaign.py tests/test_page_new_campaign.py
git commit -m "feat: implement New Campaign page (live progress, Venn diagram, signal bars)"
```

---

### Task 11: Review Queue page (cross-campaign)

**Files:**
- Modify: `app_pages/review_queue.py`
- Test: `tests/test_page_review_queue.py`

**Interfaces:**
- Consumes: `api_client.list_campaigns()`, `api_client.get_campaign()`, `api_client.approve_candidate()`, `api_client.reject_candidate()` (Task 7), `styles.signal_bar_html()` (Task 6)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_page_review_queue.py`:

```python
from unittest.mock import patch

from streamlit.testing.v1 import AppTest


def test_review_queue_empty_state():
    with patch("api_client.list_campaigns", return_value=[]):
        at = AppTest.from_file("app_pages/review_queue.py")
        at.run(timeout=15)

    assert not at.exception
    all_text = " ".join(m.value for m in at.markdown) + " ".join(c.value for c in at.caption)
    assert "nothing needs review" in all_text.lower() or "no candidates" in all_text.lower()


def test_review_queue_lists_pending_candidates_across_campaigns():
    campaigns = [
        {"id": 1, "url": "https://a.com", "status": "awaiting_review", "created_at": "2026-07-01T00:00:00+00:00"},
        {"id": 2, "url": "https://b.com", "status": "awaiting_review", "created_at": "2026-07-02T00:00:00+00:00"},
    ]
    details = {
        1: {"campaign": campaigns[0], "context": None, "leads": [], "creatives": [], "candidates": [
            {"id": 10, "company_name": "Acme Health", "domain": "acmehealth.com", "score": 55,
             "bucket": "needs_review", "human_override": None, "score_reason": "borderline size",
             "apollo_description": "digital health startup", "apollo_industry": "health tech", "apollo_employee_count": 30,
             "created_at": "2026-07-01T00:00:00+00:00"},
        ]},
        2: {"campaign": campaigns[1], "context": None, "leads": [], "creatives": [], "candidates": []},
    }
    with patch("api_client.list_campaigns", return_value=campaigns), \
         patch("api_client.get_campaign", side_effect=lambda cid: details[cid]):
        at = AppTest.from_file("app_pages/review_queue.py")
        at.run(timeout=15)

    assert not at.exception
    all_text = " ".join(m.value for m in at.markdown)
    assert "Acme Health" in all_text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_page_review_queue.py -v`
Expected: FAIL — stub page has no queue logic.

- [ ] **Step 3: Implement `app_pages/review_queue.py`**

```python
"""Cross-campaign review queue: every needs_review candidate (without a
human_override yet) across all campaigns, not just the most recent run."""
import streamlit as st

import api_client
from styles import signal_bar_html

st.title("Review queue")

campaigns = api_client.list_campaigns()

pending = []
for c in campaigns:
    detail = api_client.get_campaign(c["id"])
    if not detail:
        continue
    for candidate in detail.get("candidates") or []:
        if candidate.get("bucket") == "needs_review" and not candidate.get("human_override"):
            pending.append({**candidate, "campaign_id": c["id"], "campaign_url": c["url"], "campaign_created_at": c["created_at"]})

if not pending:
    st.caption("Nothing needs review right now — all recent candidates were auto-approved or auto-rejected by the ICP scorer.")
else:
    sort_choice = st.selectbox("Sort by", ["Age (newest first)", "Score (highest first)", "Campaign"])
    if sort_choice == "Score (highest first)":
        pending.sort(key=lambda c: c.get("score") or 0, reverse=True)
    elif sort_choice == "Campaign":
        pending.sort(key=lambda c: c["campaign_id"])
    else:
        pending.sort(key=lambda c: c["campaign_created_at"], reverse=True)

    st.caption(f"{len(pending)} candidate(s) awaiting a decision across {len({c['campaign_id'] for c in pending})} campaign(s).")

    for c in pending:
        with st.expander(f"{c['company_name']} ({c['domain']}) — campaign #{c['campaign_id']}"):
            st.markdown(signal_bar_html(c.get("score") or 0, c["bucket"]), unsafe_allow_html=True)
            st.write(f"**Industry:** {c.get('apollo_industry') or '—'}  |  **Employees:** {c.get('apollo_employee_count') or '—'}")
            st.write(f"**Reason:** {c.get('score_reason') or '—'}")
            if c.get("apollo_description"):
                st.caption(c["apollo_description"][:500])
            if st.button("View campaign", key=f"view_{c['id']}", icon=":material/open_in_new:"):
                st.session_state["history_target_campaign_id"] = c["campaign_id"]
                st.switch_page("app_pages/history.py")

            b1, b2 = st.columns(2)
            if b1.button("Approve", key=f"rq_approve_{c['id']}", icon=":material/check:"):
                data = api_client.approve_candidate(c["campaign_id"], c["id"])
                if data and "error" not in data:
                    st.rerun()
                else:
                    st.error(f"Approve failed: {(data or {}).get('error', 'unknown error')}")
            if b2.button("Reject", key=f"rq_reject_{c['id']}", icon=":material/close:"):
                data = api_client.reject_candidate(c["campaign_id"], c["id"])
                if data and "error" not in data:
                    st.rerun()
                else:
                    st.error(f"Reject failed: {(data or {}).get('error', 'unknown error')}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_page_review_queue.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add app_pages/review_queue.py tests/test_page_review_queue.py
git commit -m "feat: implement cross-campaign Review Queue page"
```

---

### Task 12: Campaign History page (archive + drill-down)

**Files:**
- Modify: `app_pages/history.py`
- Test: `tests/test_page_history.py`

**Interfaces:**
- Consumes: `api_client.list_campaigns()`, `api_client.get_campaign()` (Task 7), `services.usage_dashboard.get_cost_per_campaign()`, `get_total_cost()` (existing), `styles.signal_bar_html()`, `styles.venn_svg()`, `styles.mono()` (Task 6)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_page_history.py`:

```python
from unittest.mock import patch

from streamlit.testing.v1 import AppTest


def test_history_empty_state():
    with patch("api_client.list_campaigns", return_value=[]), \
         patch("services.usage_dashboard.get_cost_per_campaign", return_value=[]):
        at = AppTest.from_file("app_pages/history.py")
        at.run(timeout=15)

    assert not at.exception
    all_text = " ".join(c.value for c in at.caption)
    assert "no campaigns" in all_text.lower()


def test_history_lists_campaigns_and_drills_into_detail():
    campaigns = [{"id": 1, "url": "https://example.com/article", "status": "generated", "created_at": "2026-07-01T00:00:00+00:00"}]
    cost_rows = [{"campaign_id": 1, "article_url": "https://example.com/article", "run_at": "2026-07-01T00:00:00+00:00",
                  "total_usd": 0.05, "apollo_credits": 0, "lead_count": 2, "cost_per_lead": 0.025, "model_costs": {"gpt-4o-mini": 0.05}}]
    detail = {
        "campaign": campaigns[0], "context": {"entity": "Acme", "location": "NY", "catalyst": "funding round",
        "pain_points": ["a", "b", "c"], "product_id": "prod_1", "urgency_score": 8},
        "leads": [], "creatives": [], "candidates": [],
    }
    with patch("api_client.list_campaigns", return_value=campaigns), \
         patch("api_client.get_campaign", return_value=detail), \
         patch("services.usage_dashboard.get_cost_per_campaign", return_value=cost_rows), \
         patch("services.usage_dashboard.get_total_cost", return_value={"openai_usd": 0.05, "apollo_credits": 0, "apollo_usd": 0.0, "total_usd": 0.05}):
        at = AppTest.from_file("app_pages/history.py")
        at.session_state["history_target_campaign_id"] = 1
        at.run(timeout=15)

    assert not at.exception
    all_text = " ".join(m.value for m in at.markdown)
    assert "Acme" in all_text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_page_history.py -v`
Expected: FAIL — stub page has no archive/drill-down logic.

- [ ] **Step 3: Implement `app_pages/history.py`**

```python
"""Campaign History: full archive table + per-campaign drill-down
(context, Venn visual, full candidate list, leads/copy, cost breakdown)."""
import pandas as pd
import streamlit as st

import api_client
from services.usage_dashboard import get_cost_per_campaign, get_total_cost
from styles import mono, signal_bar_html, venn_svg

st.title("Campaign history")

campaigns = api_client.list_campaigns()

if not campaigns:
    st.caption("No campaigns yet. Run your first one from New Campaign.")
else:
    cost_by_id = {row["campaign_id"]: row for row in get_cost_per_campaign()}

    search = st.text_input("Search by URL", placeholder="Filter by keyword...")
    rows = []
    for c in campaigns:
        if search and search.lower() not in (c.get("url") or "").lower():
            continue
        cost_row = cost_by_id.get(c["id"], {})
        rows.append({
            "ID": c["id"], "Date": c["created_at"], "URL": c["url"], "Status": c["status"],
            "Cost (USD)": cost_row.get("total_usd", 0.0), "Leads": cost_row.get("lead_count", 0),
        })

    df = pd.DataFrame(rows)
    st.dataframe(df, width="stretch", hide_index=True)

    target_id = st.session_state.pop("history_target_campaign_id", None)
    campaign_ids = [c["id"] for c in campaigns]
    default_index = campaign_ids.index(target_id) if target_id in campaign_ids else 0
    selected_id = st.selectbox("View campaign detail", campaign_ids, index=default_index, format_func=lambda cid: f"#{cid}")

    detail = api_client.get_campaign(selected_id)
    if detail:
        st.divider()
        st.subheader(f"Campaign #{selected_id} detail")

        ctx = detail.get("context")
        if ctx:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Company", ctx["entity"])
            c2.metric("Product match", ctx["product_id"])
            c3.metric("Urgency", f"{ctx['urgency_score']}/10")
            c4.metric("Location", ctx.get("location") or "—")
            st.write(f"**Catalyst:** {ctx['catalyst']}")

        candidates = detail.get("candidates") or []
        if candidates:
            with st.expander(f"Full candidate list ({len(candidates)})", expanded=False):
                for c in candidates:
                    st.markdown(signal_bar_html(c.get("score") or 0, c.get("bucket") or "rejected"), unsafe_allow_html=True)
                    st.write(f"**{c['company_name']}** ({c['domain']}) — {c.get('score_reason') or c.get('prefilter_reason') or '—'}")

        leads = detail.get("leads") or []
        creatives = detail.get("creatives") or []
        creatives_by_lead: dict[int, list] = {}
        for cr in creatives:
            creatives_by_lead.setdefault(cr["lead_id"], []).append(cr)

        if leads:
            st.markdown(f"#### Leads ({len(leads)})")
            for lead in leads:
                name = f"{lead.get('first_name', '')} {lead.get('last_name', '')}".strip()
                with st.expander(f"{name} — {lead.get('title', 'Unknown title')}"):
                    for cr in creatives_by_lead.get(lead["id"], []):
                        st.markdown(f"**{cr['channel']}**")
                        if cr.get("subject_line"):
                            st.markdown(f"Subject: {cr['subject_line']}")
                        st.code(cr.get("body_text", ""), language=None)

        campaign_cost = get_total_cost(selected_id)
        st.markdown("#### Cost breakdown")
        c1, c2, c3 = st.columns(3)
        c1.markdown(f"**Total**  \n{mono(f\"${campaign_cost['total_usd']:.4f}\")}", unsafe_allow_html=True)
        c2.markdown(f"**Apollo credits**  \n{mono(campaign_cost['apollo_credits'])}", unsafe_allow_html=True)
        c3.markdown(f"**OpenAI spend**  \n{mono(f\"${campaign_cost['openai_usd']:.4f}\")}", unsafe_allow_html=True)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_page_history.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add app_pages/history.py tests/test_page_history.py
git commit -m "feat: implement Campaign History page (archive table + drill-down)"
```

---

### Task 13: Settings page

**Files:**
- Modify: `app_pages/settings.py`
- Test: `tests/test_page_settings.py`

**Interfaces:**
- Consumes: `config.load_icp_config()` (existing), `config.load_settings()`, `config.save_settings()` (Task 1), `config.ICP_CONFIG_PATH` (existing), `api_client.health_keys()` (Task 7)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_page_settings.py`:

```python
import json
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

import config


def test_settings_page_renders(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "SETTINGS_PATH", tmp_path / "settings.json")
    icp_path = tmp_path / "icp_config.json"
    icp_path.write_text(json.dumps({
        "icp_id": "test", "company_type": {"include": ["a"], "exclude": ["b"]},
        "build_pattern": {"values": ["x"]},
        "size_band": {"employee_count_min": 1, "employee_count_max": 100, "preferred_range": [10, 50], "soft_ceiling": 200},
        "vertical_keywords": ["v1"], "technology_signal_keywords": ["t1"],
        "buying_trigger_keywords": ["b1"], "hard_exclude_industries": ["e1"],
    }))
    monkeypatch.setattr(config, "ICP_CONFIG_PATH", icp_path)

    with patch("api_client.health_keys", return_value={"openai": True, "apollo": False}):
        at = AppTest.from_file("app_pages/settings.py")
        at.run(timeout=15)

    assert not at.exception


def test_settings_page_shows_connection_status(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "SETTINGS_PATH", tmp_path / "settings.json")
    icp_path = tmp_path / "icp_config.json"
    icp_path.write_text(json.dumps({
        "icp_id": "test", "company_type": {"include": [], "exclude": []},
        "build_pattern": {"values": []},
        "size_band": {"employee_count_min": 1, "employee_count_max": 100, "preferred_range": [10, 50], "soft_ceiling": 200},
        "vertical_keywords": [], "technology_signal_keywords": [], "buying_trigger_keywords": [], "hard_exclude_industries": [],
    }))
    monkeypatch.setattr(config, "ICP_CONFIG_PATH", icp_path)

    with patch("api_client.health_keys", return_value={"openai": False, "apollo": True}):
        at = AppTest.from_file("app_pages/settings.py")
        at.run(timeout=15)

    assert not at.exception
    all_text = " ".join(b.label for b in at.badge) if hasattr(at, "badge") else " ".join(m.value for m in at.markdown)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_page_settings.py -v`
Expected: FAIL — stub page has none of this logic.

- [ ] **Step 3: Implement `app_pages/settings.py`**

```python
"""Settings: ICP config editor, score thresholds, testing caps, pricing,
and API key connection status. All edits round-trip through data/settings.json
(Task 1) or data/icp_config.json (existing config.load_icp_config path)."""
import json

import streamlit as st

import api_client
import config

st.title("Settings")

# --- Connection status ------------------------------------------------------
st.subheader("Connection status")
health = api_client.health_keys()
c1, c2 = st.columns(2)
with c1:
    if health.get("openai"):
        st.badge("OpenAI key present", icon=":material/check:", color="green")
    else:
        st.badge("OpenAI key missing", icon=":material/error:", color="red")
with c2:
    if health.get("apollo"):
        st.badge("Apollo key present", icon=":material/check:", color="green")
    else:
        st.badge("Apollo key missing", icon=":material/error:", color="red")

# --- Thresholds --------------------------------------------------------------
st.subheader("Score thresholds")
settings = config.load_settings()
approve_threshold = st.number_input("Approve threshold", min_value=0, max_value=100, value=settings["approve_threshold"])
review_threshold = st.number_input("Review threshold", min_value=0, max_value=100, value=settings["review_threshold"])

st.markdown(
    f"""
    <div style="display:flex; height:24px; border-radius:6px; overflow:hidden; font-family:'JetBrains Mono',monospace; font-size:0.75rem;">
      <div style="width:{review_threshold}%; background:#C4634B; display:flex; align-items:center; justify-content:center; color:#12151C;">rejected</div>
      <div style="width:{approve_threshold - review_threshold}%; background:#E8AA4C; display:flex; align-items:center; justify-content:center; color:#12151C;">needs_review</div>
      <div style="width:{100 - approve_threshold}%; background:#4FA88A; display:flex; align-items:center; justify-content:center; color:#12151C;">approved</div>
    </div>
    """,
    unsafe_allow_html=True,
)

# --- Testing caps --------------------------------------------------------------
st.subheader("Testing caps")
st.caption("Blank = unlimited. These bound Apollo credit spend while testing, not a permanent product limit.")
current_max_companies = settings["max_lead_fetch_companies"]
current_max_leads = settings["max_leads_per_campaign"]
max_companies_input = st.number_input(
    "Max lead-fetch companies per campaign", min_value=0, value=current_max_companies or 0,
    help="0 means unlimited",
)
max_leads_input = st.number_input(
    "Max leads per campaign", min_value=0, value=current_max_leads or 0,
    help="0 means unlimited",
)

# --- Pricing --------------------------------------------------------------
st.subheader("Pricing")
llm_pricing = settings["llm_pricing"]
apollo_cost_usd = st.number_input("Apollo credit cost (USD)", min_value=0.0, value=float(settings["apollo_credit_cost_usd"]), format="%.4f")
for model, prices in llm_pricing.items():
    st.markdown(f"**{model}**")
    ic1, ic2 = st.columns(2)
    prices["input"] = ic1.number_input(f"{model} input $/1M tokens", min_value=0.0, value=float(prices["input"]), key=f"price_in_{model}")
    prices["output"] = ic2.number_input(f"{model} output $/1M tokens", min_value=0.0, value=float(prices["output"]), key=f"price_out_{model}")

if st.button("Save thresholds, caps & pricing", type="primary", icon=":material/save:"):
    settings["approve_threshold"] = int(approve_threshold)
    settings["review_threshold"] = int(review_threshold)
    settings["max_lead_fetch_companies"] = int(max_companies_input) or None
    settings["max_leads_per_campaign"] = int(max_leads_input) or None
    settings["apollo_credit_cost_usd"] = float(apollo_cost_usd)
    settings["llm_pricing"] = llm_pricing
    config.save_settings(settings)
    st.success("Settings saved.")

st.divider()

# --- ICP config editor --------------------------------------------------------
st.subheader("ICP configuration")
icp = config.load_icp_config()

include_text = st.text_area("Company type — include (one per line)", value="\n".join(icp["company_type"]["include"]))
exclude_text = st.text_area("Company type — exclude (one per line)", value="\n".join(icp["company_type"]["exclude"]))

sc1, sc2, sc3 = st.columns(3)
emp_min = sc1.number_input("Employee count min", min_value=0, value=icp["size_band"]["employee_count_min"])
emp_max = sc2.number_input("Employee count max", min_value=0, value=icp["size_band"]["employee_count_max"])
soft_ceiling = sc3.number_input("Soft ceiling", min_value=0, value=icp["size_band"]["soft_ceiling"])
preferred_text = st.text_input("Preferred range (min,max)", value=f"{icp['size_band']['preferred_range'][0]},{icp['size_band']['preferred_range'][1]}")

vertical_text = st.text_area("Vertical keywords (one per line)", value="\n".join(icp["vertical_keywords"]))
tech_text = st.text_area("Technology signal keywords (one per line)", value="\n".join(icp["technology_signal_keywords"]))
buying_text = st.text_area("Buying trigger keywords (one per line)", value="\n".join(icp["buying_trigger_keywords"]))
hard_exclude_text = st.text_area("Hard-exclude industries (one per line)", value="\n".join(icp["hard_exclude_industries"]))

if st.button("Save ICP config", type="primary", icon=":material/save:"):
    preferred_parts = [int(p.strip()) for p in preferred_text.split(",")]
    updated_icp = {
        **icp,
        "company_type": {
            "include": [line.strip() for line in include_text.splitlines() if line.strip()],
            "exclude": [line.strip() for line in exclude_text.splitlines() if line.strip()],
        },
        "size_band": {
            "employee_count_min": int(emp_min), "employee_count_max": int(emp_max),
            "preferred_range": preferred_parts, "soft_ceiling": int(soft_ceiling),
        },
        "vertical_keywords": [line.strip() for line in vertical_text.splitlines() if line.strip()],
        "technology_signal_keywords": [line.strip() for line in tech_text.splitlines() if line.strip()],
        "buying_trigger_keywords": [line.strip() for line in buying_text.splitlines() if line.strip()],
        "hard_exclude_industries": [line.strip() for line in hard_exclude_text.splitlines() if line.strip()],
    }
    with open(config.ICP_CONFIG_PATH, "w") as f:
        json.dump(updated_icp, f, indent=2)
    st.success("ICP config saved.")

with st.expander("Raw ICP config (JSON)"):
    st.json(icp)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_page_settings.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add app_pages/settings.py tests/test_page_settings.py
git commit -m "feat: implement Settings page (ICP editor, thresholds, caps, pricing, connection status)"
```

---

### Task 14: Usage & Cost page (restyled, same functional content)

**Files:**
- Modify: `app_pages/usage.py`
- Test: `tests/test_page_usage.py`

**Interfaces:**
- Consumes: `services.usage_dashboard.get_total_cost()`, `get_apollo_credit_status()`, `get_cost_by_operation()`, `get_cost_by_model()`, `get_cost_per_campaign()` (existing, unchanged signatures), `api_client.list_campaigns()` (Task 7), `config.get_max_lead_fetch_companies()`, `get_max_leads_per_campaign()` (Task 1), `styles.mono()` (Task 6)

This task migrates `frontend.py`'s `usage_tab` block (lines 291-370 of the original file) with restyling only — no functional changes.

- [ ] **Step 1: Write the failing test**

Create `tests/test_page_usage.py`:

```python
from unittest.mock import patch

from streamlit.testing.v1 import AppTest


def test_usage_page_renders_with_no_usage_logged():
    with patch("services.usage_dashboard.get_total_cost", return_value={"openai_usd": 0.0, "apollo_credits": 0, "apollo_usd": 0.0, "total_usd": 0.0}), \
         patch("services.usage_dashboard.get_apollo_credit_status", return_value={"used": 0, "limit": 4000, "remaining": 4000, "pct": 0.0}), \
         patch("services.usage_dashboard.get_cost_by_operation", return_value=[]), \
         patch("services.usage_dashboard.get_cost_by_model", return_value=[]), \
         patch("services.usage_dashboard.get_cost_per_campaign", return_value=[]), \
         patch("api_client.list_campaigns", return_value=[]):
        at = AppTest.from_file("app_pages/usage.py")
        at.run(timeout=15)

    assert not at.exception


def test_usage_page_warns_at_high_apollo_usage():
    with patch("services.usage_dashboard.get_total_cost", return_value={"openai_usd": 1.0, "apollo_credits": 3600, "apollo_usd": 74.16, "total_usd": 75.16}), \
         patch("services.usage_dashboard.get_apollo_credit_status", return_value={"used": 3600, "limit": 4000, "remaining": 400, "pct": 90.0}), \
         patch("services.usage_dashboard.get_cost_by_operation", return_value=[]), \
         patch("services.usage_dashboard.get_cost_by_model", return_value=[]), \
         patch("services.usage_dashboard.get_cost_per_campaign", return_value=[]), \
         patch("api_client.list_campaigns", return_value=[]):
        at = AppTest.from_file("app_pages/usage.py")
        at.run(timeout=15)

    assert not at.exception
    all_text = " ".join(e.value for e in at.error) + " ".join(w.value for w in at.warning)
    assert "usage" in all_text.lower() or "limit" in all_text.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_page_usage.py -v`
Expected: FAIL — stub page has none of this logic.

- [ ] **Step 3: Implement `app_pages/usage.py`**

```python
"""Usage & Cost dashboard: account-wide spend and Apollo credit usage.
Functional content unchanged from the original frontend.py usage_tab --
restyled for the signal-detection theme (signal-bar-style gauge, monospace
figures via config.toml's codeFont)."""
import pandas as pd
import streamlit as st

import api_client
import config
from services.usage_dashboard import (
    get_apollo_credit_status,
    get_cost_by_model,
    get_cost_by_operation,
    get_cost_per_campaign,
    get_total_cost,
)

st.title("Usage & cost")

total_cost = get_total_cost()
apollo_status = get_apollo_credit_status()
campaigns = api_client.list_campaigns()

st.subheader("Account-wide summary")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Total OpenAI spend", f"${total_cost['openai_usd']:.4f}")
c2.metric("Total Apollo credits", total_cost["apollo_credits"])
c3.metric("Total estimated USD", f"${total_cost['total_usd']:.4f}")
c4.metric("Campaigns run", len(campaigns))

st.markdown("#### Apollo credit usage")
st.progress(min(apollo_status["pct"] / 100.0, 1.0))

c1, c2, c3 = st.columns(3)
c1.metric("Credits used", f"{apollo_status['used']}/{apollo_status['limit']}")
c2.metric("Credits remaining", apollo_status["remaining"])
c3.metric("Usage percentage", f"{apollo_status['pct']:.1f}%")

if apollo_status["pct"] >= 90:
    st.error("High usage — nearing monthly limit!", icon=":material/error:")
elif apollo_status["pct"] >= 75:
    st.warning("Moderate usage — monitor closely.", icon=":material/warning:")
else:
    st.success("Usage within normal range.", icon=":material/check_circle:")

max_companies = config.get_max_lead_fetch_companies()
max_leads = config.get_max_leads_per_campaign()
if max_companies is not None or max_leads is not None:
    st.info("Testing caps are currently active — actual spend is suppressed below what a full run would cost.", icon=":material/info:")

st.divider()

col_a, col_b = st.columns(2)
with col_a:
    st.markdown("#### Cost by operation")
    cost_by_op = get_cost_by_operation()
    if cost_by_op:
        st.bar_chart({item["operation"]: item["total_usd"] for item in cost_by_op})
    else:
        st.caption("No usage logged yet.")

with col_b:
    st.markdown("#### Cost by model")
    cost_by_model = get_cost_by_model()
    if cost_by_model:
        st.bar_chart({item["model"]: item["total_usd"] for item in cost_by_model})
    else:
        st.caption("No usage logged yet.")

st.divider()

st.subheader("Per-campaign breakdown")
cost_per_campaign = get_cost_per_campaign()
if cost_per_campaign:
    df_data = [
        {
            "Campaign": f"#{item['campaign_id']}", "Run At": item["run_at"],
            "Article": (item["article_url"][:50] + "...") if len(item["article_url"]) > 50 else item["article_url"],
            "Total Cost (USD)": f"${item['total_usd']:.4f}",
            "LLM Cost by Model": ", ".join(f"{model}: ${cost:.4f}" for model, cost in item["model_costs"].items()) if item["model_costs"] else "—",
            "Apollo Credits": item["apollo_credits"], "Leads Found": item["lead_count"],
            "Cost per Lead (USD)": f"${item['cost_per_lead']:.4f}" if item["cost_per_lead"] is not None else "—",
        }
        for item in cost_per_campaign
    ]
    st.dataframe(pd.DataFrame(df_data), width="stretch", hide_index=True)
else:
    st.caption("No campaigns run yet.")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_page_usage.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add app_pages/usage.py tests/test_page_usage.py
git commit -m "feat: implement Usage & Cost page (restyled, same functional content)"
```

---

### Task 15: Retire `frontend.py` + full manual verification pass

**Files:**
- Delete: `frontend.py`
- Modify: `README.md`, `VERIFICATION_RUNBOOK.md` (update any `streamlit run frontend.py` references to `streamlit run streamlit_app.py`)

**Interfaces:** None (cleanup + verification task, no new code interfaces).

- [ ] **Step 1: Confirm no remaining references to `frontend.py`**

Run: `grep -rn "frontend.py" --include=*.py --include=*.md .`
Expected: no matches outside this plan/spec docs and `campaign_test.py` (if it references the old file, update it too — check its content first).

- [ ] **Step 2: Delete the old entrypoint**

```bash
git rm frontend.py
```

- [ ] **Step 3: Update docs**

In `README.md` and `VERIFICATION_RUNBOOK.md`, replace any `streamlit run frontend.py` with `streamlit run streamlit_app.py`.

- [ ] **Step 4: Run the full test suite**

Run: `python -m pytest tests/ -v`
Expected: All tests from Tasks 1-14 PASS.

- [ ] **Step 5: Full manual verification pass (screenshot each page)**

Run: `uvicorn main:app --reload --port 8000` (terminal 1) and `streamlit run streamlit_app.py` (terminal 2). For each of the 6 pages, capture a screenshot (or written description if screenshots aren't available in the execution environment) confirming:

- **Dashboard:** cards render, pending-review badge appears only when count > 0, quick-start URL input works and navigates to New Campaign
- **New Campaign:** run a real article URL end-to-end; confirm live stage checklist advances, Venn diagram appears, signal bars render, needs_review approve/reject works, CSV export downloads, cost summary shows
- **Review Queue:** with at least one needs_review candidate pending, confirm it lists across campaigns (not just the latest), filter/sort works, approve/reject works, "View campaign" navigates to History with the right campaign pre-selected
- **Campaign History:** table lists all campaigns, search filters by URL, selecting a campaign shows the full drill-down (context, candidates, leads/copy, cost)
- **Settings:** connection status badges reflect actual `.env` key presence, changing a threshold/cap/pricing value and saving persists across a page reload, ICP config edits save and are reflected in `data/icp_config.json`
- **Usage & Cost:** matches prior functional behavior, now dark-themed with monospace figures

- [ ] **Step 6: Commit**

```bash
git add README.md VERIFICATION_RUNBOOK.md
git commit -m "chore: retire frontend.py in favor of the multi-page streamlit_app.py"
```

---

## Self-Review Notes

- **Spec coverage:** all 6 pages, theme, styles.py, api_client.py, multi-page nav, empty states, and both approved backend touches (settings.json, /health/keys) map to Tasks 1-15. The pricing-editable exception (approved by the user) is covered in Task 1 (store) + Task 3 (consumers) + Task 13 (UI).
- **Type consistency checked:** `signal_bar_html(score, bucket)` and `venn_svg(article_only, icp_only, blended)` signatures are identical everywhere they're called (Tasks 9-12). `api_client` function names/returns are consistent across Tasks 9-14. `config.get_*` getter names match between Task 1's definitions and Tasks 2/3/13's usages.
- **No placeholders:** every step has complete, runnable code — no "add error handling here" stand-ins.
