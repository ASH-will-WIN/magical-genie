"""
Extracts the underlying market theme from a news article -- NOT the named
company -- so a future handoff can search Apollo broadly for vendor
categories that would sell into this situation, instead of resolving the
single named company (which fails for small/niche companies). Same
retry/JSON-mode pattern as services/context.py. temperature=0.1 for
deterministic extraction.
"""
import json

from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from config import OPENAI_API_KEY
from services.usage_tracker import log_llm_usage

client = AsyncOpenAI(api_key=OPENAI_API_KEY)

MODEL = "gpt-4o-mini"
MAX_RETRIES = 3


class ThemeExtraction(BaseModel):
    theme_summary: str = Field(..., description="1-2 sentences on the underlying market shift/problem")
    affected_problem_space: list[str] = Field(..., description='e.g. "patient transport logistics"')
    vendor_categories_who_benefit: list[str] = Field(..., description='e.g. "AI-powered scheduling platforms"')
    apollo_keyword_candidates: list[str] = Field(
        ..., min_length=3, max_length=6, description="3-6 short phrases suitable for company search"
    )


_FEW_SHOT = """
Example 1
Article: "HealthcareDive: Rural hospital network signs multi-year deal with a
patient-transport logistics startup after struggling with missed appointments
and ambulance dispatch delays across its service area."
Output:
{
  "theme_summary": "Rural health systems are struggling with patient no-shows and dispatch inefficiency caused by fragmented, manual transport logistics.",
  "affected_problem_space": ["patient transport logistics", "appointment no-show reduction", "ambulance dispatch coordination"],
  "vendor_categories_who_benefit": ["AI-powered patient transport scheduling platforms", "logistics optimization SaaS for healthcare"],
  "apollo_keyword_candidates": ["patient transport logistics", "non-emergency medical transport software", "care coordination scheduling", "dispatch optimization healthcare"]
}

Example 2
Article: "HealthcareDive: Health system CIOs report AI-based clinical documentation tools cut physician charting time by 40% amid ongoing burnout concerns."
Output:
{
  "theme_summary": "Health systems are adopting AI documentation tools to reduce physician administrative burden and burnout.",
  "affected_problem_space": ["clinical documentation burden", "physician burnout", "EHR charting inefficiency"],
  "vendor_categories_who_benefit": ["AI clinical documentation / ambient scribe platforms", "EHR workflow automation vendors"],
  "apollo_keyword_candidates": ["ambient clinical documentation", "AI medical scribe", "EHR workflow automation", "physician burnout software"]
}

Example 3
Article: "HealthcareDive: Regional payer flags rising claims denial rates tied to inconsistent prior authorization documentation, prompting a search for automation vendors."
Output:
{
  "theme_summary": "Payers and providers are facing rising claims denials due to manual, inconsistent prior authorization processes.",
  "affected_problem_space": ["prior authorization workflow", "claims denial management", "utilization review documentation"],
  "vendor_categories_who_benefit": ["AI prior-authorization automation platforms", "claims optimization / denial-prevention SaaS"],
  "apollo_keyword_candidates": ["prior authorization automation", "claims denial prevention software", "utilization review AI", "healthcare claims optimization"]
}
""".strip()


def _build_prompt(article_text: str) -> str:
    return f"""You are a B2B market analyst identifying the underlying market theme
in a health-tech news article, for the purpose of finding OTHER vendor companies
who sell solutions into this same problem space.

CRITICAL: Do NOT extract or return the name of the company mentioned in the
article. Ignore the specific company entirely. Instead, extract the CATEGORY
of vendor that would sell a solution into the situation described.

{_FEW_SHOT}

Return ONLY valid JSON matching this schema, no prose, no markdown fences:
{{
  "theme_summary": string (1-2 sentences),
  "affected_problem_space": [string, ...],
  "vendor_categories_who_benefit": [string, ...],
  "apollo_keyword_candidates": [string, string, string, ...]  (3 to 6 short search phrases)
}}

Article:
\"\"\"
{article_text[:8000]}
\"\"\"
"""


async def extract_theme(article_text: str, campaign_id: int | None = None) -> ThemeExtraction:
    last_error = None
    for attempt in range(MAX_RETRIES):
        resp = await client.chat.completions.create(
            model=MODEL,
            temperature=0.1,
            messages=[{"role": "user", "content": _build_prompt(article_text)}],
            response_format={"type": "json_object"},
        )
        raw = resp.choices[0].message.content
        try:
            data = json.loads(raw)
            result = ThemeExtraction(**data)
        except Exception as e:
            last_error = e
            continue
        if campaign_id is not None:
            log_llm_usage(campaign_id, MODEL, "icp_theme_extraction",
                           resp.usage.prompt_tokens, resp.usage.completion_tokens)
        return result
    raise ValueError(f"Theme extraction failed after {MAX_RETRIES} attempts: {last_error}")
