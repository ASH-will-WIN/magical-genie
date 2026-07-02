# Handoff 2: Wire ICP Matching Into the Live Pipeline

## Context

Handoff 1 built and validated four standalone modules (`services/icp_matching/theme_extraction.py`, `prefilter.py`, `scoring.py`, plus `data/icp_config.json`) against real data. Calibration confirmed a clean score separation: positives clustered 85-95, the one clean negative scored 0, and scrape-failure cases correctly self-labeled at 50 (`insufficient_data`) rather than guessing. Thresholds are now set from real data, not placeholders:

```
score >= 70   -> approved      (auto-proceeds to lead fetch)
40 <= score < 70 -> needs_review  (surfaced in UI, human decides)
score < 40    -> rejected      (auto-dropped, reversible in UI)
```

This handoff wires those validated modules into the real `/campaign` pipeline, replacing the current single-company Apollo resolution with the Venn (theme -> candidates -> score -> approved leads) flow, and gives the user a review queue for the `needs_review` band.

---

## Step 0 (prerequisite — do this before writing pipeline code)

Confirm the actual, current Apollo API surface before wiring anything against it. Handoff 1 did not touch Apollo — it used web search + the existing scraper for test data. This handoff is the first time Apollo org search actually gets called in the new flow, so verify:

- Whether `/mixed_people/search` (currently used, free tier) supports company-level/org search with keyword + employee-count filtering, or whether org search is a separate endpoint (`/mixed_companies/search` or similar) with its own pricing/rate limits
- Actual field names returned for `industry`, `employee_count`, `domain` — Handoff 1's prefilter logic assumed these field names from Handoff 1's synthetic test dicts; confirm they match real Apollo response shape before wiring
- Current rate limits for the volume this flow implies: up to ~3 parallel keyword-cluster queries per article (per the earlier query-cluster design), each potentially returning enough candidates that Handoff 1's fix (removing the `hospital & health care` hard-exclude) is now allowed to return more raw candidates than before

If Apollo's actual schema differs meaningfully from what's assumed below, adjust the integration code accordingly — do not force-fit field names that don't exist. Report any material mismatch before proceeding rather than silently working around it.

---

## Deliverable 1: Database migration

Add two new tables. Do not modify or drop existing tables (`campaigns`, `contexts`, `leads`, `creatives`, `clicks`).

```sql
CREATE TABLE theme_extractions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL REFERENCES campaigns(id),
    theme_summary TEXT,
    affected_problem_space TEXT,   -- JSON array, stored as text
    vendor_categories_who_benefit TEXT,  -- JSON array, stored as text
    apollo_keyword_candidates TEXT,  -- JSON array, stored as text
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE icp_candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL REFERENCES campaigns(id),
    company_name TEXT,
    domain TEXT,
    apollo_industry TEXT,
    apollo_employee_count INTEGER,
    apollo_description TEXT,
    prefilter_result TEXT,      -- 'kept' | 'dropped_at_prefilter'
    prefilter_reason TEXT,
    score INTEGER,              -- nullable, null if dropped at prefilter
    score_reason TEXT,
    exclude_flag BOOLEAN,
    bucket TEXT,                -- 'approved' | 'needs_review' | 'rejected' | 'dropped_at_prefilter'
    human_override TEXT,        -- nullable: 'approved' | 'rejected', set only if a human changed the bucket
    status TEXT DEFAULT 'pending_review',  -- 'pending_review' | 'reviewed' | 'leads_fetched'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(campaign_id, domain)
);
```

Write this as a proper migration script (`migrations/002_add_icp_tables.py` or equivalent, matching whatever migration pattern — if any — already exists in `database.py`; if there's no existing migration pattern, add these as `CREATE TABLE IF NOT EXISTS` statements in the same place the existing tables are initialized).

---

## Deliverable 2: Pipeline restructure

**File:** modify `main.py`'s `/campaign` endpoint, and add `services/icp_matching/pipeline.py` to hold the new orchestration logic (keep `main.py` thin — it should call into this module, not contain the logic inline).

Replace the current single-company resolution flow (scrape -> context extract -> Apollo domain resolve for the named company -> Apollo people search for that one company) with:

1. Scrape article (unchanged, existing `scraper.py`)
2. Run existing `context.py` extraction (unchanged — this still produces the company-specific intel used later in copy-gen) AND run Handoff 1's `extract_theme()` in parallel (`asyncio.gather` both, they're independent). Persist theme extraction result to `theme_extractions`.
3. Build Apollo query clusters from `theme.apollo_keyword_candidates` + `icp_config["vertical_keywords"]` (per the 3-cluster design from earlier: article-only, ICP-only, blended). Run parallel Apollo org searches, dedupe by domain.
4. Run Handoff 1's `prefilter_candidates()` on the deduped list.
5. Run Handoff 1's `score_candidates_batch()` on everything that survives prefilter.
6. Bucket each candidate using the thresholds above. Persist every candidate (including prefilter-dropped ones — set `bucket='dropped_at_prefilter'`, `score=null`) to `icp_candidates`.
7. **Stop here for `needs_review` and `rejected` buckets — do not auto-fetch leads for them.** Only `approved` candidates proceed automatically.
8. For each `approved` candidate, run the existing per-company Apollo people-search + seniority-tier logic from the current `apollo.py` (this part is unchanged — you're now just calling it once per approved company instead of once for the single named company). Persist to `leads` as before, `campaign_id` shared across all companies in this campaign.
9. Copy generation (`copy.py`) runs unchanged per lead, but do not yet add theme-context into the copy prompt — that's explicitly deferred (see Out of Scope).

Campaign status field should now include a new intermediate state: `analyzing -> theme_extracted -> candidates_scored -> awaiting_review` (if any candidates are `needs_review` and none are `approved` yet) or `-> leads_found` (if at least one `approved` candidate exists and lead-fetch has run) `-> generated -> failed`. A campaign is not "failed" just because zero candidates were approved — `awaiting_review` with zero approved and some needs_review is a valid, non-error state, matching the existing pattern of soft-failure/partial-results.

---

## Deliverable 3: Review UI (Streamlit)

Add a new view/tab in `frontend.py` for the `needs_review` queue, scoped to the current campaign (not a global queue across all campaigns — keep it simple for now).

For each `needs_review` candidate, display: company name, domain, score, score_reason, apollo_description (so the human has context to judge). Two buttons: **Approve** and **Reject**. On click:
- Update `icp_candidates.human_override` and `status='reviewed'`
- If approved: trigger lead-fetch for that single company (reuse the same per-company fetch logic from Deliverable 2 step 8, called individually rather than batch)
- If rejected: no further action, just update status

Also show the `approved` and `rejected` (auto) lists in a read-only expandable section below, so the user can see what the system decided automatically, not just what needs a decision — this matches the existing Streamlit pattern of showing full campaign state, not hiding automated decisions.

Since the user has said they'll review this manually themselves for now, no notification/alerting system is needed — just make sure the queue is visible and doesn't require re-running the campaign to see.

---

## Deliverable 4: Cost tracking (Phase 7 tie-in)

Handoff 1's scoring pass adds a real per-candidate LLM cost that didn't exist in the current cost model (potentially 15-40+ scoring calls per campaign, depending on how many candidates survive prefilter). If `usage_log` (from Phase 7) already exists, add a distinct `operation` value for this: `"icp_theme_extraction"` and `"icp_scoring"`, logged separately from `"context_extraction"` and `"copy_generation"`. If Phase 7's table doesn't exist yet in the current codebase, create a minimal version of it now (just `campaign_id, operation, model, input_tokens, output_tokens, cost_usd, created_at`) rather than deferring cost visibility entirely — this flow meaningfully changes the cost profile of a campaign and shouldn't ship blind.

---

## Explicitly out of scope for this handoff

- Individual/physician prospect matching (still deferred from earlier discussion)
- Copy-gen changes — outreach copy does not yet reference the theme-match reasoning; that's a follow-up once this flow is live and stable
- Email sending, A/B testing, PostgreSQL migration — unchanged from original roadmap
- Cross-campaign review queue / notifications — single-campaign scoped review only for now
- Re-tuning thresholds — use 70/40 as set; only revisit if real campaign data shows they're wrong, don't preemptively adjust

## Deliverable checklist

- [ ] Step 0: Apollo API surface confirmed, any schema mismatches reported before coding
- [ ] `migrations/002_add_icp_tables.py` (or equivalent) — `theme_extractions`, `icp_candidates`
- [ ] `services/icp_matching/pipeline.py` — orchestration logic
- [ ] `main.py` `/campaign` endpoint updated to call the new pipeline
- [ ] New campaign status states wired (`theme_extracted`, `candidates_scored`, `awaiting_review`)
- [ ] Streamlit review UI: needs_review queue with approve/reject, read-only approved/rejected sections
- [ ] Approve action triggers single-company lead fetch
- [ ] `usage_log` (or minimal version) logging `icp_theme_extraction` and `icp_scoring` operations separately
- [ ] End-to-end test: run one real article through the full new flow, confirm leads land in `leads` table only for approved companies, confirm needs_review companies are visible and actionable in the UI
