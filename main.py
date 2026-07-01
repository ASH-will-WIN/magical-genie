"""
FastAPI backend. Single /campaign endpoint orchestrates:
scrape -> context extraction -> domain resolution -> lead search -> parallel
copy generation -> persist. Every failure path returns a structured partial
result instead of a 500 (see CLAUDE.md "Failure is always soft").
"""
import json

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from config import load_product_catalog
from database import get_conn, init_db, now_iso
from services.apollo import find_leads, resolve_domain
from services.context import extract_context
from services.copy import generate_all_copy
from services.scraper import scrape_article

app = FastAPI(title="Magical Genie")


class CampaignRequest(BaseModel):
    url: str | None = None
    manual_text: str | None = None  # paywall fallback


@app.on_event("startup")
def startup():
    init_db()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/scrape")
async def scrape_endpoint(req: CampaignRequest):
    if not req.url:
        raise HTTPException(400, "url is required")
    result = await scrape_article(req.url)
    return {
        "text": result.text,
        "is_paywalled": result.is_paywalled,
        "error": result.error,
    }


@app.post("/analyze")
async def analyze_endpoint(req: CampaignRequest):
    text = req.manual_text
    if not text and req.url:
        scraped = await scrape_article(req.url)
        if scraped.is_paywalled:
            return {"status": "paywalled", "context": None}
        if not scraped.text:
            return {"status": "scrape_failed", "error": scraped.error, "context": None}
        text = scraped.text

    if not text:
        raise HTTPException(400, "url or manual_text is required")

    try:
        ctx = await extract_context(text)
    except ValueError as e:
        return {"status": "extraction_failed", "error": str(e), "context": None}

    return {"status": "ok", "context": ctx.model_dump()}


@app.post("/campaign")
async def run_campaign(req: CampaignRequest):
    if not req.url and not req.manual_text:
        raise HTTPException(400, "url or manual_text is required")

    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO campaigns (url, status, created_at) VALUES (?, 'analyzing', ?)",
            (req.url or "manual_paste", now_iso()),
        )
        campaign_id = cur.lastrowid

    def set_status(status: str):
        with get_conn() as conn:
            conn.execute("UPDATE campaigns SET status = ? WHERE id = ?", (status, campaign_id))

    # 1. Scrape (if needed)
    text = req.manual_text
    if not text:
        scraped = await scrape_article(req.url)
        if scraped.is_paywalled:
            set_status("failed")
            return {"campaign_id": campaign_id, "status": "paywalled", "leads": [], "context": None}
        if not scraped.text:
            set_status("failed")
            return {"campaign_id": campaign_id, "status": "scrape_failed", "error": scraped.error, "leads": [], "context": None}
        text = scraped.text

    # 2. Context extraction
    try:
        ctx = await extract_context(text)
    except ValueError as e:
        set_status("failed")
        return {"campaign_id": campaign_id, "status": "extraction_failed", "error": str(e), "leads": [], "context": None}

    with get_conn() as conn:
        conn.execute(
            """INSERT INTO contexts (campaign_id, entity, location, catalyst, pain_points, product_id, urgency_score)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (campaign_id, ctx.entity, ctx.location, ctx.catalyst, json.dumps(ctx.pain_points), ctx.product_id, ctx.urgency_score),
        )
    set_status("context_extracted")

    # 3. Domain resolution (soft-fail -> partial result, 0 leads)
    domain = await resolve_domain(ctx.entity)
    if not domain:
        set_status("generated")
        return {"campaign_id": campaign_id, "status": "no_domain", "context": ctx.model_dump(), "leads": []}

    # 4. Lead search
    product = next((p for p in load_product_catalog() if p["product_id"] == ctx.product_id), None)
    target_titles = product["target_titles"] if product else []
    raw_leads = await find_leads(domain, target_titles, city=ctx.city, state=ctx.state)

    if not raw_leads:
        set_status("generated")
        return {"campaign_id": campaign_id, "status": "zero_leads", "context": ctx.model_dump(), "leads": []}

    saved_leads = []
    with get_conn() as conn:
        for lead in raw_leads:
            try:
                cur = conn.execute(
                    """INSERT OR IGNORE INTO leads
                       (campaign_id, apollo_id, first_name, last_name, title, seniority, email, phone, linkedin)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (campaign_id, lead["apollo_id"], lead["first_name"], lead["last_name"],
                     lead["title"], lead["seniority"], lead["email"], lead["phone"], lead["linkedin"]),
                )
                lead["db_id"] = cur.lastrowid
                saved_leads.append(lead)
            except Exception:
                continue
    set_status("leads_found")

    # 5. Copy generation (parallel, soft-fail per lead)
    ctx_dict = ctx.model_dump()
    results = await generate_all_copy(saved_leads, ctx_dict, campaign_id)

    with get_conn() as conn:
        for r in results:
            lead = r["lead"]
            for channel, copy in r["copy"].items():
                if "error" in copy:
                    continue
                conn.execute(
                    """INSERT INTO creatives (campaign_id, lead_id, channel, subject_line, body_text, tracking_url)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (campaign_id, lead["db_id"], channel, copy.get("subject_line"), copy["body_text"], copy["tracking_url"]),
                )
    set_status("generated")

    return {
        "campaign_id": campaign_id,
        "status": "generated",
        "context": ctx_dict,
        "leads": results,
    }


@app.post("/click")
async def log_click(campaign_id: int, apollo_id: str, channel: str):
    # Best-effort: click logging failure must never break the caller
    try:
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO clicks (campaign_id, apollo_id, channel, clicked_at) VALUES (?, ?, ?, ?)",
                (campaign_id, apollo_id, channel, now_iso()),
            )
        return {"status": "logged"}
    except Exception as e:
        return {"status": "logging_failed", "error": str(e)}


@app.get("/campaigns")
async def list_campaigns():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM campaigns ORDER BY created_at DESC").fetchall()
    return [dict(r) for r in rows]


@app.get("/campaigns/{campaign_id}")
async def get_campaign(campaign_id: int):
    with get_conn() as conn:
        campaign = conn.execute("SELECT * FROM campaigns WHERE id = ?", (campaign_id,)).fetchone()
        if not campaign:
            raise HTTPException(404, "campaign not found")
        ctx = conn.execute("SELECT * FROM contexts WHERE campaign_id = ?", (campaign_id,)).fetchone()
        leads = conn.execute("SELECT * FROM leads WHERE campaign_id = ?", (campaign_id,)).fetchall()
        creatives = conn.execute("SELECT * FROM creatives WHERE campaign_id = ?", (campaign_id,)).fetchall()

    return {
        "campaign": dict(campaign),
        "context": dict(ctx) if ctx else None,
        "leads": [dict(l) for l in leads],
        "creatives": [dict(c) for c in creatives],
    }
