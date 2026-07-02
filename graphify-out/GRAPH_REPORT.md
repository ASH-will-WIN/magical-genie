# Graph Report - .  (2026-07-02)

## Corpus Check
- Corpus is ~17,812 words - fits in a single context window. You may not need a graph.

## Summary
- 195 nodes · 405 edges · 16 communities (15 shown, 1 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 11 edges (avg confidence: 0.87)
- Token cost: 0 input · 82,750 output

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
- [[_COMMUNITY_Streamlit Frontend|Streamlit Frontend]]

## God Nodes (most connected - your core abstractions)
1. `CLAUDE.md — Magical Genie Project Memory` - 21 edges
2. `get_conn()` - 20 edges
3. `build_and_score_candidates()` - 15 edges
4. `log()` - 14 edges
5. `scrape_article()` - 11 edges
6. `approve_candidate()` - 10 edges
7. `main.py — FastAPI backend` - 10 edges
8. `now_iso()` - 9 edges
9. `run_campaign()` - 9 edges
10. `_try_tier()` - 9 edges

## Surprising Connections (you probably didn't know these)
- `services/icp_matching/theme_extraction.py — extract_theme()` --semantically_similar_to--> `services/context.py — LLM intelligence extraction (temp=0.1)`  [INFERRED] [semantically similar]
  handoff-1-icp-scoring-spec.md → CLAUDE.md
- `services/icp_matching/scoring.py — score_candidate()/score_candidates_batch()` --semantically_similar_to--> `services/copy.py — per-person copy generation (temp=0.7, parallel)`  [INFERRED] [semantically similar]
  handoff-1-icp-scoring-spec.md → CLAUDE.md
- `get_campaign_cost_summary()` --calls--> `get_conn()`  [EXTRACTED]
  services/usage_tracker.py → database.py
- `fastapi==0.115.0` --shares_data_with--> `main.py — FastAPI backend`  [INFERRED]
  requirements.txt → CLAUDE.md
- `pandas==2.2.3` --shares_data_with--> `frontend.py — Streamlit UI`  [INFERRED]
  requirements.txt → CLAUDE.md

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Non-negotiable design decisions (CLAUDE.md)** — claude_md_personalization_design, claude_md_soft_failure_design, claude_md_product_catalog_explicit, claude_md_apollo_free_endpoint_policy, claude_md_sqlite_decision, claude_md_no_email_sending_decision [EXTRACTED 1.00]
- **ICP Venn-diagram standalone module set (Handoff 1)** — services_icp_matching_theme_extraction_py, services_icp_matching_prefilter_py, services_icp_matching_scoring_py, services_icp_matching_test_calibration_py, data_icp_config_json [EXTRACTED 1.00]
- **Live pipeline wiring deliverables (Handoff 2)** — services_icp_matching_pipeline_py, migrations_002_add_icp_tables_py, handoff2_bucket_thresholds, handoff2_review_ui, handoff2_cost_tracking_tie_in [EXTRACTED 1.00]

## Communities (16 total, 1 thin omitted)

### Community 0 - "Campaign Pipeline Orchestration"
Cohesion: 0.10
Nodes (40): get_conn(), init_db(), now_iso(), SQLite schema + connection management. Zero-DevOps choice for MVP. Migrate to Po, approve_candidate_endpoint(), get_campaign(), list_campaigns(), log_click() (+32 more)

### Community 1 - "Outreach Copy Generation"
Cohesion: 0.18
Nodes (15): load_product_catalog(), Environment variable management + product catalog loading., ChannelCopy, _enforce_channel_constraints(), generate_all_copy(), generate_copy_for_lead(), _generate_one(), _product_for() (+7 more)

### Community 2 - "ICP Prefilter & Calibration Testing"
Cohesion: 0.18
Nodes (14): load_icp_config(), prefilter_candidates(), Deterministic, non-LLM pre-filter: drops candidate companies that are obviously, main(), print_separation(), print_table(), Standalone calibration harness for ICP theme-extraction and scoring. Run: python, Step B: scrape each labeled company, prefilter, then batch-score     whatever su (+6 more)

### Community 3 - "Apollo Lead Search & Enrichment"
Cohesion: 0.21
Nodes (16): AsyncClient, Response, _guess_domain(), _headers(), _lead_from_matched_person(), normalize_seniority(), Apollo.io integration: - Domain resolution: org search (primary) -> DNS pattern, Single /mixed_people/api_search call (FREE endpoint). Verified emails     only. (+8 more)

### Community 4 - "ICP Scoring & Usage Tracking"
Cohesion: 0.21
Nodes (13): _build_prompt(), CandidateScore, Scores a single Apollo-style candidate company against Reinvent's ICP using an L, Scores all companies in parallel (asyncio.gather pattern from     services/copy., score_candidate(), score_candidates_batch(), _build_prompt(), extract_theme() (+5 more)

### Community 5 - "Core App Files & Dependencies"
Cohesion: 0.21
Nodes (13): database.py — SQLite schema + connection, frontend.py — Streamlit UI, Streamlit needs_review queue with approve/reject, main.py — FastAPI backend, requirements.txt — Magical Genie dependencies, fastapi==0.115.0, httpx==0.27.2, pandas==2.2.3 (+5 more)

### Community 6 - "Article Context Extraction"
Cohesion: 0.24
Nodes (9): BaseModel, product_ids(), analyze_endpoint(), CampaignRequest, scrape_endpoint(), _build_prompt(), CampaignContext, extract_context() (+1 more)

### Community 7 - "Project Design Principles (CLAUDE.md)"
Cohesion: 0.17
Nodes (12): CLAUDE.md — Magical Genie Project Memory, No built-in email sending — export-only via CSV, Copy generation is parallel via asyncio.gather, Personalization is real, not mail merge, Phase 7 cost dashboard (scaffolded, not wired in), Product catalog is explicit, not inferred, SQLite is intentional for MVP (no Postgres upgrade), Temperatures: context=0.1, copy=0.7 (+4 more)

### Community 8 - "Campaign Test Suite"
Cohesion: 0.36
Nodes (9): check(), End-to-end test suite. Run with: python campaign_test.py Requires uvicorn main:a, test_analyze(), test_click_logging(), test_database_integrity(), test_full_campaign(), test_health(), test_list_campaigns() (+1 more)

### Community 9 - "Handoff 2: ICP Pipeline Wiring Spec"
Cohesion: 0.22
Nodes (9): Apollo usage: free /mixed_people/search only, avoid enrichment credits, Score bucket thresholds: >=70 approved, 40-69 needs_review, <40 rejected, Phase 7 cost tracking tie-in (icp_theme_extraction, icp_scoring operations), icp_candidates table, ICP matching wired into /campaign pipeline, theme_extractions table, Handoff 2: Wire ICP Matching Into the Live Pipeline, migrations/002_add_icp_tables.py — theme_extractions, icp_candidates (+1 more)

### Community 10 - "Handoff 1: ICP Scoring Modules"
Cohesion: 0.46
Nodes (8): data/icp_config.json — Reinvent HIT ICP definition, Venn diagram ICP strategy (theme -> candidates -> score -> leads), Handoff 1: ICP Theme-Matching & Scoring Modules, services/icp_matching/pipeline.py — new orchestration logic, services/icp_matching/prefilter.py — prefilter_candidates(), services/icp_matching/scoring.py — score_candidate()/score_candidates_batch(), services/icp_matching/test_calibration.py — labeled test harness, services/icp_matching/theme_extraction.py — extract_theme()

### Community 11 - "Testing & Soft-Failure Design"
Cohesion: 0.33
Nodes (6): campaign_test.py — end-to-end test suite, Failure is always soft (no 500s, partial results), services/apollo.py — domain resolution + lead search, Magical Genie — Rebuild Verification Runbook, Known accepted simplifications vs. original (placeholder catalog, tracking URL, unwired Phase 7, no CI/Docker), 3-tier location fallback (city -> state -> no filter) for find_leads

### Community 12 - "Product Catalog & Channel Config"
Cohesion: 0.40
Nodes (6): config.py — env vars, pricing, product catalog loader, data/product_catalog.json — products, target titles, seniority angles, openai==1.51.0, services/context.py — LLM intelligence extraction (temp=0.1), services/copy.py — per-person copy generation (temp=0.7, parallel), Per-channel copy limits enforced in code (email subject<=60, whatsapp<=25 words, google_ads<=90 chars)

## Knowledge Gaps
- **14 isolated node(s):** `README.md — Magical Genie`, `Urgency score rubric (1-10 fixed)`, `Exactly 3 pain points per article`, `Temperatures: context=0.1, copy=0.7`, `Phase 7 cost dashboard (scaffolded, not wired in)` (+9 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **1 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `CLAUDE.md — Magical Genie Project Memory` connect `Project Design Principles (CLAUDE.md)` to `Handoff 2: ICP Pipeline Wiring Spec`, `Testing & Soft-Failure Design`, `Product Catalog & Channel Config`, `Core App Files & Dependencies`?**
  _High betweenness centrality (0.037) - this node is a cross-community bridge._
- **Why does `get_conn()` connect `Campaign Pipeline Orchestration` to `ICP Scoring & Usage Tracking`?**
  _High betweenness centrality (0.024) - this node is a cross-community bridge._
- **Why does `scrape_article()` connect `ICP Prefilter & Calibration Testing` to `Campaign Pipeline Orchestration`, `Article Context Extraction`?**
  _High betweenness centrality (0.022) - this node is a cross-community bridge._
- **What connects `End-to-end test suite. Run with: python campaign_test.py Requires uvicorn main:a`, `Environment variable management + product catalog loading.`, `SQLite schema + connection management. Zero-DevOps choice for MVP. Migrate to Po` to the rest of the system?**
  _57 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Campaign Pipeline Orchestration` be split into smaller, more focused modules?**
  _Cohesion score 0.10202020202020202 - nodes in this community are weakly interconnected._