"""
Scores a single Apollo-style candidate company against Reinvent's ICP using
an LLM. This is a judgment call, not deterministic (unlike prefilter.py) --
that's why it's a separate stage: prefilter removes obvious non-fits
cheaply, scoring ranks the ambiguous survivors. temperature=0.1. No
thresholds are applied here -- this module returns a raw 0-100 score and
lets a later handoff decide approve/review/reject cutoffs.
"""
import asyncio
import json

from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from config import OPENAI_API_KEY
from services.usage_tracker import log_llm_usage

client = AsyncOpenAI(api_key=OPENAI_API_KEY)
MODEL = "gpt-4o"
MAX_RETRIES = 3

# Below this length, a description carries no real signal (empty scrape,
# failed fetch, or a one-line stub) -- asking the LLM to judge company type
# from near-nothing just produces a confident-sounding guess anchored on the
# industry tag alone, which calibration showed flips inconsistently case to
# case. Short-circuit instead of calling the LLM on it.
MIN_DESCRIPTION_CHARS = 50


class CandidateScore(BaseModel):
    score: int = Field(..., ge=0, le=100)
    reason: str
    exclude: bool


def _build_prompt(company: dict, icp: dict) -> str:
    vertical_kw = ", ".join(icp["vertical_keywords"])
    tech_kw = ", ".join(icp["technology_signal_keywords"])
    trigger_kw = ", ".join(icp["buying_trigger_keywords"])

    return f"""You are scoring a company against Reinvent's Ideal Customer Profile (ICP).

ICP definition: small-to-mid-size health-tech SOFTWARE vendors who build or are
adding AI features to THEIR OWN product, where that product is sold as software
(a website, app, or platform) to healthcare organizations, patients, or providers.

This is NOT care-delivery organizations, NOT payers/insurance carriers, and NOT
pharma/biotech companies. Apply this distinction carefully using company TYPE,
not surface vocabulary:
- A company is a care-delivery organization ONLY if it directly employs
  clinicians who diagnose/treat patients, or operates physical
  hospitals/clinics/practices (e.g. a hospital system, a physician practice, a
  dental practice group). Marketing copy that mentions "patients," "care
  coordination," "appointment scheduling," or "front desk" does NOT by itself
  make a company a care-delivery organization -- most digital health SaaS
  vendors describe their product using exactly this kind of patient-facing
  language because their SOFTWARE automates those workflows FOR clinics,
  hospitals, or dental practices (i.e. the clinic/practice is the company's
  CUSTOMER, not the company itself). Read for who actually treats the patient:
  if it's a separate customer organization using this company's app/platform/
  AI agent, this company is a software vendor and fits the ICP, not an exclude.
- A company is a payer ONLY if it is itself a licensed insurance carrier /
  health plan selling insurance policies or administering claims as the payer
  of record.
- A company is pharma/biotech ONLY if it discovers, manufactures, or markets
  drugs/biologics as its core product.

HARD RULE: If this company is clearly, by the test above, a hospital, clinic,
physician/dental practice, insurance carrier, or pharma/biotech company (not a
software vendor selling to one), you MUST return score=0 and exclude=true,
regardless of any other signal. When genuinely ambiguous, prefer scoring it as
a software vendor over excluding it -- false exclusions are worse than a
mediocre score here, since a later step can still filter on score.

Before setting exclude=true, answer this exact question from the description
text: does the company's OWN description say THIS company employs
doctors/dentists/nurses/clinicians who treat patients, or that THIS company
operates a hospital/clinic/practice location? If the answer is no -- even if
the description says the product is used by, sold to, or serves hospitals,
clinics, dental practices, or patients -- you MUST set exclude=false. Who the
CUSTOMER is (a hospital, a dental group, a patient) is irrelevant to this
question; only what the company ITSELF is/does/employs matters.

Worked examples of this distinction:
- "Arini is the AI front desk for dental groups, trusted by hundreds of DSOs and
  private practices" -> Arini is a software vendor selling an AI product TO
  dental practices; Arini itself does not treat patients. exclude=false, score
  high on vertical/tech fit.
- "Careforce builds AI Workers that autonomously call and schedule patients for
  healthcare orgs" -> Careforce sells software/AI agents to healthcare
  organizations; Careforce itself does not treat patients. exclude=false, score
  high on vertical/tech fit.
- "Riverside Community Hospital is a 250-bed acute care hospital serving the
  Inland Empire" -> this company itself operates a hospital and treats
  patients. exclude=true, score=0.
- "Acme Family Practice is a physician-owned practice with 12 locations" -> this
  company itself is the clinic/practice. exclude=true, score=0.

score and exclude are INDEPENDENT fields. If exclude=false, you MUST still
assign a graded 0-100 score reflecting keyword match strength below -- do NOT
default to 0 just because the exclude question above was in play. Score
0-100 based on how well the company's description matches:
- Vertical fit keywords: {vertical_kw}
- Technology signal keywords: {tech_kw}
- Buying trigger keywords: {trigger_kw}

Company name: {company.get('name')}
Apollo industry tag: {company.get('industry')}
Apollo description: {(company.get('description') or '')[:6000]}

Return ONLY valid JSON, no markdown fences:
{{"score": integer 0-100, "reason": string (one sentence), "exclude": boolean}}
"""


async def score_candidate(company: dict, icp: dict, campaign_id: int | None = None) -> CandidateScore:
    description = (company.get("description") or "").strip()
    if len(description) < MIN_DESCRIPTION_CHARS:
        return CandidateScore(
            score=50,
            exclude=False,
            reason=(
                f"insufficient_data: description is only {len(description)} chars "
                "(scrape likely failed or returned nothing) -- not enough signal to "
                "judge company type or vertical fit; needs human review or a re-scrape, "
                "not an LLM guess anchored on the industry tag alone"
            ),
        )

    last_error = None
    for attempt in range(MAX_RETRIES):
        resp = await client.chat.completions.create(
            model=MODEL,
            temperature=0.1,
            messages=[{"role": "user", "content": _build_prompt(company, icp)}],
            response_format={"type": "json_object"},
        )
        raw = resp.choices[0].message.content
        try:
            data = json.loads(raw)
            result = CandidateScore(**data)
        except Exception as e:
            last_error = e
            continue
        if campaign_id is not None:
            log_llm_usage(campaign_id, MODEL, "icp_scoring",
                           resp.usage.prompt_tokens, resp.usage.completion_tokens)
        return result
    raise ValueError(f"Scoring failed for '{company.get('name')}' after {MAX_RETRIES} attempts: {last_error}")


async def score_candidates_batch(companies: list[dict], icp: dict, campaign_id: int | None = None) -> list[CandidateScore]:
    """Scores all companies in parallel (asyncio.gather pattern from
    services/copy.py). A single company's scoring failure never blocks the
    batch -- per CLAUDE.md's 'failure is always soft' rule, a failed score is
    represented as score=0/exclude=True with the error message as the
    reason, keeping the output list index-aligned 1:1 with the input list
    rather than raising or dropping the entry."""
    results = await asyncio.gather(
        *[score_candidate(c, icp, campaign_id) for c in companies],
        return_exceptions=True,
    )

    output = []
    for company, result in zip(companies, results):
        if isinstance(result, Exception):
            output.append(CandidateScore(score=0, exclude=True, reason=f"scoring_error: {result}"))
        else:
            output.append(result)
    return output
