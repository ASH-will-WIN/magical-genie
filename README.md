# Magical Genie 🧞

News-triggered B2B micro-campaign engine. Paste a news article URL about a
company → get verified leads at that company + genuinely personalized
outreach copy (email, WhatsApp, Google Ads), tailored per person's seniority.

> Rebuilt from a project summary after the original local files were lost.
> See `CLAUDE.md` for the full design-decision rationale — read it before
> changing core behavior (urgency rubric, failure handling, Apollo endpoint
> choice, etc.), those aren't arbitrary.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # then fill in OPENAI_API_KEY and APOLLO_API_KEY
python database.py     # initializes campaigns.db
```

## Run

```bash
# Terminal 1
uvicorn main:app --reload --port 8000

# Terminal 2
streamlit run frontend.py
```

- UI: http://localhost:8501
- API: http://localhost:8000 (docs at /docs)

## Test

```bash
python campaign_test.py
```
Edit `TEST_URL` in that file to a real, non-paywalled article first.

## File structure

```
magical-genie/
├── main.py                  # FastAPI backend, all endpoints
├── frontend.py               # Streamlit UI
├── database.py                # SQLite schema + connection
├── config.py                   # Env vars, pricing, product catalog loader
├── campaign_test.py             # End-to-end test suite
├── services/
│   ├── scraper.py               # Article extraction + paywall detection
│   ├── context.py                # LLM intelligence extraction (temp=0.1)
│   ├── apollo.py                  # Domain resolution + lead search
│   ├── copy.py                     # Per-person copy generation (temp=0.7, parallel)
│   ├── tracker.py                   # UTM tracking link builder
│   └── usage_tracker.py              # Phase 7 cost logging (scaffolded, not wired in)
├── data/product_catalog.json          # Products, target titles, seniority angles
├── .env.example
└── campaigns.db (auto-created)
```

## Cost per campaign (approx)
- OpenAI context extraction: ~$0.0004
- OpenAI copy generation (12 leads): ~$0.006
- Apollo lead search: $0 (using free `/mixed_people/search`)
- **Total: ~$0.006** — jumps to $0.60-$6.00 only if enrichment endpoints are
  enabled (not currently wired in — see CLAUDE.md before adding this).

## Status
Phases 1-6 complete and working. Phase 7 (cost dashboard) is scaffolded in
`services/usage_tracker.py` and the `usage_log` table but not yet called from
`main.py` or surfaced in the UI — that's the natural next task.
