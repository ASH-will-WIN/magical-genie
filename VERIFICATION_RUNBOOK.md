# Magical Genie — Rebuild Verification Runbook

## Purpose

The original Magical Genie project (a working MVP, Phases 1-6 complete) was
lost when local files were deleted. It was reconstructed from a project
summary document — **not from the original source code**, which no longer
exists anywhere. This runbook is a systematic checklist to verify the rebuild
in this folder actually matches the original spec and behaves correctly.

**Read this whole file before touching anything.** Then work through each
section in order, checking off items as you confirm them. Where a check
fails, fix it before moving to the next section — later sections assume
earlier ones pass.

Two things to hold in tension while doing this:

1. **Don't assume the rebuild is correct just because it runs.** It was
   written from a prose summary, not the original code, so subtle behavioral
   gaps are the likely failure mode, not crashes. Section 4 exists
   specifically to catch those.
2. **Don't "improve" things that are deliberately unusual.** `CLAUDE.md` in
   this folder documents non-negotiable design decisions (soft-fail
   everywhere, free Apollo endpoint only, SQLite over Postgres, no email
   sending, etc.). If verification surfaces something that looks like a bug
   but is actually one of those documented decisions, leave it alone.

---

## Section 0: Prerequisites

- [ ] `python3 --version` is 3.10+ (uses `X | None` union syntax throughout)
- [ ] Network access confirmed to `pypi.org` / `pythonhosted.org` (for pip)
- [ ] You have real API keys available for `OPENAI_API_KEY` and
      `APOLLO_API_KEY`, OR you accept that Sections 4.2–4.4 can only be
      verified with mocks, not live calls. State which mode you're
      verifying in before starting.

```bash
cd magical-genie
python3 --version
pip install -r requirements.txt --break-system-packages   # or use a venv
pip install pyflakes --break-system-packages              # for lint checks below
cp .env.example .env
# now edit .env and fill in real keys if doing a live-API verification pass
```

---

## Section 1: File Inventory

Confirm every file below exists and is non-empty. Run:

```bash
find . -type f -not -path "./__pycache__/*" -not -path "./.git/*" | sort
```

Expected file list (21 files):

```
.env.example
.gitignore
CLAUDE.md
README.md
campaign_test.py
config.py
data/product_catalog.json
database.py
frontend.py
main.py
requirements.txt
services/__init__.py
services/apollo.py
services/context.py
services/copy.py
services/scraper.py
services/tracker.py
services/usage_tracker.py
```

(`.env` will also exist locally after Section 0 but is gitignored — don't
expect it in a fresh clone.)

- [ ] No file is missing from the list above
- [ ] No extra/orphaned files exist that aren't explained by this runbook or
      `.gitignore` (stray `.bak` files, duplicate versions like `main2.py`,
      leftover scratch scripts, etc.)
- [ ] `campaigns.db` is NOT checked into git (`git status` should not show it
      if `.git` exists; `.gitignore` should list it either way)

---

## Section 2: Static Correctness

These catch syntax errors, bad imports, and dead code without needing API
keys or a running server.

```bash
python3 -m py_compile main.py frontend.py database.py config.py campaign_test.py services/*.py
python3 -m pyflakes main.py frontend.py database.py config.py campaign_test.py services/*.py
```

- [ ] Both commands produce **zero output** and exit code 0. Any output is a
      real problem — fix it, don't suppress it.

```bash
python3 -c "
import config, database
print('product_ids:', config.product_ids())
database.init_db()
with database.get_conn() as conn:
    tables = [r['name'] for r in conn.execute(\"SELECT name FROM sqlite_master WHERE type='table'\").fetchall()]
print('tables:', tables)
"
```

- [ ] `product_ids()` returns a non-empty list matching `data/product_catalog.json`
- [ ] `tables` includes exactly: `campaigns, sqlite_sequence, contexts, leads, creatives, clicks, usage_log`
      (see Section 3 for schema detail — `sqlite_sequence` is an internal
      SQLite artifact from `AUTOINCREMENT`, expected)

```bash
python3 -c "
import services.scraper, services.context, services.apollo, services.copy, services.tracker, services.usage_tracker
import main
print('all modules + FastAPI app import cleanly')
for r in main.app.routes:
    if hasattr(r, 'methods'):
        print(list(r.methods), r.path)
"
```

- [ ] No import errors
- [ ] Route list includes exactly these 7 application routes (plus
      auto-generated `/docs`, `/redoc`, `/openapi.json`, which you can ignore):
      `GET /health`, `POST /scrape`, `POST /analyze`, `POST /campaign`,
      `POST /click`, `GET /campaigns`, `GET /campaigns/{campaign_id}`

---

## Section 3: Database Schema Verification

Cross-check `database.py`'s `SCHEMA` string against this table-by-table spec.
For each table, confirm every listed column exists with a compatible type.

### `campaigns`

| column     | type                              | notes                                                                                                                                                                                                  |
| ---------- | --------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| id         | INTEGER PK AUTOINCREMENT          |                                                                                                                                                                                                        |
| url        | TEXT NOT NULL                     |                                                                                                                                                                                                        |
| industry   | TEXT                              | nullable, currently unused by the pipeline — that's fine, it's a placeholder from the original schema                                                                                                  |
| geo        | TEXT                              | nullable, same as above                                                                                                                                                                                |
| status     | TEXT NOT NULL DEFAULT 'analyzing' | **must only ever be set to one of:** `analyzing`, `context_extracted`, `leads_found`, `generated`, `failed`. No other value (e.g. `completed`, `done`, `success`) should appear anywhere in `main.py`. |
| created_at | TEXT NOT NULL                     | ISO 8601                                                                                                                                                                                               |

```bash
grep -n 'set_status(' main.py
```

- [ ] Every string literal passed to `set_status(...)` is one of the 5 values above. If you see anything else, that's a regression — fix it to reuse `"generated"` for "pipeline completed, possibly with zero leads" cases (no_domain, zero_leads), matching the original 5-state design.

### `contexts`

| column        | notes                                                                                                                                                                                                                                                                              |
| ------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| campaign_id   | FK to campaigns                                                                                                                                                                                                                                                                    |
| entity        | company name                                                                                                                                                                                                                                                                       |
| location      | **derived/computed display string**, e.g. `"Detroit, MI, USA"` — do not expect this to be an LLM-extracted field directly; it's built from `city`/`state`/`country` on the `CampaignContext` Pydantic model via a `@computed_field`. Confirm this exists in `services/context.py`. |
| catalyst      | one-sentence news event                                                                                                                                                                                                                                                            |
| pain_points   | JSON-encoded array, **must contain exactly 3 items**, enforced via `Field(..., min_length=3, max_length=3)` on `CampaignContext.pain_points`                                                                                                                                       |
| product_id    | must be one of the ids in `data/product_catalog.json` — enforced via a `field_validator`                                                                                                                                                                                           |
| urgency_score | integer 1-10, enforced via `Field(..., ge=1, le=10)`                                                                                                                                                                                                                               |

- [ ] Confirm the min/max=3 constraint on `pain_points` in `services/context.py`
- [ ] Confirm the `product_id` validator actually calls `config.product_ids()` and raises if not found
- [ ] Confirm `urgency_score` bounds

### `leads`

| column                         | notes                                                                                                                                                                                                         |
| ------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| apollo_id                      |                                                                                                                                                                                                               |
| seniority                      | must be normalized to exactly one of `director`, `vp`, `c_suite` — never Apollo's raw seniority string. Check `services/apollo.py`'s `normalize_seniority()`.                                                 |
| UNIQUE(campaign_id, apollo_id) | prevents duplicate leads per campaign — confirm this constraint exists in the schema and that `main.py` uses `INSERT OR IGNORE` when inserting leads (not a plain `INSERT`, which would crash on a duplicate) |

### `creatives`

| column       | notes                                                                                                                                                          |
| ------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| channel      | one of `email`, `whatsapp`, `google_ads` — confirm exactly these 3 string values are used consistently across `services/copy.py`, `main.py`, and `frontend.py` |
| subject_line | nullable — WhatsApp and Google Ads copy must NOT have a subject line (see Section 4.4)                                                                         |
| body_text    | NOT NULL                                                                                                                                                       |
| tracking_url | built via `services/tracker.py`, must be unique per lead+channel combination                                                                                   |

### `clicks` and `usage_log`

- [ ] `clicks` — confirm `main.py`'s `/click` endpoint never raises even if
      the insert fails (best-effort logging, wrapped in try/except, returns
      `{"status": "logging_failed", ...}` rather than a 500)
- [ ] `usage_log` — confirm this table exists but is **not yet written to**
      anywhere in `main.py`'s request path. `services/usage_tracker.py`
      should have working `log_llm_usage()` / `log_apollo_usage()` /
      `get_campaign_cost_summary()` functions, but they are Phase 7
      scaffolding — not wired into the live pipeline yet. This is expected,
      not a bug. Don't wire it in during this verification pass unless
      explicitly asked to — that's separate follow-up work.

---

## Section 4: Phase-by-Phase Behavioral Verification

This is the core of the audit. For each phase, there's a description of what
the original doc specified, then a concrete way to verify it in this
rebuild. Use mocks (no API cost) unless you have real keys and want to
spend a few cents confirming live behavior.

### 4.1 — Phase 1: Foundation

- [ ] `.env.example` documents all required env vars: `OPENAI_API_KEY`, `APOLLO_API_KEY`, `APOLLO_CREDITS_LIMIT`, `DATABASE_PATH`, `TRACKING_BASE_URL`
- [ ] `config.py` loads these via `python-dotenv` and exposes `LLM_PRICING`, `APOLLO_CREDIT_COSTS`, `URGENCY_RUBRIC`, `load_product_catalog()`, `product_ids()`
- [ ] `data/product_catalog.json` has at least one product with `product_id`, `name`, `description`, `target_titles`, `pain_keywords`, and `seniority_angles` containing all 3 keys: `director`, `vp`, `c_suite`

```bash
python3 -c "
import json
cat = json.load(open('data/product_catalog.json'))
for p in cat:
    assert set(p['seniority_angles'].keys()) == {'director','vp','c_suite'}, p['product_id']
    assert 'target_titles' in p and 'pain_keywords' in p
print(f'{len(cat)} products validated OK')
"
```

### 4.2 — Phase 2: Article Intelligence

Original spec requirements to verify against `services/scraper.py` and `services/context.py`:

- [ ] Scraping uses `httpx` (async) + `trafilatura` (DOM-aware extraction) — not `BeautifulSoup`/`requests`/`readability-lxml` or anything else
- [ ] Paywall detection exists — `ScrapeResult.is_paywalled` is set `True` when extraction is too short AND paywall marker phrases are found in the raw HTML (check `PAYWALL_MARKERS` list in `scraper.py`)
- [ ] Context extraction uses `temperature=0.1` (deterministic) — grep to confirm:
  ```bash
  grep -n "temperature" services/context.py
  ```
  Should show `temperature=0.1`.
- [ ] Retries up to 3 times on schema validation failure — confirm `MAX_RETRIES = 3` and a retry loop in `extract_context()`
- [ ] Urgency score rubric matches exactly:
  - 9-10 = deadline within 3 months
  - 7-8 = deadline within 6 months
  - 5-6 = timeline within 12 months
  - 3-4 = timeline vague or missing
  - 1-2 = no deadline

  Confirm `config.URGENCY_RUBRIC` matches this text and is actually included in the prompt built by `services/context.py::_build_prompt`.

- [ ] Exactly 3 pain points, not "up to 3" or "at least 3" — `Field(..., min_length=3, max_length=3)`
- [ ] Product mapping is constrained to the catalog (no hallucination possible) — the `product_id` field_validator must raise `ValueError` for any id not in `config.product_ids()`

Mocked test to run:

```bash
python3 -c "
import asyncio
from unittest.mock import patch
import services.context as context

fake_response_json = '{\"entity\":\"Acme\",\"city\":\"Detroit\",\"state\":\"MI\",\"country\":\"USA\",\"catalyst\":\"raised \$50M\",\"pain_points\":[\"a\",\"b\",\"c\"],\"product_id\":\"compliance_suite\",\"urgency_score\":8}'

class FakeChoice:
    class M: content = fake_response_json
    message = M()
class FakeResp:
    choices = [FakeChoice()]

async def fake_create(*a, **kw):
    return FakeResp()

async def run():
    with patch.object(context.client.chat.completions, 'create', new=fake_create):
        ctx = await context.extract_context('some article text ' * 100)
        print(ctx.model_dump())
        assert len(ctx.pain_points) == 3
        assert ctx.location == 'Detroit, MI, USA'
        print('Phase 2 checks passed')

asyncio.run(run())
"
```

- [ ] Output shows `Phase 2 checks passed` with no exception

Also confirm hallucination protection actually works:

```bash
python3 -c "
from pydantic import ValidationError
from services.context import CampaignContext
try:
    CampaignContext(entity='X', city=None, state=None, country=None, catalyst='y',
                     pain_points=['a','b','c'], product_id='totally_made_up_product', urgency_score=5)
    print('FAIL: should have rejected unknown product_id')
except ValidationError:
    print('OK: unknown product_id correctly rejected')
"
```

### 4.3 — Phase 3: Lead Discovery (Apollo)

- [ ] Domain resolution tries Apollo org search first, falls back to DNS-pattern guessing (`_guess_domain`) only on failure — check `services/apollo.py::resolve_domain`
- [ ] Lead search uses `/mixed_people/search` (the FREE endpoint) — grep to confirm no other Apollo endpoint is used for lead fetching:
  ```bash
  grep -n "apollo.com/v1" services/apollo.py
  ```
  Should show `/organizations/search` (domain resolution) and `/mixed_people/search` (lead search) only. If `/people/match` or `/organizations/enrich` appear anywhere, that's a violation of the "free search only" design decision documented in `CLAUDE.md` — flag it, don't just fix silently, since enrichment has real cost implications the user needs to opt into.
- [ ] Verified-email-only filter present: `"contact_email_status": ["verified"]` in the search payload
- [ ] Seniority normalization maps to exactly `director` / `vp` / `c_suite` — never passes through Apollo's raw seniority string unmodified
- [ ] **Location fallback is 3-tier: city → state → no filter.** This was a gap in an earlier version of this rebuild — confirm `find_leads()` signature takes `city` and `state` as separate params (not a single flattened `location` string), and that it tries each tier in order, stopping at the first tier that returns results:
  ```bash
  grep -n "def find_leads" services/apollo.py
  ```
  Should show `city: str | None = None, state: str | None = None` as parameters, not `location: str | None = None`.
- [ ] Rate-limit handling: HTTP 429 triggers a 2-second wait and exactly one retry, both in `resolve_domain` and in the lead search path (`_search_people`)

Mocked cascade test:

```bash
python3 -c "
import asyncio
from unittest.mock import patch
import services.apollo as apollo

class FakeResp:
    def __init__(self, status_code, people): self.status_code, self._people = status_code, people
    def json(self): return {'people': self._people}

calls = []
async def fake_search(client, domain, titles, location, max_results):
    calls.append(location)
    if location in (None, 'MI'):
        return FakeResp(200, [{'id':'x','first_name':'A','last_name':'B','title':'VP','seniority':'vp','email':'a@b.com'}] if location == 'MI' else [])
    return FakeResp(200, [])

async def run():
    with patch('services.apollo._search_people', new=fake_search):
        leads = await apollo.find_leads('acme.com', ['VP'], city='Detroit', state='MI')
        assert calls == ['Detroit', 'MI'], f'wrong cascade order: {calls}'
        assert len(leads) == 1
        print('3-tier cascade verified:', calls)

asyncio.run(run())
"
```

- [ ] Output confirms `calls == ['Detroit', 'MI']` — i.e. it stopped at the state tier once results were found, and never needed the no-filter tier

### 4.4 — Phase 4: Personalized Copy Generation

- [ ] Copy is genuinely different per seniority, not `{first_name}` mail merge — confirm `services/copy.py::_prompt()` pulls a seniority-specific `angle` from `product["seniority_angles"][lead["seniority"]]` and includes it in every prompt
- [ ] Three channels generated per lead: `email`, `whatsapp`, `google_ads` — confirm `CHANNELS` list in `copy.py`
- [ ] **Character/word limits enforced, not just prompted for.** This was a gap in an earlier version — confirm actual Pydantic/function-level enforcement exists, not just instructions embedded in the LLM prompt text:
  - Email subject_line ≤ 60 chars (`Field(None, max_length=60)` on `ChannelCopy.subject_line`)
  - WhatsApp body ≤ 25 words AND has no subject line
  - Google Ads body ≤ 90 chars AND has no subject line

  Confirm `CHANNEL_LIMITS` dict and `_enforce_channel_constraints()` function exist in `services/copy.py`, and that `_generate_one()` actually calls it (with a retry) rather than just trusting the LLM's output.

  ```bash
  python3 -c "
  from pydantic import ValidationError
  from services.copy import ChannelCopy, _enforce_channel_constraints

  # too many whatsapp words should raise
  c = ChannelCopy(subject_line=None, body_text=' '.join(['w']*30))
  try:
      _enforce_channel_constraints('whatsapp', c)
      print('FAIL: 30-word whatsapp body should have been rejected')
  except ValueError:
      print('OK: whatsapp word limit enforced')

  # google ads with a subject line should raise (not allowed)
  c2 = ChannelCopy(subject_line='not allowed', body_text='short ad copy')
  try:
      _enforce_channel_constraints('google_ads', c2)
      print('FAIL: google_ads should reject a subject_line')
  except ValueError:
      print('OK: google_ads subject_line correctly rejected')
  "
  ```

  - [ ] Both checks print `OK`

- [ ] Parallel generation via `asyncio.gather`, not sequential — confirm in `generate_copy_for_lead()` and `generate_all_copy()`. Sequential generation of 12 leads × 3 channels would be a real regression (36 seconds vs. ~4 seconds per the original spec's UX requirement).
- [ ] `temperature=0.7` for copy generation (creative variation) — grep to confirm, and confirm it's distinct from the 0.1 used in context extraction
- [ ] UTM tracking URL embedded per lead+channel — confirm `services/tracker.py::build_tracking_url()` includes `cid`, `lid`, and channel-specific `utm_source`
- [ ] **Graceful individual failure**: one lead's copy generation failing must not cancel other leads, and one channel failing for a lead must not block the other channels for that same lead. Confirm both `generate_copy_for_lead` and `generate_all_copy` use `asyncio.gather(..., return_exceptions=True)` and convert exceptions into a `{"error": ...}` dict per channel/lead rather than letting them propagate.

  ```bash
  grep -n "return_exceptions=True" services/copy.py
  ```

  - [ ] Should appear twice (once per function)

### 4.5 — Phase 5: Full Pipeline + UI

- [ ] `main.py`'s `/campaign` endpoint runs the phases in order: scrape → context extraction → domain resolution → lead search → parallel copy generation → persist, and updates `campaigns.status` at each stage (see Section 3)
- [ ] Every failure branch returns HTTP 200 with a structured `status` field — **never a 500**. Confirm this by re-running the mocked failure-path tests below.
- [ ] Streamlit UI (`frontend.py`) uses `st.session_state` to hold the last result so re-rendering the page (e.g. expanding a lead row) doesn't re-call the API
- [ ] CSV download includes copy text, not just lead contact info — confirm `csv_rows` in `frontend.py` includes `subject_line`, `body_text`, `tracking_url` per channel per lead
- [ ] No raw Python stack traces are ever shown in the Streamlit UI — errors go through `st.error(...)` with a human-readable message

Full pipeline mocked test (adjust mock leads/context to taste, but confirm the shape of what comes back):

```bash
rm -f campaigns.db
python3 -c "
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
import main
from services.scraper import ScrapeResult
from services.context import CampaignContext

fake_ctx = CampaignContext(entity='Acme', city='Detroit', state='MI', country='USA',
    catalyst='raised \$50M', pain_points=['a','b','c'], product_id='compliance_suite', urgency_score=8)
fake_leads = [{'apollo_id':'a1','first_name':'Jane','last_name':'Doe','title':'VP Compliance',
    'seniority':'vp','email':'jane@acme.com','phone':None,'linkedin':None}]

async def fake_copy(leads, ctx, cid):
    return [{'lead': l, 'copy': {
        'email': {'subject_line':'Hi','body_text':'body','tracking_url':'http://t/1'},
        'whatsapp': {'body_text':'hey','tracking_url':'http://t/2'},
        'google_ads': {'body_text':'ad','tracking_url':'http://t/3'},
    }} for l in leads]

with patch('main.scrape_article', new=AsyncMock(return_value=ScrapeResult(text='x '*100, is_paywalled=False))), \
     patch('main.extract_context', new=AsyncMock(return_value=fake_ctx)), \
     patch('main.resolve_domain', new=AsyncMock(return_value='acme.com')), \
     patch('main.find_leads', new=AsyncMock(return_value=fake_leads)), \
     patch('main.generate_all_copy', new=fake_copy):
    with TestClient(main.app) as client:
        r = client.post('/campaign', json={'url':'https://example.com'})
        d = r.json()
        assert r.status_code == 200
        assert d['status'] == 'generated'
        cid = d['campaign_id']
        r2 = client.get(f'/campaigns/{cid}').json()
        assert r2['campaign']['status'] == 'generated'
        assert len(r2['leads']) == 1
        assert len(r2['creatives']) == 3
        print('Full pipeline (happy path) verified end-to-end')
"
```

- [ ] Prints `Full pipeline (happy path) verified end-to-end` with no assertion errors

Failure-path sweep (all 5 must return HTTP 200 with the listed status, never 500):

```bash
python3 -c "
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
import main
from services.scraper import ScrapeResult
from services.context import CampaignContext

fake_ctx = CampaignContext(entity='Acme', city=None, state=None, country=None, catalyst='x',
    pain_points=['a','b','c'], product_id='compliance_suite', urgency_score=5)

with TestClient(main.app) as client:
    cases = []

    with patch('main.scrape_article', new=AsyncMock(return_value=ScrapeResult(text=None, is_paywalled=True))):
        r = client.post('/campaign', json={'url':'https://x.com'}); cases.append((r.status_code, r.json()['status'], 'paywalled'))

    with patch('main.scrape_article', new=AsyncMock(return_value=ScrapeResult(text=None, is_paywalled=False, error='timeout'))):
        r = client.post('/campaign', json={'url':'https://x.com'}); cases.append((r.status_code, r.json()['status'], 'scrape_failed'))

    with patch('main.scrape_article', new=AsyncMock(return_value=ScrapeResult(text='x '*100, is_paywalled=False))), \
         patch('main.extract_context', new=AsyncMock(side_effect=ValueError('fail'))):
        r = client.post('/campaign', json={'url':'https://x.com'}); cases.append((r.status_code, r.json()['status'], 'extraction_failed'))

    with patch('main.scrape_article', new=AsyncMock(return_value=ScrapeResult(text='x '*100, is_paywalled=False))), \
         patch('main.extract_context', new=AsyncMock(return_value=fake_ctx)), \
         patch('main.resolve_domain', new=AsyncMock(return_value=None)):
        r = client.post('/campaign', json={'url':'https://x.com'}); cases.append((r.status_code, r.json()['status'], 'no_domain'))

    with patch('main.scrape_article', new=AsyncMock(return_value=ScrapeResult(text='x '*100, is_paywalled=False))), \
         patch('main.extract_context', new=AsyncMock(return_value=fake_ctx)), \
         patch('main.resolve_domain', new=AsyncMock(return_value='acme.com')), \
         patch('main.find_leads', new=AsyncMock(return_value=[])):
        r = client.post('/campaign', json={'url':'https://x.com'}); cases.append((r.status_code, r.json()['status'], 'zero_leads'))

    for code, status, expected in cases:
        ok = code == 200 and status == expected
        print(('OK ' if ok else 'FAIL '), expected, '-> got', code, status)
"
```

- [ ] All 5 lines print `OK`

### 4.6 — Phase 6: Testing

- [ ] `campaign_test.py` exists and covers all 7 original test cases: health check, scrape, analyze, full campaign, database integrity, click logging, campaigns list
- [ ] Running it against a **real, non-paywalled article URL** with real API keys should pass all 7 (edit `TEST_URL` at the top of the file first)
  ```bash
  # terminal 1
  uvicorn main:app --port 8000 &
  # terminal 2
  python3 campaign_test.py
  ```

  - [ ] `7/7 tests passed`
- [ ] .gitignore excludes `.env`, `campaigns.db`, `__pycache__`

### 4.7 — Phase 7: Cost Dashboard (Planned, Not Started)

This phase was **never completed in the original project** — don't expect
it to be fully working, and don't treat its absence from `main.py`/
`frontend.py` as a bug.

- [ ] `services/usage_tracker.py` exists with `log_llm_usage()`,
      `log_apollo_usage()`, `get_campaign_cost_summary()` — these should
      work correctly in isolation (unit-testable) but are **not called
      anywhere in `main.py`**. Confirm this with:
  ```bash
  grep -rn "usage_tracker" main.py frontend.py
  ```

  - [ ] Expect **zero matches**. If you find matches, someone already
        started wiring this in — verify it doesn't break the soft-fail
        guarantees (cost logging failure must never fail a campaign).

---

## Section 5: Known, Accepted Simplifications vs. the Original

These are intentional and were called out during the rebuild — do not
"fix" them without being asked, but do keep them in mind if user-reported
behavior seems related to one of these:

1. `data/product_catalog.json` ships with 3 example products
   (compliance_suite, workforce_platform, data_infra). The real product
   catalog from the original deployment is gone and needs to be re-entered
   by hand.
2. `TRACKING_BASE_URL` in `.env.example` is a placeholder
   (`https://track.example.com/r`). Tracking links will not actually
   resolve until this is pointed at a real redirect/analytics endpoint.
3. Phase 7 cost dashboard is scaffolded but not wired in (see 4.7).
4. No CI, no Dockerfile, no deployment config were part of the original
   summary doc, so none were reconstructed. Confirm with the user whether
   these existed before and are also worth rebuilding.

---

## Section 6: Sign-off

Only check this once every box above is checked and every command's actual
output matches its expected output — not "looks close enough."

- [ ] Section 0 — prerequisites installed
- [ ] Section 1 — file inventory matches exactly
- [ ] Section 2 — static correctness (compile + lint) clean
- [ ] Section 3 — database schema matches spec, status values constrained to the 5 valid states
- [ ] Section 4.1 — Foundation verified
- [ ] Section 4.2 — Article Intelligence verified (rubric, 3 pain points, product validation, retries, temp=0.1)
- [ ] Section 4.3 — Lead Discovery verified (free endpoint only, 3-tier location fallback, seniority normalization, rate-limit handling)
- [ ] Section 4.4 — Copy Generation verified (real per-channel limits enforced, parallel, temp=0.7, graceful per-lead/per-channel failure)
- [ ] Section 4.5 — Full pipeline + UI verified (all 5 failure paths return 200, happy path persists correctly)
- [ ] Section 4.6 — `campaign_test.py` passes 7/7 against a real article (if API keys available)
- [ ] Section 4.7 — Phase 7 confirmed as intentionally unwired
- [ ] Section 5 — known simplifications reviewed and acceptable to the user

If everything above is checked, the project is verified back to its
pre-loss state (Phases 1-6 complete and behaviorally equivalent to the
original spec, Phase 7 scaffolded but not started — same place it was
before the files were lost).

**If anything fails:** fix it, re-run the specific check that failed, and
only then continue down the list. Don't skip ahead on a failing check.
