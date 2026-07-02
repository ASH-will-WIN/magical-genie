# Magical Genie — Project Memory

## What this is
A news-triggered B2B micro-campaign engine. User pastes a news article URL about
a company -> system extracts sales intelligence -> maps to a product -> finds
verified leads at that company via Apollo.io -> generates personalized outreach
copy (email/WhatsApp/Google Ads) per lead, tailored to their seniority level.

This project was previously built and working end-to-end (Phases 1-6 complete,
Phase 7 cost dashboard planned but not started). The local files were lost.
This folder is a rebuild from the last known project summary. Code here is a
functional scaffold reconstructed from that summary — verify behavior against
the "Known Limitations" and "Key Decisions" sections below before trusting it
blindly, and treat this as ~80% of the way back to where it was.

## Non-negotiable design decisions (do not silently change these)
1. **Personalization is real, not mail merge.** Copy generation must use
   urgency score + pain points + seniority to produce fundamentally different
   messaging per person, not just {first_name} substitution.
   - Director angle: execution speed, timelines, not looking bad to VP
   - VP angle: strategic risk, vendor consolidation, budget optics
   - C-Suite angle: board liability, compliance readiness, cost savings
2. **Failure is always soft.** Nothing should throw a 500 or crash the UI.
   - Domain resolution fails -> return partial result (0 leads, context still returned)
   - One lead's copy generation fails -> others still complete (asyncio.gather with
     return_exceptions, filter failures)
   - Click logging fails -> campaign still returns successfully (best-effort only)
   - Unknown LLM model in cost tracking -> log warning, cost=$0, continue
3. **Product catalog is explicit, not inferred.** Products live in
   `data/product_catalog.json`. The LLM can only choose a product_id that exists
   in that file — validate with Pydantic, never let it hallucinate a product.
4. **Urgency score rubric (fixed, do not let the LLM freelance this):**
   - 9-10 = deadline within 3 months
   - 7-8 = deadline within 6 months
   - 5-6 = timeline within 12 months
   - 3-4 = timeline vague or missing
   - 1-2 = no deadline
5. **Exactly 3 pain points per article.** Not 2, not 5.
6. **Apollo usage:** `/mixed_people/search` is FREE — use this for lead
   discovery. Only `/people/match` and `/organizations/enrich` cost credits.
   Do NOT call enrichment endpoints unless the user explicitly asks for it —
   phone enrichment alone can burn 9,600+ credits/month at 100 campaigns
   (8 credits/phone), way past a typical 4,000/month allowance. Default to
   email-only if enrichment is ever turned on.
7. **Temperatures:** context extraction = 0.1 (deterministic), copy generation
   = 0.7 (creative variation).
8. **Copy generation is parallel** via `asyncio.gather`, not sequential —
   12 leads should take ~4s, not ~36s. This is a hard UX requirement.
9. **SQLite is intentional for MVP.** Don't "upgrade" to Postgres unless asked
   — that's a deliberate Phase 11, not a default.
10. **No built-in email sending.** Export-only via CSV is intentional (GDPR/
    CAN-SPAM liability avoidance), not a missing feature.

## Architecture
FastAPI backend (`main.py`) orchestrates: Scraper -> Context AI -> Apollo Domain
Resolver -> Apollo Lead Finder -> Copy AI (parallel) -> Database. Streamlit
(`frontend.py`) is the UI, calling the FastAPI endpoint and holding session state
so it doesn't re-call the API on every UI interaction.

```
services/
  scraper.py         # httpx + trafilatura article extraction, paywall detection
  context.py         # OpenAI gpt-4o-mini structured-output intel extraction
  apollo.py          # domain resolution (org search -> DNS fallback) + lead search
  copy.py            # per-person, per-channel copy generation (parallel)
  tracker.py         # UTM tracking URL builder
  usage_tracker.py   # Phase 7 cost logging (LLM + Apollo) — scaffolded, not wired in yet
```

## Status vs. before
- ✅ Phases 1-6 scaffolded fresh in this rebuild (see file list below)
- 🔄 Phase 7 (cost dashboard) — `usage_tracker.py` and `usage_log` table are
  present as scaffolding but not yet wired into `main.py`'s request flow or
  surfaced in the Streamlit UI. That's the next real task.
- ❌ Everything in the doc's Phase 8+ (email sending, A/B testing, Postgres
  migration, admin UI, multi-LLM) — intentionally not started.

## What to do first when resuming work
1. Fill in `.env` from `.env.example` (OPENAI_API_KEY, APOLLO_API_KEY).
2. `pip install -r requirements.txt`
3. `python database.py` to init `campaigns.db` (or it auto-inits on first run).
4. `uvicorn main:app --reload --port 8000` + `streamlit run frontend.py` in a
   second terminal.
5. Run `python campaign_test.py` against a real article URL to confirm the
   pipeline is intact end-to-end before building anything new on top of it.
6. Then pick up Phase 7 (wire `usage_tracker.py` into the live request path).

## Known limitations (carried over, still true until fixed)
- Domain resolution success ~95% (DNS guessing is imperfect) — no manual
  override in UI yet.
- Copy quality varies at temp=0.7 by design; if it degrades, lower temp or
  tighten the prompt before reaching for a bigger model.
- Product catalog requires a restart to change (no hot-reload).
- Only top-of-funnel click tracking; no click-to-conversion.

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
