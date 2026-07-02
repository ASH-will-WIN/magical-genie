"""
FastAPI backend. Single /campaign endpoint orchestrates:
scrape -> (context extraction || theme-driven ICP matching, in parallel) ->
lead search + copy generation for approved companies only -> persist. Every
failure path returns a structured partial result instead of a 500 (see
CLAUDE.md "Failure is always soft").
"""
import asyncio
import json

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from database import get_conn, init_db, now_iso
from services.context import extract_context
from services.icp_matching.pipeline import (
    approve_candidate,
    build_and_score_candidates,
    fetch_leads_for_approved,
    reject_candidate,
)
from services.logging_utils import log
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
    log("main", f"campaign {campaign_id}: created, status=analyzing (url={req.url or 'manual_paste'})")

    status_holder = ["analyzing"]

    def set_status(status: str):
        log("status", f"campaign {campaign_id}: {status_holder[0]} -> {status}")
        status_holder[0] = status
        with get_conn() as conn:
            conn.execute("UPDATE campaigns SET status = ? WHERE id = ?", (status, campaign_id))

    # 1. Scrape (if needed)
    text = req.manual_text
    if not text:
        log("main", f"campaign {campaign_id}: scraping {req.url}")
        scraped = await scrape_article(req.url)
        if scraped.is_paywalled:
            log("main", f"campaign {campaign_id}: scrape hit a paywall")
            set_status("failed")
            return {"campaign_id": campaign_id, "status": "paywalled", "leads": [], "context": None}
        if not scraped.text:
            log("main", f"campaign {campaign_id}: scrape failed: {scraped.error}")
            set_status("failed")
            return {"campaign_id": campaign_id, "status": "scrape_failed", "error": scraped.error, "leads": [], "context": None}
        text = scraped.text
        log("main", f"campaign {campaign_id}: scrape succeeded ({len(text)} chars)")
    else:
        log("main", f"campaign {campaign_id}: using manually pasted text ({len(text)} chars)")

    # 2. Context extraction AND theme-driven ICP candidate scoring, in parallel
    #    (context extraction still produces the company-specific intel used
    #    later in copy-gen; theme extraction/scoring is independent of it)
    log("main", f"campaign {campaign_id}: starting context extraction + theme/ICP scoring in parallel")
    ctx_result, scoring_result = await asyncio.gather(
        extract_context(text), build_and_score_candidates(campaign_id, text),
        return_exceptions=True,
    )

    if isinstance(ctx_result, Exception):
        log("main", f"campaign {campaign_id}: context extraction FAILED: {ctx_result}")
        set_status("failed")
        error = str(ctx_result) if isinstance(ctx_result, ValueError) else "context extraction failed unexpectedly"
        return {"campaign_id": campaign_id, "status": "extraction_failed", "error": error, "leads": [], "context": None}
    ctx = ctx_result
    log("main", f"campaign {campaign_id}: context extraction succeeded (entity={ctx.entity}, product_id={ctx.product_id})")

    if isinstance(scoring_result, Exception):
        log("main", f"campaign {campaign_id}: theme/ICP scoring raised unexpectedly: {scoring_result}")
        scoring_result = {"theme": None, "candidates": []}

    with get_conn() as conn:
        conn.execute(
            """INSERT INTO contexts (campaign_id, entity, location, catalyst, pain_points, product_id, urgency_score)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (campaign_id, ctx.entity, ctx.location, ctx.catalyst, json.dumps(ctx.pain_points), ctx.product_id, ctx.urgency_score),
        )
    set_status("theme_extracted")
    set_status("candidates_scored")

    ctx_dict = ctx.model_dump()
    theme = scoring_result["theme"]
    candidates = scoring_result["candidates"]

    if theme is None:
        # Soft-fail: theme extraction failed, so no ICP candidates could be
        # found at all -- distinct from "some candidates, none approved yet".
        log("main", f"campaign {campaign_id}: no theme -> no candidates found")
        set_status("awaiting_review")
        return {
            "campaign_id": campaign_id, "status": "no_candidates", "context": ctx_dict,
            "theme": None, "candidates": [], "leads": [],
        }

    approved = [c for c in candidates if c["bucket"] == "approved"]
    log("main", f"campaign {campaign_id}: {len(candidates)} candidates scored, {len(approved)} approved")

    if not approved:
        log("main", f"campaign {campaign_id}: zero approved companies -> awaiting human review")
        set_status("awaiting_review")
        return {
            "campaign_id": campaign_id, "status": "awaiting_review", "context": ctx_dict,
            "theme": theme, "candidates": candidates, "leads": [],
        }

    # 3. Lead search + copy generation for approved companies only
    results = await fetch_leads_for_approved(campaign_id, candidates, ctx)
    set_status("leads_found")
    set_status("generated")
    log("main", f"campaign {campaign_id}: done -> {len(results)} leads with copy generated")

    return {
        "campaign_id": campaign_id,
        "status": "generated",
        "context": ctx_dict,
        "theme": theme,
        "candidates": candidates,
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
        candidates = conn.execute("SELECT * FROM icp_candidates WHERE campaign_id = ?", (campaign_id,)).fetchall()

    return {
        "campaign": dict(campaign),
        "context": dict(ctx) if ctx else None,
        "leads": [dict(l) for l in leads],
        "creatives": [dict(c) for c in creatives],
        "candidates": [dict(c) for c in candidates],
    }


@app.post("/campaigns/{campaign_id}/candidates/{candidate_id}/approve")
async def approve_candidate_endpoint(campaign_id: int, candidate_id: int):
    result = await approve_candidate(campaign_id, candidate_id)
    if result is None:
        raise HTTPException(404, "candidate not found for this campaign")
    return result


@app.post("/campaigns/{campaign_id}/candidates/{candidate_id}/reject")
async def reject_candidate_endpoint(campaign_id: int, candidate_id: int):
    result = await reject_candidate(campaign_id, candidate_id)
    if result is None:
        raise HTTPException(404, "candidate not found for this campaign")
    return result
