# Graph Report - ui-overhaul  (2026-07-03)

## Corpus Check
- 39 files · ~33,513 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 370 nodes · 582 edges · 60 communities (24 shown, 36 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 12 edges (avg confidence: 0.85)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `d8bfddc5`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- [[_COMMUNITY_Campaign Pipeline Orchestration|Campaign Pipeline Orchestration]]
- [[_COMMUNITY_Outreach Copy Generation|Outreach Copy Generation]]
- [[_COMMUNITY_ICP Prefilter & Calibration Testing|ICP Prefilter & Calibration Testing]]
- [[_COMMUNITY_Apollo Lead Search & Enrichment|Apollo Lead Search & Enrichment]]
- [[_COMMUNITY_ICP Scoring & Usage Tracking|ICP Scoring & Usage Tracking]]
- [[_COMMUNITY_Core App Files & Dependencies|Core App Files & Dependencies]]
- [[_COMMUNITY_Article Context Extraction|Article Context Extraction]]
- [[_COMMUNITY_Project Design Principles (CLAUDE.md)|Project Design Principles (CLAUDE.md)]]
- [[_COMMUNITY_Campaign Test Suite|Campaign Test Suite]]
- [[_COMMUNITY_Handoff 2 ICP Pipeline Wiring Spec|Handoff 2: ICP Pipeline Wiring Spec]]
- [[_COMMUNITY_Handoff 1 ICP Scoring Modules|Handoff 1: ICP Scoring Modules]]
- [[_COMMUNITY_Testing & Soft-Failure Design|Testing & Soft-Failure Design]]
- [[_COMMUNITY_Product Catalog & Channel Config|Product Catalog & Channel Config]]
- [[_COMMUNITY_main.py|main.py]]
- [[_COMMUNITY_ICP Matching Package Init|ICP Matching Package Init]]
- [[_COMMUNITY_Services Package Init|Services Package Init]]
- [[_COMMUNITY_Handoff 1 ICP Theme-Matching & Scoring Modules (Standalone)|Handoff 1: ICP Theme-Matching & Scoring Modules (Standalone)]]
- [[_COMMUNITY_Handoff 2 Wire ICP Matching Into the Live Pipeline|Handoff 2: Wire ICP Matching Into the Live Pipeline]]
- [[_COMMUNITY_Magical Genie — Project Memory|Magical Genie — Project Memory]]
- [[_COMMUNITY_Handoff 3 Cost & Usage Dashboard (Phase 7)|Handoff 3: Cost & Usage Dashboard (Phase 7)]]
- [[_COMMUNITY_Magical Genie 🧞|Magical Genie 🧞]]
- [[_COMMUNITY_UI Overhaul Implementation Progress|UI Overhaul Implementation Progress]]
- [[_COMMUNITY_No built-in email sending — export-only via CSV|No built-in email sending — export-only via CSV]]
- [[_COMMUNITY_Copy generation is parallel via asyncio.gather|Copy generation is parallel via asyncio.gather]]
- [[_COMMUNITY_Personalization is real, not mail merge|Personalization is real, not mail merge]]
- [[_COMMUNITY_Phase 7 cost dashboard (scaffolded, not wired in)|Phase 7 cost dashboard (scaffolded, not wired in)]]
- [[_COMMUNITY_Product catalog is explicit, not inferred|Product catalog is explicit, not inferred]]
- [[_COMMUNITY_Failure is always soft (no 500s, partial results)|Failure is always soft (no 500s, partial results)]]
- [[_COMMUNITY_SQLite is intentional for MVP (no Postgres upgrade)|SQLite is intentional for MVP (no Postgres upgrade)]]
- [[_COMMUNITY_Temperatures context=0.1, copy=0.7|Temperatures: context=0.1, copy=0.7]]
- [[_COMMUNITY_Exactly 3 pain points per article|Exactly 3 pain points per article]]
- [[_COMMUNITY_Urgency score rubric (1-10 fixed)|Urgency score rubric (1-10 fixed)]]
- [[_COMMUNITY_dataproduct_catalog.json — products, target titles, seniority angles|data/product_catalog.json — products, target titles, seniority angles]]
- [[_COMMUNITY_database.py — SQLite schema + connection|database.py — SQLite schema + connection]]
- [[_COMMUNITY_Venn diagram ICP strategy (theme - candidates - score - leads)|Venn diagram ICP strategy (theme -> candidates -> score -> leads)]]
- [[_COMMUNITY_Score bucket thresholds =70 approved, 40-69 needs_review, 40 rejected|Score bucket thresholds: >=70 approved, 40-69 needs_review, <40 rejected]]
- [[_COMMUNITY_Phase 7 cost tracking tie-in (icp_theme_extraction, icp_scoring operations)|Phase 7 cost tracking tie-in (icp_theme_extraction, icp_scoring operations)]]
- [[_COMMUNITY_icp_candidates table|icp_candidates table]]
- [[_COMMUNITY_ICP matching wired into campaign pipeline|ICP matching wired into /campaign pipeline]]
- [[_COMMUNITY_Streamlit needs_review queue with approvereject|Streamlit needs_review queue with approve/reject]]
- [[_COMMUNITY_theme_extractions table|theme_extractions table]]
- [[_COMMUNITY_Handoff 1 ICP Theme-Matching & Scoring Modules|Handoff 1: ICP Theme-Matching & Scoring Modules]]
- [[_COMMUNITY_migrations002_add_icp_tables.py — theme_extractions, icp_candidates|migrations/002_add_icp_tables.py — theme_extractions, icp_candidates]]
- [[_COMMUNITY_README.md — Magical Genie|README.md — Magical Genie]]
- [[_COMMUNITY_servicesapollo.py — domain resolution + lead search|services/apollo.py — domain resolution + lead search]]
- [[_COMMUNITY_servicesicp_matchingpipeline.py — new orchestration logic|services/icp_matching/pipeline.py — new orchestration logic]]
- [[_COMMUNITY_servicesicp_matchingtest_calibration.py — labeled test harness|services/icp_matching/test_calibration.py — labeled test harness]]
- [[_COMMUNITY_servicestracker.py — UTM tracking link builder|services/tracker.py — UTM tracking link builder]]
- [[_COMMUNITY_servicesusage_tracker.py — Phase 7 cost logging (scaffolded)|services/usage_tracker.py — Phase 7 cost logging (scaffolded)]]
- [[_COMMUNITY_Per-channel copy limits enforced in code (email subject=60, whatsapp=25 words, google_ads=90 chars)|Per-channel copy limits enforced in code (email subject<=60, whatsapp<=25 words, google_ads<=90 chars)]]
- [[_COMMUNITY_Known accepted simplifications vs. original (placeholder catalog, tracking URL, unwired Phase 7, no CIDocker)|Known accepted simplifications vs. original (placeholder catalog, tracking URL, unwired Phase 7, no CI/Docker)]]
- [[_COMMUNITY_5-state campaign status machine (analyzingcontext_extractedleads_foundgeneratedfailed)|5-state campaign status machine (analyzing/context_extracted/leads_found/generated/failed)]]
- [[_COMMUNITY_3-tier location fallback (city - state - no filter) for find_leads|3-tier location fallback (city -> state -> no filter) for find_leads]]
- [[_COMMUNITY_test_styles.py|test_styles.py]]

## God Nodes (most connected - your core abstractions)
1. `get_conn()` - 29 edges
2. `File Structure` - 16 edges
3. `build_and_score_candidates()` - 15 edges
4. `log()` - 15 edges
5. `log_llm_usage()` - 14 edges
6. `now_iso()` - 12 edges
7. `scrape_article()` - 11 edges
8. `approve_candidate()` - 10 edges
9. `Handoff 1: ICP Theme-Matching & Scoring Modules (Standalone)` - 10 edges
10. `load_settings()` - 9 edges

## Surprising Connections (you probably didn't know these)
- `test_health_keys_never_returns_key_value()` --indirect_call--> `main()`  [INFERRED]
  tests/test_health_endpoint.py → services/icp_matching/test_calibration.py
- `test_health_keys_reports_missing_when_unset()` --indirect_call--> `main()`  [INFERRED]
  tests/test_health_endpoint.py → services/icp_matching/test_calibration.py
- `test_health_keys_reports_present_when_both_set()` --indirect_call--> `main()`  [INFERRED]
  tests/test_health_endpoint.py → services/icp_matching/test_calibration.py
- `log_llm_usage()` --calls--> `get_llm_pricing()`  [EXTRACTED]
  services/usage_tracker.py → config.py
- `log_apollo_usage()` --calls--> `get_apollo_credit_costs()`  [EXTRACTED]
  services/usage_tracker.py → config.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Non-negotiable design decisions (CLAUDE.md)** — claude_md_personalization_design, claude_md_soft_failure_design, claude_md_product_catalog_explicit, claude_md_apollo_free_endpoint_policy, claude_md_sqlite_decision, claude_md_no_email_sending_decision [EXTRACTED 1.00]
- **ICP Venn-diagram standalone module set (Handoff 1)** — services_icp_matching_theme_extraction_py, services_icp_matching_prefilter_py, services_icp_matching_scoring_py, services_icp_matching_test_calibration_py, data_icp_config_json [EXTRACTED 1.00]
- **Live pipeline wiring deliverables (Handoff 2)** — services_icp_matching_pipeline_py, migrations_002_add_icp_tables_py, handoff2_bucket_thresholds, handoff2_review_ui, handoff2_cost_tracking_tie_in [EXTRACTED 1.00]

## Communities (60 total, 36 thin omitted)

### Community 0 - "Campaign Pipeline Orchestration"
Cohesion: 0.14
Nodes (24): AsyncClient, Response, find_leads(), _guess_domain(), _headers(), _lead_from_matched_person(), normalize_seniority(), Apollo.io integration: - Domain resolution: org search (primary) -> DNS pattern (+16 more)

### Community 1 - "Outreach Copy Generation"
Cohesion: 0.16
Nodes (16): BaseModel, load_product_catalog(), ChannelCopy, _enforce_channel_constraints(), generate_all_copy(), generate_copy_for_lead(), _generate_one(), _product_for() (+8 more)

### Community 2 - "ICP Prefilter & Calibration Testing"
Cohesion: 0.10
Nodes (33): load_icp_config(), build_and_score_candidates(), _fetch_description(), _prefilter_drop_reason(), Theme-driven, multi-company ICP matching pipeline (Handoff 2).  Replaces the o, Re-derives a human-readable reason for why prefilter_candidates()     dropped t, Runs theme extraction -> Apollo keyword search -> prefilter -> scoring     -> b, prefilter_candidates() (+25 more)

### Community 3 - "Apollo Lead Search & Enrichment"
Cohesion: 0.25
Nodes (9): _bucket(), _campaign_lead_fetch_counts(), _lead_fetch_cap_reason(), Returns (companies_fetched, total_leads) for this campaign so far.     companie, Returns a human-readable reason string if either testing cap     (max_lead_fetc, test_bucket_respects_custom_threshold_from_settings(), test_bucket_uses_default_thresholds(), test_lead_fetch_cap_reason_fires_from_settings() (+1 more)

### Community 4 - "ICP Scoring & Usage Tracking"
Cohesion: 0.14
Nodes (23): Any, get_apollo_credit_cost_usd(), get_apollo_credit_costs(), get_approve_threshold(), get_llm_pricing(), get_max_lead_fetch_companies(), get_max_leads_per_campaign(), get_review_threshold() (+15 more)

### Community 5 - "Core App Files & Dependencies"
Cohesion: 0.21
Nodes (13): frontend.py — Streamlit UI, main.py — FastAPI backend, requirements.txt — Magical Genie dependencies, fastapi==0.115.0, httpx==0.27.2, openai==1.51.0, pandas==2.2.3, pydantic==2.9.2 (+5 more)

### Community 6 - "Article Context Extraction"
Cohesion: 0.09
Nodes (21): 4.1 — Phase 1: Foundation, 4.2 — Phase 2: Article Intelligence, 4.3 — Phase 3: Lead Discovery (Apollo), 4.4 — Phase 4: Personalized Copy Generation, 4.5 — Phase 5: Full Pipeline + UI, 4.6 — Phase 6: Testing, 4.7 — Phase 7: Cost Dashboard (Planned, Not Started), `campaigns` (+13 more)

### Community 8 - "Campaign Test Suite"
Cohesion: 0.36
Nodes (9): check(), End-to-end test suite. Run with: python campaign_test.py Requires uvicorn main:, test_analyze(), test_click_logging(), test_database_integrity(), test_full_campaign(), test_health(), test_list_campaigns() (+1 more)

### Community 13 - "main.py"
Cohesion: 0.09
Nodes (40): product_ids(), Connection, get_conn(), init_db(), _migrate(), now_iso(), SQLite schema + connection management. Zero-DevOps choice for MVP. Migrate to P, Additive, idempotent column migrations for DBs created before a schema     chan (+32 more)

### Community 14 - "ICP Matching Package Init"
Cohesion: 0.10
Nodes (19): File Structure, Global Constraints, Magical Genie UI Overhaul Implementation Plan, Self-Review Notes, Task 10: New Campaign page (migrated logic + live progress + Venn), Task 11: Review Queue page (cross-campaign), Task 12: Campaign History page (archive + drill-down), Task 13: Settings page (+11 more)

### Community 15 - "Services Package Init"
Cohesion: 0.14
Nodes (13): 1. Dashboard (home), 2. New Campaign, 3. Review Queue, 4. Campaign History, 5. Settings, 6. Usage & Cost, Backend touches (both additive/config-only, not pipeline logic), Empty states & error voice (+5 more)

### Community 16 - "Handoff 1: ICP Theme-Matching & Scoring Modules (Standalone)"
Cohesion: 0.18
Nodes (10): Context, Deliverable 1: ICP config, Deliverable 2: Theme extraction module, Deliverable 3: Pre-filter module, Deliverable 4: Scoring module, Deliverable 5: Test harness (this is the actual point of the handoff), Deliverable checklist, Explicitly out of scope for this handoff (+2 more)

### Community 17 - "Handoff 2: Wire ICP Matching Into the Live Pipeline"
Cohesion: 0.20
Nodes (9): Context, Deliverable 1: Database migration, Deliverable 2: Pipeline restructure, Deliverable 3: Review UI (Streamlit), Deliverable 4: Cost tracking (Phase 7 tie-in), Deliverable checklist, Explicitly out of scope for this handoff, Handoff 2: Wire ICP Matching Into the Live Pipeline (+1 more)

### Community 18 - "Magical Genie — Project Memory"
Cohesion: 0.22
Nodes (8): Architecture, graphify (for Claude, not the user — an internal research step), Known limitations (carried over, still true until fixed), Magical Genie — Project Memory, Non-negotiable design decisions (do not silently change these), Status vs. before, What this is, What to do first when resuming work

### Community 19 - "Handoff 3: Cost & Usage Dashboard (Phase 7)"
Cohesion: 0.25
Nodes (7): Context, Current verified pricing (June 2026 — confirm against live before shipping if it's been a while), Deliverable 1: Usage aggregation module, Deliverable 2: Streamlit dashboard, Deliverable checklist, Explicitly out of scope, Handoff 3: Cost & Usage Dashboard (Phase 7)

### Community 20 - "Magical Genie 🧞"
Cohesion: 0.25
Nodes (7): Cost per campaign (approx), File structure, Magical Genie 🧞, Run, Setup, Status, Test

### Community 21 - "UI Overhaul Implementation Progress"
Cohesion: 0.40
Nodes (4): Completed Tasks, In Progress, Remaining, UI Overhaul Implementation Progress

### Community 59 - "test_styles.py"
Cohesion: 0.19
Nodes (14): inject_base_styles(), mono(), Central CSS + small visual-component helpers for the signal-detection theme. Col, Call once, from the app entrypoint, before any page renders., A filled horizontal 0-100 signal-strength bar, colored by bucket., Two overlapping circles: Article Theme (left) ∩ Reinvent ICP (right),     labele, Wrap an ad-hoc numeric/data value in the monospace class, for use     inside st., signal_bar_html() (+6 more)

## Knowledge Gaps
- **114 isolated node(s):** `Completed Tasks`, `In Progress`, `Remaining`, `What this is`, `Non-negotiable design decisions (do not silently change these)` (+109 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **36 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `get_conn()` connect `main.py` to `Campaign Pipeline Orchestration`, `ICP Prefilter & Calibration Testing`, `Apollo Lead Search & Enrichment`, `ICP Scoring & Usage Tracking`?**
  _High betweenness centrality (0.030) - this node is a cross-community bridge._
- **Why does `build_and_score_candidates()` connect `ICP Prefilter & Calibration Testing` to `Campaign Pipeline Orchestration`, `Apollo Lead Search & Enrichment`, `main.py`?**
  _High betweenness centrality (0.008) - this node is a cross-community bridge._
- **Why does `log_llm_usage()` connect `main.py` to `Outreach Copy Generation`, `ICP Prefilter & Calibration Testing`, `ICP Scoring & Usage Tracking`?**
  _High betweenness centrality (0.008) - this node is a cross-community bridge._
- **What connects `End-to-end test suite. Run with: python campaign_test.py Requires uvicorn main:`, `Environment variable management + product catalog loading.`, `Runtime-editable settings (thresholds, testing caps, pricing).     Falls back t` to the rest of the system?**
  _175 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Campaign Pipeline Orchestration` be split into smaller, more focused modules?**
  _Cohesion score 0.14461538461538462 - nodes in this community are weakly interconnected._
- **Should `ICP Prefilter & Calibration Testing` be split into smaller, more focused modules?**
  _Cohesion score 0.0951219512195122 - nodes in this community are weakly interconnected._
- **Should `ICP Scoring & Usage Tracking` be split into smaller, more focused modules?**
  _Cohesion score 0.14245014245014245 - nodes in this community are weakly interconnected._