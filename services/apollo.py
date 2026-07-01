"""
Apollo.io integration:
- Domain resolution: org search (primary) -> DNS pattern guessing (fallback)
- Lead search: /mixed_people/search (FREE endpoint — do not swap for enrichment
  endpoints without an explicit ask, see CLAUDE.md)
- Seniority normalization -> director | vp | c_suite
- Rate-limit handling: 429 -> wait 2s, retry once
"""
import asyncio
import re

import httpx

from config import APOLLO_API_KEY

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
    async with httpx.AsyncClient(timeout=15) as client:
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
        except httpx.HTTPError:
            pass

    # Fallback: DNS pattern guessing
    return _guess_domain(company_name)


async def _search_people(client: httpx.AsyncClient, domain: str, target_titles: list[str],
                          location: str | None, max_results: int) -> httpx.Response:
    """Single /mixed_people/search call (FREE endpoint). Verified emails only.
    429 -> wait 2s, retry once."""
    payload = {
        "q_organization_domains": domain,
        "person_titles": target_titles,
        "contact_email_status": ["verified"],
        "page": 1,
        "per_page": max_results,
    }
    if location:
        payload["person_locations"] = [location]

    resp = await client.post(f"{APOLLO_BASE}/mixed_people/search", headers=_headers(), json=payload)
    if resp.status_code == 429:
        await asyncio.sleep(2)
        resp = await client.post(f"{APOLLO_BASE}/mixed_people/search", headers=_headers(), json=payload)
    return resp


def _leads_from_people(people: list[dict]) -> list[dict]:
    leads = []
    for p in people:
        leads.append({
            "apollo_id": p.get("id"),
            "first_name": p.get("first_name"),
            "last_name": p.get("last_name"),
            "title": p.get("title"),
            "seniority": normalize_seniority(p.get("seniority")),
            "email": p.get("email"),
            "phone": (p.get("phone_numbers") or [{}])[0].get("raw_number") if p.get("phone_numbers") else None,
            "linkedin": p.get("linkedin_url"),
        })
    return leads


async def find_leads(domain: str, target_titles: list[str], city: str | None = None,
                      state: str | None = None, max_results: int = 12) -> list[dict]:
    """Uses free /mixed_people/search endpoint. 3-tier location fallback:
    city -> state -> no filter, stopping at the first tier that returns results."""
    tiers = [loc for loc in (city, state) if loc] + [None]

    async with httpx.AsyncClient(timeout=20) as client:
        for location in tiers:
            resp = await _search_people(client, domain, target_titles, location, max_results)
            if resp.status_code >= 400:
                continue
            people = resp.json().get("people", [])
            if people or location is None:
                return _leads_from_people(people)
    return []
