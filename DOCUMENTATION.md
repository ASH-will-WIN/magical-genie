# Magical Genie - Technical Documentation

## Project Overview
Magical Genie is a news-triggered B2B micro-campaign engine. The system takes a news article URL about a company, extracts sales intelligence, maps it to a product, finds verified leads at that company via Apollo.io, and generates personalized outreach copy (email/WhatsApp/Google Ads) per lead, tailored by seniority level (Director, VP, C-Suite).

## Third-Party APIs and Services

### 1. OpenAI API
- **Service**: OpenAI GPT-4o-mini
- **Purpose**: 
  - Extract structured sales intelligence from news articles (company name, catalyst, exactly 3 pain points, urgency score 1-10, product match)
  - Generate personalized outreach copy per lead seniority
- **Implementation**:
  - Located in `services/context.py` for intelligence extraction
  - Located in `services/copy.py` for copy generation
- **Configuration**:
  - API Key: `OPENAI_API_KEY` (from `.env`)
  - Model: `gpt-4o-mini` (hardcoded in `context.py` and `copy.py`)
  - Temperature: 
    - Context extraction: `0.1` (deterministic)
    - Copy generation: `0.7` (creative variation)
- **Usage Tracking**: 
  - LLM usage logged via `services/usage_tracker.py` (Phase 7 scaffold)

### 2. Apollo.io API
- **Service**: Apollo.io B2B contact and company database
- **Purpose**:
  - Domain resolution: Find company domain from name
  - Lead search: Find verified email leads at target companies
- **Implementation**:
  - Located in `services/apollo.py`
- **Endpoints Used**:
  - `POST https://api.apollo.io/v1/organizations/search` - Company domain resolution (FREE)
  - `POST https://api.apollo.io/v1/mixed_people/search` - Lead search with obfuscated previews (FREE)
  - `POST https://api.apollo.io/v1/people/match` - Email reveal (COSTS CREDITS - used only if explicitly requested per CLAUDE.md)
- **Key Constraints (from CLAUDE.md)**:
  - Only use `/mixed_people/search` (free) for lead discovery
  - Do NOT call enrichment endpoints (`/people/match`, `/organizations/enrich`) unless explicitly requested
  - Phone enrichment alone can burn 9,600+ credits/month at 100 campaigns (8 credits/phone)
  - Default to email-only if enrichment is enabled
- **Rate Limiting**: Handles 429 responses with 2-second wait and one retry
- **Configuration**:
  - API Key: `APOLLO_API_KEY` (from `.env`)
  - Base URL: `https://api.apollo.io/v1`

### 3. HTTP Client (httpx)
- **Library**: `httpx==0.27.2`
- **Purpose**: Async HTTP client for all external API calls (Apollo.io)
- **Usage**: 
  - Used in `services/apollo.py` for all Apollo.io communications
  - Configured with 20-second timeouts

### 4. Article Extraction (trafilatura)
- **Library**: `trafilatura==1.12.2`
- **Purpose**: Extract clean text content from news article URLs (handles paywalls, ads, etc.)
- **Usage**: 
  - Located in `services/scraper.py`
  - Function: `scrape_article(url: str) -> str`

### 5. UTM Tracking (Internal)
- **Service**: Custom UTM parameter builder
- **Purpose**: Generate tracking URLs for outbound campaigns
- **Implementation**: 
  - Located in `services/tracker.py`
  - Builds URLs with UTM parameters for attribution

## Open Source Libraries (from requirements.txt)

| Library | Version | Purpose |
|---------|---------|---------|
| fastapi | 0.115.0 | Async web framework for backend API |
| uvicorn[standard] | 0.30.6 | ASGI server for FastAPI |
| httpx | 0.27.2 | Async HTTP client (used for Apollo.io) |
| trafilatura | 1.12.2 | Article text extraction |
| openai | 1.51.0 | OpenAI API client |
| pydantic | 2.9.2 | Data validation and settings management |
| streamlit | 1.39.0 | Frontend UI framework |
| python-dotenv | 1.0.1 | Environment variable management |
| pandas | 2.2.3 | Data manipulation (used in usage dashboard) |

## Internal Services Architecture

```
FastAPI Backend (main.py)
├── Scraper (services/scraper.py) - httpx + trafilatura
├── Context AI (services/context.py) - OpenAI GPT-4o-mini (temp=0.1)
├── Apollo Domain Resolver (services/apollo.py) - httpx + Apollo.io API
├── Apollo Lead Finder (services/apollo.py) - httpx + Apollo.io API (/mixed_people/search)
├── Copy AI (services/copy.py) - OpenAI GPT-4o-mini (temp=0.7, parallel via asyncio.gather)
├── UTM Tracker (services/tracker.py) - Campaign tracking URL builder
├── Usage Tracker (services/usage_tracker.py) - Phase 7 cost logging (scaffolded)
└── Database (database.py) - SQLite (campaigns.db)

Streamlit Frontend (frontend.py)
- Multi-page UI: Home, History, Usage/Cost, Settings, Review Queue
- Session state management to avoid redundant API calls
- Calls FastAPI backend endpoints
```

## Non-Negotiable Design Decisions (from CLAUDE.md)

1. **Personalization is real, not mail merge**: 
   - Copy generation uses urgency score + pain points + seniority to produce fundamentally different messaging per person
   - Director angle: execution speed, timelines, not looking bad to VP
   - VP angle: strategic risk, vendor consolidation, budget optics
   - C-Suite angle: board liability, compliance readiness, cost savings

2. **Failure is always soft**:
   - Domain resolution fails → return partial result (0 leads, context still returned)
   - One lead's copy generation fails → others still complete (asyncio.gather with return_exceptions, filter failures)
   - Click logging fails → campaign still returns successfully (best-effort only)
   - Unknown LLM model in cost tracking → log warning, cost=$0, continue

3. **Product catalog is explicit, not inferred**:
   - Products live in `data/product_catalog.json`
   - LLM can only choose a product_id that exists in that file (validated with Pydantic)
   - Never let LLM hallucinate a product

4. **Urgency score rubric (fixed)**:
   - 9-10 = deadline within 3 months
   - 7-8 = deadline within 6 months
   - 5-6 = timeline within 12 months
   - 3-4 = timeline vague or missing
   - 1-2 = no deadline

5. **Exactly 3 pain points per article** (not 2, not 5)

6. **Apollo usage**:
   - `/mixed_people/search` is FREE — use this for lead discovery
   - Only `/people/match` and `/organizations/enrich` cost credits
   - Do NOT call enrichment endpoints unless user explicitly asks for it
   - Default to email-only if enrichment is ever turned on

7. **Temperatures**:
   - Context extraction: 0.1 (deterministic)
   - Copy generation: 0.7 (creative variation)

8. **Copy generation is parallel** via `asyncio.gather`:
   - 12 leaves should take ~4s, not ~36s (hard UX requirement)

9. **SQLite is intentional for MVP**:
   - Don't "upgrade" to Postgres unless asked (that's Phase 11, not a default)

10. **No built-in email sending**:
    - Export-only via CSV is intentional (GDPR/CAN-SPAM liability avoidance), not a missing feature

## Known Limitations (from CLAUDE.md)

- Domain resolution success ~95% (DNS guessing is imperfect) — no manual override in UI yet
- Copy quality varies at temp=0.7 by design; if it degrades, lower temp or tighten prompt before reaching for bigger model
- Product catalog requires a restart to change (no hot-reload)
- Only top-of-funnel click tracking; no click-to-conversion

## Setup Instructions (from CLAUDE.md)

1. Fill in `.env` from `.env.example` (OPENAI_API_KEY, APOLLO_API_KEY)
2. Run `pip3 install -r requirements.txt` (use pip3/python3 as needed)
3. Run `python3 database.py` to init `campaigns.db` (or it auto-inits on first run)
4. Start backend: `uvicorn main:app --reload --port 8000`
5. Start frontend: `streamlit run frontend.py` (in second terminal)
6. Test end-to-end: `python3 campaign_test.py` against a real article URL

## Data Flow Summary

1. **User Input**: News article URL pasted in Streamlit UI
2. **Scraper**: Extracts article text via trafilatura (`services/scraper.py`)
3. **Context AI**: 
   - Sends article to OpenAI GPT-4o-mini (temp=0.1) 
   - Extracts: company name, city/state/country, catalyst, exactly 3 pain points, product match from catalog, urgency score 1-10
   - Uses Pydantic validation (especially for product_id against catalog)
4. **Apollo Domain Resolution**:
   - Tries Apollo.io organization search for company domain
   - Falls back to DNS guessing (`companyame.com` -> slug)
5. **Apollo Lead Search**:
   - Uses `/mixed_people/search` (FREE) to find leads at domain
   - Returns obfuscated preview data (names, titles, companies)
6. **Copy Generation** (parallel via asyncio.gather):
   - For each lead, sends context + lead seniority to OpenAI GPT-4o-mini (temp=0.7)
   - Generates personalized outreach copy per channel (email/WhatsApp/Google Ads)
   - Director/VP/C-Suite get fundamentally different messaging angles
7. **Database**: Stores campaign, leads, copy, and usage metrics (SQLite)
8. **Output**: Streamlit UI displays results with export to CSV

## Usage Tracking (Phase 7 - Scaffolded)

- **Purpose**: Track LLM token usage and Apollo credit costs
- **Location**: `services/usage_tracker.py` and `services/usage_dashboard.py`
- **Status**: Scaffolded but not yet wired into main request flow (next task)
- **Tracks**:
  - LLM usage: prompt/completion tokens by model
  - Apollo usage: credits consumed by endpoint type
- **Storage**: `usage_log` table in SQLite

## File Structure Overview

```
magical-genie/
├── .env.example
├── requirements.txt
├── database.py              # SQLite initialization and helpers
├── main.py                  # FastAPI backend
├── frontend.py              # Streamlit multi-page UI
├── campaign_test.py         # End-to-end test script
├── data/
│   └── product_catalog.json # Explicit product list (no LLM hallucination)
├── services/
│   ├── scraper.py           # Article extraction (httpx + trafilatura)
│   ├── context.py           # OpenAI context extraction (temp=0.1)
│   ├── apollo.py            # Apollo.io domain/lead search (httpx)
│   ├── copy.py              # Parallel copy generation (temp=0.7)
│   ├── tracker.py           # UTM tracking URL builder
│   ├── usage_tracker.py     # LLM/Apollo usage logging (scaffolded)
│   └── usage_dashboard.py   # Cost reporting views (scaffolded)
│   └── icp_matching/        # Lead scoring/pipeline (additional logic)
├── tests/                   # Unit tests
└── graphify-out/            # Knowledge graph (for developer orientation)
```