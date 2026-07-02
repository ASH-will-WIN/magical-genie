"""
Theme-driven, multi-company ICP matching pipeline (Handoff 2).

Replaces the old single-company domain-resolution flow: instead of resolving
the one named company from context extraction, extract_theme() identifies the
underlying market/vendor category, Apollo org search finds candidate
companies in that category, prefilter + scoring narrow them down, and only
score>=70/not-excluded ("approved") companies automatically proceed to lead
search + copy generation. 40-69 ("needs_review") candidates surface in the UI
for a human decision (see main.py's approve/reject endpoints). <40 or
exclude=True ("rejected") are auto-dropped but stay visible, reversible in
the UI. Every candidate (including ones dropped at the deterministic
prefilter stage) is persisted so nothing is silently discarded, per
CLAUDE.md's "failure is always soft" / show-full-state philosophy.
"""
import json

import asyncio

from config import MAX_LEAD_FETCH_COMPANIES, MAX_LEADS_PER_CAMPAIGN, load_icp_config, load_product_catalog
from database import get_conn, now_iso
from services.apollo import find_leads, search_organizations
from services.copy import generate_all_copy
from services.icp_matching.prefilter import prefilter_candidates
from services.icp_matching.scoring import score_candidates_batch
from services.icp_matching.theme_extraction import extract_theme
from services.logging_utils import log
from services.scraper import scrape_article

APPROVE_THRESHOLD = 70
REVIEW_THRESHOLD = 40
CLUSTER_LABELS = ["article-only", "icp-only", "blended"]


def _campaign_lead_fetch_counts(campaign_id: int) -> tuple[int, int]:
    """Returns (companies_fetched, total_leads) for this campaign so far.
    companies_fetched counts icp_candidates rows already marked
    'leads_fetched' (i.e. a fetch was attempted for that company, whether or
    not it found leads); total_leads counts actual rows in the leads table."""
    with get_conn() as conn:
        companies_fetched = conn.execute(
            "SELECT COUNT(*) AS c FROM icp_candidates WHERE campaign_id = ? AND status = 'leads_fetched'",
            (campaign_id,),
        ).fetchone()["c"]
        total_leads = conn.execute(
            "SELECT COUNT(*) AS c FROM leads WHERE campaign_id = ?", (campaign_id,)
        ).fetchone()["c"]
    return companies_fetched, total_leads


def _lead_fetch_cap_reason(campaign_id: int) -> str | None:
    """Returns a human-readable reason string if either testing cap
    (MAX_LEAD_FETCH_COMPANIES / MAX_LEADS_PER_CAMPAIGN, both optional /
    None = unlimited) is already reached for this campaign, else None."""
    companies_fetched, total_leads = _campaign_lead_fetch_counts(campaign_id)
    if MAX_LEAD_FETCH_COMPANIES is not None and companies_fetched >= MAX_LEAD_FETCH_COMPANIES:
        return f"MAX_LEAD_FETCH_COMPANIES ({MAX_LEAD_FETCH_COMPANIES}) reached ({companies_fetched} companies already fetched)"
    if MAX_LEADS_PER_CAMPAIGN is not None and total_leads >= MAX_LEADS_PER_CAMPAIGN:
        return f"MAX_LEADS_PER_CAMPAIGN ({MAX_LEADS_PER_CAMPAIGN}) reached ({total_leads} leads already found)"
    return None


def _has_unresolved_needs_review(campaign_id: int) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            """SELECT COUNT(*) AS c FROM icp_candidates
               WHERE campaign_id = ? AND bucket = 'needs_review' AND human_override IS NULL""",
            (campaign_id,),
        ).fetchone()
    return row["c"] > 0


def _maybe_advance_campaign_status(campaign_id: int) -> None:
    """Once every needs_review candidate has a human decision (approved or
    rejected), the campaign is fully resolved -- advance to 'generated'
    (terminal), mirroring the existing convention where DB status reaches
    'generated' even when the JSON-level outcome is zero leads (see main.py's
    no_domain/zero_leads paths). Without this, a campaign that started with
    zero auto-approved companies stays stuck at 'awaiting_review' forever
    once a human resolves the queue purely through reject actions -- neither
    approve_candidate() nor reject_candidate() touched campaigns.status
    before this fix."""
    if _has_unresolved_needs_review(campaign_id):
        return
    with get_conn() as conn:
        current = conn.execute("SELECT status FROM campaigns WHERE id = ?", (campaign_id,)).fetchone()
        if current and current["status"] != "generated":
            log("status", f"campaign {campaign_id}: {current['status']} -> generated (all candidates resolved)")
            conn.execute("UPDATE campaigns SET status = 'generated' WHERE id = ?", (campaign_id,))


def _bucket(score: int, exclude: bool) -> str:
    if exclude:
        return "rejected"
    if score >= APPROVE_THRESHOLD:
        return "approved"
    if score >= REVIEW_THRESHOLD:
        return "needs_review"
    return "rejected"


def _prefilter_drop_reason(candidate: dict, icp: dict) -> str:
    """Re-derives a human-readable reason for why prefilter_candidates()
    dropped this candidate, for persistence. Mirrors prefilter.py's own two
    checks (industry hard-exclude, employee band) without altering its
    validated decision logic -- prefilter.py itself only returns the kept
    list, not per-candidate reasons."""
    hard_exclude = [t.lower() for t in icp["hard_exclude_industries"]]
    industry = (candidate.get("industry") or "").strip().lower()
    if industry:
        term = next((t for t in hard_exclude if t in industry or industry in t), None)
        if term:
            return f"industry '{industry}' matches hard-exclude term '{term}'"

    employee_count = candidate.get("employee_count")
    min_emp = icp["size_band"]["employee_count_min"]
    max_emp = icp["size_band"]["employee_count_max"]
    if employee_count is not None and (employee_count < min_emp or employee_count > max_emp):
        return f"employee_count {employee_count} outside band [{min_emp}, {max_emp}]"

    return "dropped_at_prefilter"


async def _fetch_description(domain: str) -> str:
    scrape = await scrape_article(f"https://{domain}")
    return scrape.text or ""


def _target_titles_for(product_id: str | None) -> list[str]:
    product = next((p for p in load_product_catalog() if p["product_id"] == product_id), None)
    return product["target_titles"] if product else []


async def fetch_leads_and_copy_for_company(campaign_id: int, domain: str, target_titles: list[str],
                                            ctx_dict: dict, city: str | None, state: str | None) -> list[dict]:
    """Per-company lead-fetch + copy-gen + persist, reused for every
    'approved' candidate in the batch pipeline and for a single candidate
    when a human approves it from the needs_review queue. Same soft-fail
    per-row/per-channel behavior as the original single-company flow in
    main.py."""
    log("leads", f"campaign {campaign_id}: lead-fetch starting for {domain} (titles={target_titles}, city={city}, state={state})")
    raw_leads = await find_leads(domain, target_titles, city=city, state=state, campaign_id=campaign_id)
    log("leads", f"campaign {campaign_id}: {domain} -> {len(raw_leads)} leads found")
    if not raw_leads:
        return []

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

    if not saved_leads:
        return []

    log("copy", f"campaign {campaign_id}: {domain} -> copy-gen starting for {len(saved_leads)} lead(s)")
    results = await generate_all_copy(saved_leads, ctx_dict, campaign_id)

    with get_conn() as conn:
        for r in results:
            lead = r["lead"]
            name = f"{lead.get('first_name', '')} {lead.get('last_name', '')}".strip()
            channels_ok = [ch for ch, copy in r["copy"].items() if "error" not in copy]
            channels_failed = [ch for ch, copy in r["copy"].items() if "error" in copy]
            log("copy", f"campaign {campaign_id}: {domain} -> {name}: ok={channels_ok} failed={channels_failed}")
            for channel, copy in r["copy"].items():
                if "error" in copy:
                    continue
                conn.execute(
                    """INSERT INTO creatives (campaign_id, lead_id, channel, subject_line, body_text, tracking_url)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (campaign_id, lead["db_id"], channel, copy.get("subject_line"), copy["body_text"], copy["tracking_url"]),
                )
    log("copy", f"campaign {campaign_id}: {domain} -> copy-gen finished ({len(results)} lead(s) processed)")
    return results


async def build_and_score_candidates(campaign_id: int, article_text: str) -> dict:
    """Runs theme extraction -> Apollo keyword search -> prefilter -> scoring
    -> bucketing -> persistence. Deliberately does not need CampaignContext
    (only article_text), so main.py can run this concurrently with
    extract_context() via asyncio.gather (plan Deliverable 2 step 1) rather
    than sequentially.

    Returns {"theme": dict|None, "candidates": [dict, ...]}. theme=None
    signals theme extraction failed (soft-fail: zero candidates, caller
    decides on a distinct status rather than a hard failure)."""
    icp = load_icp_config()

    log("theme", f"campaign {campaign_id}: theme extraction starting")
    try:
        theme = await extract_theme(article_text, campaign_id=campaign_id)
    except ValueError as e:
        log("theme", f"campaign {campaign_id}: theme extraction FAILED: {e}")
        return {"theme": None, "candidates": []}
    log("theme", f"campaign {campaign_id}: theme extracted -> keywords={theme.apollo_keyword_candidates}")

    with get_conn() as conn:
        conn.execute(
            """INSERT INTO theme_extractions
               (campaign_id, theme_summary, affected_problem_space, vendor_categories_who_benefit,
                apollo_keyword_candidates, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (campaign_id, theme.theme_summary, json.dumps(theme.affected_problem_space),
             json.dumps(theme.vendor_categories_who_benefit), json.dumps(theme.apollo_keyword_candidates),
             now_iso()),
        )

    # 3 query clusters: article-only, ICP-only, blended (union, dedupe keeps order)
    vertical_keywords = icp["vertical_keywords"]
    blended = list(dict.fromkeys(theme.apollo_keyword_candidates + vertical_keywords))
    clusters = [theme.apollo_keyword_candidates, vertical_keywords, blended]

    emp_min = icp["size_band"]["employee_count_min"]
    emp_max = icp["size_band"]["employee_count_max"]
    log("apollo-search", f"campaign {campaign_id}: starting {len(clusters)} parallel org-search clusters (employee range {emp_min}-{emp_max})")
    cluster_results = await asyncio.gather(
        *[search_organizations(kw, emp_min, emp_max) for kw in clusters]
    )
    for label, orgs in zip(CLUSTER_LABELS, cluster_results):
        log("apollo-search", f"campaign {campaign_id}: cluster '{label}' -> {len(orgs)} orgs")

    merged: dict[str, dict] = {}
    for orgs in cluster_results:
        for org in orgs:
            domain = org.get("domain")
            if domain and domain not in merged:
                merged[domain] = org
    all_candidates = list(merged.values())
    log("apollo-search", f"campaign {campaign_id}: {len(all_candidates)} unique candidates after dedupe")

    log("prefilter", f"campaign {campaign_id}: prefilter starting on {len(all_candidates)} candidates")
    kept = prefilter_candidates(all_candidates, icp)
    kept_domains = {c["domain"] for c in kept}
    dropped = [c for c in all_candidates if c["domain"] not in kept_domains]
    log("prefilter", f"campaign {campaign_id}: prefilter finished -> {len(kept)} kept, {len(dropped)} dropped")

    # Description sourcing: Apollo org search returns no description field
    # (see Step 0 finding) -- scrape each survivor's own site, same source
    # Handoff 1 calibrated scoring against.
    log("scoring", f"campaign {campaign_id}: scraping descriptions for {len(kept)} survivors")
    descriptions = await asyncio.gather(*[_fetch_description(c["domain"]) for c in kept])
    for c, description in zip(kept, descriptions):
        c["description"] = description

    log("scoring", f"campaign {campaign_id}: LLM scoring starting for {len(kept)} candidates")
    scores = await score_candidates_batch(kept, icp, campaign_id=campaign_id) if kept else []
    log("scoring", f"campaign {campaign_id}: LLM scoring finished")

    candidate_rows = []
    for c in dropped:
        log("bucket", f"campaign {campaign_id}: {c.get('name')} ({c.get('domain')}) -> dropped_at_prefilter: {_prefilter_drop_reason(c, icp)}")
        candidate_rows.append({
            "company_name": c.get("name"), "domain": c.get("domain"),
            "apollo_industry": c.get("industry"), "apollo_employee_count": c.get("employee_count"),
            "apollo_description": None,
            "prefilter_result": "dropped_at_prefilter", "prefilter_reason": _prefilter_drop_reason(c, icp),
            "score": None, "score_reason": None, "exclude_flag": None,
            "bucket": "dropped_at_prefilter", "status": "pending_review",
        })
    for c, s in zip(kept, scores):
        bucket = _bucket(s.score, s.exclude)
        log("bucket", f"campaign {campaign_id}: {c.get('name')} ({c.get('domain')}) -> {bucket} (score={s.score}, exclude={s.exclude}): {s.reason}")
        candidate_rows.append({
            "company_name": c.get("name"), "domain": c.get("domain"),
            "apollo_industry": c.get("industry"), "apollo_employee_count": c.get("employee_count"),
            "apollo_description": c.get("description"),
            "prefilter_result": "kept", "prefilter_reason": None,
            "score": s.score, "score_reason": s.reason, "exclude_flag": s.exclude,
            "bucket": bucket, "status": "pending_review",
        })

    with get_conn() as conn:
        for row in candidate_rows:
            cur = conn.execute(
                """INSERT OR IGNORE INTO icp_candidates
                   (campaign_id, company_name, domain, apollo_industry, apollo_employee_count,
                    apollo_description, prefilter_result, prefilter_reason, score, score_reason,
                    exclude_flag, bucket, status, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (campaign_id, row["company_name"], row["domain"], row["apollo_industry"],
                 row["apollo_employee_count"], row["apollo_description"], row["prefilter_result"],
                 row["prefilter_reason"], row["score"], row["score_reason"], row["exclude_flag"],
                 row["bucket"], row["status"], now_iso()),
            )
            row["id"] = cur.lastrowid

    n_approved = sum(1 for r in candidate_rows if r["bucket"] == "approved")
    n_review = sum(1 for r in candidate_rows if r["bucket"] == "needs_review")
    n_rejected = sum(1 for r in candidate_rows if r["bucket"] in ("rejected", "dropped_at_prefilter"))
    log("bucket", f"campaign {campaign_id}: persisted {len(candidate_rows)} candidates -> approved={n_approved} needs_review={n_review} rejected={n_rejected}")

    return {"theme": theme.model_dump(), "candidates": candidate_rows}


async def fetch_leads_for_approved(campaign_id: int, candidates: list[dict], ctx) -> list[dict]:
    """Runs fetch_leads_and_copy_for_company() for every 'approved' candidate
    row (as returned by build_and_score_candidates), once per company, and
    marks each as 'leads_fetched'. `ctx` is the CampaignContext produced by
    the parallel extract_context() call in main.py -- used for the
    company-specific intel in copy-gen, but NOT for city/state: ctx.city/
    ctx.state are the location of the article's named company (the old
    single-company flow's target), which has no relation to where an
    unrelated candidate company from the Venn search is actually
    headquartered. Location filtering isn't applied here at all; it would
    need to come from each candidate's own Apollo-provided address, not the
    article's."""
    target_titles = _target_titles_for(ctx.product_id)
    ctx_dict = ctx.model_dump()
    approved = [c for c in candidates if c["bucket"] == "approved"]
    log("leads", f"campaign {campaign_id}: fetching leads for {len(approved)} approved companies")

    approved_results = []
    for i, row in enumerate(approved, start=1):
        cap_reason = _lead_fetch_cap_reason(campaign_id)
        if cap_reason:
            log("lead-fetch", f"campaign {campaign_id}: stopping - {cap_reason} - {len(approved) - i + 1} remaining approved companies left unfetched")
            break

        log("leads", f"campaign {campaign_id}: [{i}/{len(approved)}] {row['company_name']} ({row['domain']})")
        results = await fetch_leads_and_copy_for_company(
            campaign_id, row["domain"], target_titles, ctx_dict, city=None, state=None
        )
        approved_results.extend(results)
        with get_conn() as conn:
            conn.execute("UPDATE icp_candidates SET status = 'leads_fetched' WHERE id = ?", (row["id"],))

    log("leads", f"campaign {campaign_id}: lead-fetch pass finished -> {len(approved_results)} total leads")
    return approved_results


async def approve_candidate(campaign_id: int, candidate_id: int) -> dict | None:
    """Human approves a single needs_review candidate from the Streamlit
    queue: marks human_override='approved', then runs the same lead-fetch +
    copy-gen used for auto-approved candidates. Returns None if the
    candidate doesn't exist for this campaign."""
    log("review", f"campaign {campaign_id}: APPROVE requested for candidate {candidate_id}")
    with get_conn() as conn:
        candidate = conn.execute(
            "SELECT * FROM icp_candidates WHERE id = ? AND campaign_id = ?", (candidate_id, campaign_id)
        ).fetchone()
        if not candidate:
            log("review", f"campaign {campaign_id}: candidate {candidate_id} not found")
            return None
        ctx_row = conn.execute("SELECT * FROM contexts WHERE campaign_id = ?", (campaign_id,)).fetchone()
        conn.execute(
            "UPDATE icp_candidates SET human_override = 'approved', status = 'reviewed' WHERE id = ?",
            (candidate_id,),
        )
    log("review", f"campaign {campaign_id}: candidate {candidate_id} ({candidate['company_name']}) marked human_override=approved -> triggering lead-fetch + copy-gen")

    cap_reason = _lead_fetch_cap_reason(campaign_id)
    if cap_reason:
        log("lead-fetch", f"campaign {campaign_id}: candidate {candidate_id} approve -> lead-fetch skipped - {cap_reason}")
        _maybe_advance_campaign_status(campaign_id)
        return {
            "candidate_id": candidate_id, "results": [],
            "message": f"Lead fetch skipped — testing cap reached for this campaign ({cap_reason})",
        }

    if not ctx_row:
        log("review", f"campaign {campaign_id}: no context row found, cannot fetch leads for candidate {candidate_id}")
        _maybe_advance_campaign_status(campaign_id)
        return {"candidate_id": candidate_id, "results": [], "error": "no context found for this campaign"}

    ctx_dict = {
        "entity": ctx_row["entity"], "catalyst": ctx_row["catalyst"],
        "pain_points": json.loads(ctx_row["pain_points"] or "[]"),
        "product_id": ctx_row["product_id"], "urgency_score": ctx_row["urgency_score"],
        "location": ctx_row["location"],
    }
    target_titles = _target_titles_for(ctx_dict["product_id"])
    # contexts only persists a combined display "location" string, not raw
    # city/state (existing schema, unchanged per Deliverable 1) -- the
    # manual-approve path degrades to a domain-wide lead search, no
    # city/state tiered narrowing.
    results = await fetch_leads_and_copy_for_company(
        campaign_id, candidate["domain"], target_titles, ctx_dict, city=None, state=None
    )
    with get_conn() as conn:
        conn.execute("UPDATE icp_candidates SET status = 'leads_fetched' WHERE id = ?", (candidate_id,))

    log("review", f"campaign {campaign_id}: candidate {candidate_id} approve complete -> {len(results)} leads")
    _maybe_advance_campaign_status(campaign_id)
    return {"candidate_id": candidate_id, "results": results}


async def reject_candidate(campaign_id: int, candidate_id: int) -> dict | None:
    """Human rejects a single needs_review candidate: marks
    human_override='rejected', no further action. Returns None if the
    candidate doesn't exist for this campaign."""
    log("review", f"campaign {campaign_id}: REJECT requested for candidate {candidate_id}")
    with get_conn() as conn:
        candidate = conn.execute(
            "SELECT * FROM icp_candidates WHERE id = ? AND campaign_id = ?", (candidate_id, campaign_id)
        ).fetchone()
        if not candidate:
            log("review", f"campaign {campaign_id}: candidate {candidate_id} not found")
            return None
        conn.execute(
            "UPDATE icp_candidates SET human_override = 'rejected', status = 'reviewed' WHERE id = ?",
            (candidate_id,),
        )
    log("review", f"campaign {campaign_id}: candidate {candidate_id} ({candidate['company_name']}) marked human_override=rejected, no further action")
    _maybe_advance_campaign_status(campaign_id)
    return {"candidate_id": candidate_id}
