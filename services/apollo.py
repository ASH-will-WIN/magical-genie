"""
Apollo.io integration:
- Domain resolution: org search (primary) -> DNS pattern guessing (fallback)
- Lead search: /mixed_people/api_search (FREE, but returns only obfuscated
  preview data -- see find_leads() docstring) + /people/match (email-only
  reveal, COSTS CREDITS -- see CLAUDE.md's Apollo credit-budget rule; never
  request phone reveal without an explicit ask)
- Seniority normalization -> director | vp | c_suite
- Rate-limit handling: 429 -> wait 2s, retry once
"""
import asyncio
import re

import httpx

from config import APOLLO_API_KEY
from services.logging_utils import log
from services.usage_tracker import log_apollo_usage

APOLLO_BASE = "https://api.apollo.io/v1"

SENIORITY_MAP = {
    "director": "director",
    "senior_director": "director",
    "vp": "vp",
    "vice_president": "vp",
    "svp": "vp",
    "evp": "vp",
    "c_suite": "c_suite",
    "founder": "c_suite",
    "owner": "c_suite",
    "chief": "c_suite",
}


def _headers():
    return {"Content-Type": "application/json", "X-Api-Key": APOLLO_API_KEY}


def normalize_seniority(raw: str | None) -> str:
    if not raw:
        return "director"
    raw = raw.lower()
    for key, mapped in SENIORITY_MAP.items():
        if key in raw:
            return mapped
    return "director"


def _guess_domain(company_name: str) -> str:
    slug = re.sub(r"[^a-z0-9]", "", company_name.lower())
    return f"{slug}.com"


async def resolve_domain(company_name: str) -> str | None:
    async with httpx.AsyncClient(timeout=20.0) as client:
        try:
            resp = await client.post(
                f"{APOLLO_BASE}/organizations/search",
                headers=_headers(),
                json={"q_organization_name": company_name, "page": 1, "per_page": 1},
            )
            if resp.status_code == 429:
                await asyncio.sleep(2)
                resp = await client.post(
                    f"{APOLLO_BASE}/organizations/search",
                    headers=_headers(),
                    json={"q_organization_name": company_name, "page": 1, "per_page": 1},
                )
            resp.raise_for_status()
            data = resp.json()
            orgs = data.get("organizations") or []
            if orgs and orgs[0].get("primary_domain"):
                return orgs[0]["primary_domain"]
        except httpx.TimeoutException as e:
            log("apollo-resolve", f"domain resolution timeout for {company_name}: {e}")
        except httpx.HTTPError:
            pass

    # Fallback: DNS pattern guessing
    return _guess_domain(company_name)


async def search_organizations(keywords: list[str], employee_min: int, employee_max: int,
                                per_page: int = 25) -> list[dict]:
    """Company-prospecting search (FREE endpoint) — /organizations/search with
    keyword + employee-count filters. Distinct from resolve_domain(), which
    looks up a single named company. Returns [] on any HTTP failure (soft-fail,
    caller treats as zero candidates for that query cluster)."""
    payload = {
        "q_organization_keyword_tags": keywords,
        "organization_num_employees_ranges": [f"{employee_min},{employee_max}"],
        "page": 1,
        "per_page": per_page,
    }
    async with httpx.AsyncClient(timeout=20.0) as client:
        try:
            resp = await client.post(f"{APOLLO_BASE}/organizations/search", headers=_headers(), json=payload)
            if resp.status_code == 429:
                await asyncio.sleep(2)
                resp = await client.post(f"{APOLLO_BASE}/organizations/search", headers=_headers(), json=payload)
            resp.raise_for_status()
            orgs = resp.json().get("organizations") or []
        except httpx.TimeoutException as e:
            log("apollo-search", f"org search timeout for keywords={keywords}: {e}")
            return []
        except httpx.HTTPError as e:
            log("apollo-search", f"org search failed for keywords={keywords}: {e}")
            return []

    log("apollo-search", f"keywords={keywords} -> {len(orgs)} raw orgs")
    return [
        {
            "name": org.get("name"),
            "domain": org.get("primary_domain"),
            "industry": org.get("industry"),
            "employee_count": org.get("estimated_num_employees"),
        }
        for org in orgs
        if org.get("primary_domain")
    ]


async def _search_people(client: httpx.AsyncClient, domain: str, target_titles: list[str],
                          location: str | None, max_results: int) -> httpx.Response:
    """Single /mixed_people/api_search call (FREE endpoint). Verified emails
    only. Returns obfuscated PREVIEW data (last_name_obfuscated, has_email
    boolean, no real email/phone) -- /mixed_people/search (full data) 403s on
    this account's Apollo plan. Real contact info requires a follow-up
    /people/match call per person (see _reveal_person). 429 -> wait 2s, retry
    once."""
    payload = {
        "q_organization_domains": domain,
        "person_titles": target_titles,
        "contact_email_status": ["verified"],
        "page": 1,
        "per_page": max_results,
    }
    if location:
        payload["person_locations"] = [location]

    try:
        resp = await client.post(f"{APOLLO_BASE}/mixed_people/api_search", headers=_headers(), json=payload)
        if resp.status_code == 429:
            await asyncio.sleep(2)
            resp = await client.post(f"{APOLLO_BASE}/mixed_people/api_search", headers=_headers(), json=payload)
        return resp
    except httpx.TimeoutException:
        # Re-raise to be handled by caller
        raise


async def _reveal_person(client: httpx.AsyncClient, person_id: str) -> dict | None:
    """Reveals real contact info for one person found via _search_people's
    obfuscated preview. COSTS CREDITS (1/email, per CLAUDE.md's
    APOLLO_CREDIT_COSTS). Email-only: reveal_personal_emails=False, and phone
    is never requested -- do not add phone reveal without an explicit ask,
    per CLAUDE.md's credit-budget rule. Returns None on failure/no-match."""
    payload = {"id": person_id, "reveal_personal_emails": False}
    try:
        resp = await client.post(f"{APOLLO_BASE}/people/match", headers=_headers(), json=payload)
        if resp.status_code == 429:
            await asyncio.sleep(2)
            resp = await client.post(f"{APOLLO_BASE}/people/match", headers=_headers(), json=payload)
        if resp.status_code >= 400:
            return None
        return resp.json().get("person")
    except httpx.TimeoutException:
        return None


def _lead_from_matched_person(p: dict) -> dict:
    return {
        "apollo_id": p.get("id"),
        "first_name": p.get("first_name"),
        "last_name": p.get("last_name"),
        "title": p.get("title"),
        "seniority": normalize_seniority(p.get("seniority")),
        "email": p.get("email"),
        "phone": None,  # phone reveal never requested -- see _reveal_person
        "linkedin": p.get("linkedin_url"),
    }


FOUNDER_FALLBACK_TITLES = ["CEO", "Founder", "Co-Founder", "CTO"]


async def _try_tier(client: httpx.AsyncClient, domain: str, titles: list[str], location: str | None,
                     max_results: int, campaign_id: int | None, tier_label: str) -> list[dict]:
    """Runs one search+reveal attempt for a single (titles, location) combo,
    tagged with tier_label for the console log (e.g. 'product_titles' vs
    'founder_fallback') so the two are distinguishable if the split matters
    later. Returns [] on any failure/no-match (soft-fail, caller tries the
    next tier)."""
    log("apollo-leads", f"{domain}: [{tier_label}] searching location={location!r} titles={titles}")
    try:
        resp = await _search_people(client, domain, titles, location, max_results)
        if resp.status_code >= 400:
            log("apollo-leads", f"{domain}: [{tier_label}] location={location!r} failed with status {resp.status_code}")
            return []
        people = resp.json().get("people", [])
        log("apollo-leads", f"{domain}: [{tier_label}] location={location!r} -> {len(people)} preview results")
        if not people:
            return []

        candidates = [p for p in people if p.get("id") and p.get("has_email")]
        log("apollo-leads", f"{domain}: [{tier_label}] revealing {len(candidates)}/{len(people)} candidates with has_email=true (costs credits)")
        if not candidates:
            return []
        revealed = await asyncio.gather(*[_reveal_person(client, p["id"]) for p in candidates])
        matched = [m for m in revealed if m and m.get("email")]
        log("apollo-leads", f"{domain}: [{tier_label}] reveal complete -> {len(matched)} usable leads with email")

        if campaign_id is not None and matched:
            log_apollo_usage(campaign_id, "enrichment", emails=len(matched))

        return [_lead_from_matched_person(m) for m in matched]
    except httpx.TimeoutException as e:
        log("apollo-leads", f"{domain}: [{tier_label}] timeout during search/reveal: {e}")
        return []


async def find_leads(domain: str, target_titles: list[str], city: str | None = None,
                      state: str | None = None, max_results: int = 12,
                      campaign_id: int | None = None) -> list[dict]:
    """Tiered search: product-specific target_titles at city -> state -> no
    location filter, stopping at the first tier that returns results. If all
    of those come back empty, falls back once more to founder-level titles
    (CEO/Founder/Co-Founder/CTO) with no location filter -- at the small
    (1-100 employee) companies this pipeline targets, dedicated
    compliance/security/legal titles frequently don't exist, but the founder
    is the real decision-maker for those functions. Search itself is free
    (/mixed_people/api_search); each matched person is then revealed via
    /people/match (credits, email-only) -- bounded to at most max_results
    reveals per call. campaign_id, if given, logs the resulting credit spend
    to usage_log via usage_tracker (best-effort, never raises)."""
    tiers = [loc for loc in (city, state) if loc] + [None]

    async with httpx.AsyncClient(timeout=20.0) as client:
        for location in tiers:
            try:
                leads = await _try_tier(client, domain, target_titles, location, max_results, campaign_id, "product_titles")
                if leads:
                    return leads
            except httpx.TimeoutException:
                log("apollo-leads", f"{domain}: timeout during product_titles search for location={location}")
                continue

        log("apollo-leads", f"{domain}: product-specific titles exhausted with 0 leads across all tiers, trying founder_fallback")
        try:
            return await _try_tier(client, domain, FOUNDER_FALLBACK_TITLES, None, max_results, campaign_id, "founder_fallback")
        except httpx.TimeoutException:
            log("apollo-leads", f"{domain}: timeout during founder_fallback search")
            return []