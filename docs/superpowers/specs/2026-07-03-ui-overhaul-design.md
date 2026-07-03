# Magical Genie UI Overhaul — Design

Source requirements: `ui-overhaul-prompt.md` (repo root). This document resolves
the implementation-level questions that doc left open, using the installed
Streamlit version (1.58) and its bundled `developing-with-streamlit` reference
docs. UI/UX only — no pipeline/business-logic changes beyond the two narrow
exceptions below.

## Visual identity

- **Theme via `.streamlit/config.toml`** (native support, not CSS):
  - `base = "dark"`, `backgroundColor = "#12151C"`, `secondaryBackgroundColor = "#1B2029"`
  - `primaryColor = "#E8AA4C"` (signal amber), `textColor = "#F2F3F5"`
  - `greenColor = "#4FA88A"` (approved), `redColor = "#C4634B"` (rejected) — used via `st.badge`/status text, not as literal error semantics
  - `font = "Inter:<google fonts URL>"`, `codeFont = "'JetBrains Mono':<google fonts URL>"`
  - `linkUnderline = false`, `baseRadius = "8px"`, `showWidgetBorder = true`
- **Custom CSS** (`styles.py`, one `st.html(...)` call from the entrypoint, scoped via `key=` → `.st-key-*` selectors only): signal-strength bars, the Venn SVG, and monospace formatting for values `codeFont` doesn't reach (e.g. `st.metric` values/deltas).
- **Signal-strength bar**: filled horizontal bar 0-100, discrete coloring by bucket (approved=green token, needs_review=amber/primary, rejected/dropped_at_prefilter=red token). Implemented as a small HTML snippet with a `key`-scoped class.
- **Venn diagram**: inline SVG, two overlapping circles (Article Theme, Reinvent ICP), region labels showing `search_stats.cluster_counts` (article-only, icp-only, blended) — data already returned by `/campaign` and `build_and_score_candidates`.

## Structure

```
streamlit_app.py              # entrypoint: st.navigation (sidebar), shared init
app_pages/
    dashboard.py
    new_campaign.py
    review_queue.py
    history.py
    settings.py
    usage.py
styles.py                     # CSS_HTML constant + component snippet helpers (signal bar, venn svg)
api_client.py                 # thin wrapper over existing requests calls to FastAPI
```

`app_pages/` (not `pages/`) to avoid colliding with Streamlit's legacy auto-discovery, per the bundled multipage-apps reference. `frontend.py` is retired; its logic is redistributed across `new_campaign.py` (campaign run + review UI) and `usage.py` (cost dashboard), both already-working code lifted as-is and restyled.

## Backend touches (both additive/config-only, not pipeline logic)

1. **`data/settings.json`** — new file, source of truth for `approve_threshold` (70), `review_threshold` (40), `max_lead_fetch_companies`, `max_leads_per_campaign`. `config.py` gains `load_settings()`/`save_settings()`; `MAX_LEAD_FETCH_COMPANIES`/`MAX_LEADS_PER_CAMPAIGN` become properties read from it (falling back to existing env vars only if the file doesn't exist yet, for a clean first run). `services/icp_matching/pipeline.py`'s `APPROVE_THRESHOLD`/`REVIEW_THRESHOLD` module constants become a call to `load_settings()` at the point of use in `_bucket()`. No change to scoring/matching logic itself.
2. **`GET /health/keys`** — new read-only FastAPI endpoint returning `{"openai": bool, "apollo": bool}` (presence-only, never the key value). Used by the Settings page's connection-status panel.

Everything else (ICP config edit, pricing display, cross-campaign review queue, history drill-down) reads/writes existing files and existing endpoints — no other backend changes.

## Page specs

### 1. Dashboard (home)
Cards: campaigns run (total, this week — computed client-side from `GET /campaigns`), leads found (total, sum from campaign detail calls — see perf note below), pending review count (badge styled with `redColor`/amber if >0), spend this month vs Apollo budget (`get_total_cost()`, `get_apollo_credit_status()`, already built). "New Campaign" URL input + button at top navigates to the New Campaign page (`st.session_state` carries the pasted URL over).

*Perf note:* computing "leads found (total)" and "pending review count" needs per-campaign detail fetches. Cap this to the last N (e.g. 50) campaigns for the dashboard summary and note in an `st.caption` if truncated — avoids an unbounded fan-out of requests as campaign history grows. Full totals remain available on Usage & Cost (`get_total_cost()` is already a single aggregate DB query, unaffected).

### 2. New Campaign
Existing URL input / manual-paste / run flow, restyled. Live progress: POST `/campaign` is fired in a background `threading.Thread`; the main script polls `GET /campaigns/{id}` every ~1s via a placeholder + `st.rerun()` loop, mapping `status` (`analyzing → theme_extracted → candidates_scored → awaiting_review|leads_found → generated|failed`) to a stage checklist. Once `context` + `search_stats` are available, render the Venn visual. Rest of the result rendering (candidates, needs_review approve/reject, leads/copy tabs, CSV export, per-campaign cost) is the existing `frontend.py` logic, restyled with signal bars replacing bare score numbers.

If a testing cap is active (`MAX_LEAD_FETCH_COMPANIES`/`MAX_LEADS_PER_CAMPAIGN` from `settings.json`), show a persistent small badge on this page (not just after a run finishes).

### 3. Review Queue
`GET /campaigns` then `GET /campaigns/{id}` for each (bounded to recent N same as Dashboard, or all if the list is small — no pagination needed at current expected scale) to collect `needs_review` candidates minus `human_override`. Table/card view: company, domain, signal bar, reason, `apollo_description`, campaign link (sets `st.session_state` target and switches to History detail via `st.switch_page`). Approve/Reject call the existing endpoints. Filter/sort controls: by campaign, score, age (`created_at`).

### 4. Campaign History
Table via `GET /campaigns` (date, url, status) joined client-side with per-campaign cost (`get_cost_per_campaign()`) and lead/candidate counts (from detail fetch, same bounded-N approach). Sortable via `st.dataframe` column sorting; searchable via a text filter on URL/title. Row selection (or a "view" button per row) drills into a detail view for that campaign: full `GET /campaigns/{id}` payload — context, Venn visual (from stored `theme_extractions` + candidate cluster info), full candidate list with signal bars/reasons, leads + generated copy per channel (reuse the existing per-lead expander/tabs pattern from `frontend.py`), and that campaign's cost breakdown (`get_total_cost(campaign_id)`).

### 5. Settings
- **ICP config editor**: form-backed editor for `data/icp_config.json` — add/remove list items for `company_type.include/exclude`, `size_band` min/max/preferred/soft_ceiling, `vertical_keywords`, `technology_signal_keywords`, `buying_trigger_keywords`, `hard_exclude_industries`. Save writes the file via `config.load_icp_config`'s path (`ICP_CONFIG_PATH`), full-file rewrite (no partial-merge risk since the whole form round-trips the object). Raw JSON shown in a collapsed `st.expander`.
- **Thresholds**: number inputs for approve/review cutoffs, backed by `data/settings.json`, with a labeled number-line visual (0-100, three colored bands) built via the same CSS approach as the signal bar.
- **Testing caps**: number inputs (blank = unlimited) for `MAX_LEAD_FETCH_COMPANIES`/`MAX_LEADS_PER_CAMPAIGN`, same `settings.json` store. Current values always visible here and referenced as a small badge on Dashboard/New Campaign when active.
- **Pricing config**: display `LLM_PRICING` and `APOLLO_CREDIT_COST_USD` from `config.py`. Editable — but since these are Python module constants (not currently in a JSON file), they fold into `data/settings.json` too (`llm_pricing`, `apollo_credit_cost_usd`), with `usage_dashboard.py`'s cost calculations reading from `load_settings()` instead of the hardcoded dict. This is the same category of change as #1 above (config plumbing, not business logic) — flagged explicitly since it touches `usage_dashboard.py` too.
- **Connection status**: calls `GET /health/keys`; shows two badges (OpenAI/Apollo) green/red based on presence.

### 6. Usage & Cost
Existing `usage_dashboard.py`-backed content, restyled: signal-bar style gauge for Apollo credit usage (replacing `st.progress`), monospace for all cost/credit figures (native via `codeFont`, no extra work), everything else unchanged.

## Empty states & error voice

- Review Queue, empty: short first-person statement ("Nothing needs review right now — all recent candidates were auto-approved or auto-rejected.") not a bare "no data".
- Campaign History, empty (no campaigns yet): points at New Campaign page.
- Errors (scrape failure, Apollo rate-limit, campaign failed): plain-language statement of what happened + what it means, reusing/extending the existing status-message mapping already in `frontend.py` (`scrape_failed`, `extraction_failed`, `no_domain`, `zero_leads`, `no_candidates`, `awaiting_review`) — no raw stack traces, ever.

## Out of scope (unchanged from prompt)

No other backend/pipeline changes, no new campaign features, no framework migration.
