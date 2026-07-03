"""
Generates personalized outreach copy per lead per channel (email, whatsapp,
google_ads), using the extracted context + the lead's seniority angle from the
product catalog. Runs in parallel via asyncio.gather so 12 leads takes ~4s,
not ~36s. One lead's failure never blocks the others (return_exceptions=True).
temperature=0.7 for creative variation.
"""
import asyncio
import json

from openai import AsyncOpenAI
from pydantic import BaseModel, Field, field_validator

from config import OPENAI_API_KEY, load_product_catalog
from services.tracker import build_tracking_url
from services.usage_tracker import log_llm_usage

client = AsyncOpenAI(api_key=OPENAI_API_KEY)
MODEL = "gpt-4o-mini"

CHANNELS = ["email", "whatsapp", "google_ads"]

MAX_GENERATION_RETRIES = 2

# channel -> constraints enforced in code, not just prompted for
CHANNEL_LIMITS = {
    "email": {"subject_line_max_chars": 60, "allow_subject_line": True},
    "whatsapp": {"body_max_words": 25, "allow_subject_line": False},
    "google_ads": {"body_max_chars": 90, "allow_subject_line": False},
}


class ChannelCopy(BaseModel):
    subject_line: str | None = Field(None, max_length=60)
    body_text: str

    @field_validator("body_text")
    @classmethod
    def not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError("body_text cannot be empty")
        return v


def _enforce_channel_constraints(channel: str, copy: ChannelCopy) -> None:
    """Raises ValueError if the copy violates this channel's hard limits.
    Called after LLM generation — prompting alone isn't reliable enough."""
    limits = CHANNEL_LIMITS[channel]

    if not limits["allow_subject_line"] and copy.subject_line:
        raise ValueError(f"{channel} must not have a subject_line")

    if "body_max_words" in limits:
        word_count = len(copy.body_text.split())
        if word_count > limits["body_max_words"]:
            raise ValueError(f"{channel} body_text has {word_count} words, max is {limits['body_max_words']}")

    if "body_max_chars" in limits:
        if len(copy.body_text) > limits["body_max_chars"]:
            raise ValueError(f"{channel} body_text has {len(copy.body_text)} chars, max is {limits['body_max_chars']}")


def _product_for(product_id: str) -> dict:
    for p in load_product_catalog():
        if p["product_id"] == product_id:
            return p
    raise ValueError(f"Unknown product_id: {product_id}")


def _prompt(channel: str, lead: dict, ctx: dict, product: dict, company_name: str) -> str:
    angle = product["seniority_angles"].get(lead["seniority"], product["seniority_angles"]["director"])
    constraints = {
        "email": "Subject line <=60 characters. Body: 3-5 short sentences, professional but not stiff.",
        "whatsapp": "No subject line. Body: <=25 words, casual, conversational, one clear CTA.",
        "google_ads": "No subject line. Body: <=90 characters, punchy headline-style ad copy.",
    }[channel]

    return f"""Write a {channel} outreach message to {lead['first_name']} {lead['last_name']},
{lead['title']} at {company_name}.

IMPORTANT — {company_name} is almost certainly NOT the company in the news item
below, and there is no reason to think {lead['first_name']} has seen it. Do NOT
say or imply "{company_name}" was mentioned in the news, was affected by it, or
already knows about it. Instead, use the news only as your own soft segue —
something like "we've been watching X trend in the industry" or "with Y shift
happening across the space" — then pivot into how that trend plausibly creates
the pain points below for a company like {company_name}.

Industry trend prompting this outreach: {ctx['catalyst']}
Pain points that trend plausibly creates for companies like this: {', '.join(ctx['pain_points'])}
Our product: {product['name']} — {product['description']}
Angle for this person's seniority ({lead['seniority']}): {angle}

Personalization: Lightly work in {company_name} and something that reads as
aware of {lead['title']}'s role/priorities, so the message feels tailored to
them specifically. Keep it subtle — don't explicitly call out that you looked
up their company or title (no "I noticed you're the X at Y"); just let it show
naturally in the framing and word choice.

Constraints: {constraints}

Return ONLY valid JSON, no markdown fences:
{{"subject_line": string or null, "body_text": string}}
"""


async def _generate_one(channel: str, lead: dict, ctx: dict, product: dict, company_name: str,
                         campaign_id: int | None = None) -> ChannelCopy:
    last_error = None
    for _ in range(MAX_GENERATION_RETRIES + 1):
        resp = await client.chat.completions.create(
            model=MODEL,
            temperature=0.7,
            messages=[{"role": "user", "content": _prompt(channel, lead, ctx, product, company_name)}],
            response_format={"type": "json_object"},
        )
        data = json.loads(resp.choices[0].message.content)
        copy = ChannelCopy(**data)
        try:
            _enforce_channel_constraints(channel, copy)
            if campaign_id is not None:
                log_llm_usage(campaign_id, MODEL, "copy_generation",
                             resp.usage.prompt_tokens, resp.usage.completion_tokens)
            return copy
        except ValueError as e:
            last_error = e
            continue
    raise last_error


async def generate_copy_for_lead(lead: dict, ctx: dict, company_name: str, campaign_id: int) -> dict:
    """Returns dict of channel -> {subject_line, body_text, tracking_url} or
    channel -> {"error": ...} for channels that failed. Never raises."""
    product = _product_for(ctx["product_id"])
    results = await asyncio.gather(
        *[_generate_one(ch, lead, ctx, product, company_name, campaign_id) for ch in CHANNELS],
        return_exceptions=True,
    )

    out = {}
    for channel, result in zip(CHANNELS, results):
        if isinstance(result, Exception):
            out[channel] = {"error": str(result)}
            continue
        out[channel] = {
            "subject_line": result.subject_line,
            "body_text": result.body_text,
            "tracking_url": build_tracking_url(campaign_id, lead.get("apollo_id", "unknown"), channel),
        }
    return out


async def generate_all_copy(leads: list[dict], ctx: dict, company_name: str, campaign_id: int) -> list[dict]:
    """Generates copy for all leads in parallel. A single lead's total failure
    (all channels erroring) still returns an entry with per-channel errors —
    it never removes the lead or crashes the batch."""
    per_lead_results = await asyncio.gather(
        *[generate_copy_for_lead(lead, ctx, company_name, campaign_id) for lead in leads],
        return_exceptions=True,
    )

    output = []
    for lead, result in zip(leads, per_lead_results):
        if isinstance(result, Exception):
            output.append({"lead": lead, "copy": {ch: {"error": str(result)} for ch in CHANNELS}})
        else:
            output.append({"lead": lead, "copy": result})
    return output
