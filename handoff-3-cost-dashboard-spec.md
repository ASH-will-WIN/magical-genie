# Handoff 3: Cost & Usage Dashboard (Phase 7)

## Context

The ICP pipeline now logs usage to `usage_log` across multiple operations (`icp_theme_extraction`, `icp_scoring`, `context_extraction`, `copy_generation` for OpenAI; Apollo enrichment credits via `usage_tracker.log_apollo_usage`). Right now that data goes in but is never surfaced — you can't see what a campaign actually cost without querying SQLite by hand. This handoff builds the read/aggregate layer and a Streamlit dashboard on top of the existing `usage_log` table.

This is a **read-and-display** handoff. Do not change how usage is *logged* (that's already working and verified) — only add aggregation queries and UI. The one exception: if any current LLM call site is not yet logging token counts, wire it in (see Deliverable 1 audit step).

## Current verified pricing (June 2026 — confirm against live before shipping if it's been a while)

OpenAI, per 1M tokens:
- `gpt-4o-mini`: $0.15 input / $0.60 output  (current model for all LLM calls in this app)
- `gpt-4o`: $2.50 input / $10.00 output
- `gpt-5.4-nano`: $0.20 input / $1.25 output  (cheap-task candidate, e.g. keyword/theme extraction)
- `gpt-5.4-mini`: $0.75 input / $4.50 output

Apollo:
- Email enrichment: 1 credit per email (`/people/match` with email reveal)
- Phone: 8 credits — NOT used in this app by design; dashboard should still handle it if it ever appears in the log, but don't assume it

Store these in `config.py` as a dict keyed by model name (`LLM_PRICING`), NOT hardcoded inline in the dashboard — the whole point is that when the NIM/cheaper-model swap happens, only the config changes. Include an Apollo credit-cost constant too (`APOLLO_CREDIT_COST_USD` — check your plan: Professional at $99/mo for 4,800 credits ≈ $0.0206/credit, so a per-credit dollar figure can be derived; make this a config value, not hardcoded).

---

## Deliverable 1: Usage aggregation module

**File:** `services/usage_dashboard.py`

First, **audit** every LLM call site (`context.py`, `theme_extraction.py`, `scoring.py`, `copy.py`) and confirm each one logs `input_tokens` and `output_tokens` to `usage_log`. OpenAI responses return these in `response.usage` — if any call site logs a row without real token counts (e.g. logging cost=0 or nulls), fix that call site to capture and store actual counts. Report which call sites were already correct vs. needed fixing.

Then build these query functions (pure reads against `usage_log`, all take an optional `campaign_id` — None means across all campaigns):

- `get_total_cost(campaign_id=None) -> dict` — returns `{"openai_usd": float, "apollo_credits": int, "apollo_usd": float, "total_usd": float}`
- `get_cost_by_operation(campaign_id=None) -> list[dict]` — per operation: operation name, call count, total input tokens, total output tokens, total USD
- `get_cost_by_model(campaign_id=None) -> list[dict]` — per model: call count, total tokens, total USD
- `get_cost_per_campaign() -> list[dict]` — one row per campaign: campaign_id, article url (join to `campaigns`), total USD, apollo credits, lead count — sorted most expensive first
- `get_apollo_credit_status() -> dict` — total credits used this billing period vs. the configured monthly allowance (`APOLLO_CREDITS_LIMIT` env var, 4800 for current plan), returns used/limit/remaining/pct

Cost is computed at query time from token counts × `LLM_PRICING`, not read from a stored cost column — this way if pricing config changes, historical costs recompute correctly rather than being frozen at old rates. (If `usage_log` already stores a computed `cost_usd`, ignore it for display and recompute from tokens; leave the column alone.)

---

## Deliverable 2: Streamlit dashboard

Add a new top-level tab/page in `frontend.py` — "💰 Usage & Cost" — separate from the campaign-run view.

**Section A — Account-wide summary (across all campaigns):**
- Metric cards: total OpenAI spend, total Apollo credits used, total estimated USD, number of campaigns run
- Apollo credit gauge: a progress bar showing credits used / monthly limit, with remaining count and % — color shift as it approaches the limit (this is the "don't get surprised by an overage" view your boss cares about). Reuse the `MAX_LEADS_PER_CAMPAIGN` testing-cap awareness here if useful — note in the UI if a testing cap is currently active, since that suppresses real spend.
- Bar chart: cost by operation (theme extraction vs scoring vs context vs copy-gen) — this directly answers "which stage is expensive" and validates the NIM-swap decision
- Bar chart: cost by model (will show only gpt-4o-mini today, but ready for when models are mixed)

**Section B — Per-campaign breakdown:**
- A table from `get_cost_per_campaign()`: campaign, article (truncated url), total cost, Apollo credits, leads found, and a derived **cost-per-lead** column (total_usd / lead_count, guarding divide-by-zero → show "—" for zero-lead campaigns)
- Sortable/most-expensive-first so you can spot outlier campaigns

**Section C — Current campaign inline (optional but recommended):**
- On the main campaign-run view, after a campaign completes, show a small inline cost summary for *that* campaign (total USD, Apollo credits used, cost per lead) so the user sees the cost of what they just ran without switching tabs. This is the real-time-visibility ask from earlier.

Keep charts simple — Streamlit's built-in `st.bar_chart` / `st.metric` / `st.progress` are fine, no need for a heavy charting lib.

---

## Explicitly out of scope

- No changes to how usage is logged, except fixing any call site found not logging real token counts (Deliverable 1 audit)
- No budget auto-shutoff / hard spending limits (the testing caps from the previous handoff already handle spend control; this dashboard is visibility, not enforcement)
- No actual model-swapping to NIM/cheaper models — this handoff makes the *cost of that decision visible*; the swap itself is a separate follow-up
- No historical/time-series charts (cost over time) — current data volume doesn't justify it yet; per-campaign and per-operation breakdowns are enough

## Deliverable checklist

- [ ] `config.py`: `LLM_PRICING` dict (multi-model), `APOLLO_CREDIT_COST_USD`, `APOLLO_CREDITS_LIMIT`
- [ ] Deliverable 1 audit: report which LLM call sites logged real token counts vs. needed fixing
- [ ] `services/usage_dashboard.py`: five aggregation functions, cost computed from tokens at query time
- [ ] `frontend.py`: "Usage & Cost" tab — account summary, Apollo gauge, cost-by-operation + cost-by-model charts, per-campaign table with cost-per-lead
- [ ] Inline per-campaign cost summary on the campaign-run view
- [ ] Verify live: run a fresh campaign (with a testing cap set), then open the dashboard and confirm the numbers match what the terminal logged for that run — token counts, Apollo credits, and total cost should reconcile
