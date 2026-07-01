"""
Extracts sales intelligence from article text using OpenAI structured outputs.
temperature=0.1 for deterministic extraction. Validates against product catalog
to prevent hallucinated product_id. Retries up to 3 times on schema failure.
"""
import json

from openai import AsyncOpenAI
from pydantic import BaseModel, Field, computed_field, field_validator

from config import OPENAI_API_KEY, URGENCY_RUBRIC, product_ids

client = AsyncOpenAI(api_key=OPENAI_API_KEY)

MODEL = "gpt-4o-mini"
MAX_RETRIES = 3


class CampaignContext(BaseModel):
    entity: str = Field(..., description="Company name the article is about")
    city: str | None = Field(None, description="City if mentioned")
    state: str | None = Field(None, description="State/province if mentioned")
    country: str | None = Field(None, description="Country if mentioned")
    catalyst: str = Field(..., description="The news event in one sentence, e.g. '$200M expansion announced'")
    pain_points: list[str] = Field(..., min_length=3, max_length=3, description="Exactly 3 business pain points this creates")
    product_id: str = Field(..., description="Best-matching product_id from the catalog")
    urgency_score: int = Field(..., ge=1, le=10)

    @computed_field
    @property
    def location(self) -> str | None:
        parts = [p for p in (self.city, self.state, self.country) if p]
        return ", ".join(parts) if parts else None

    @field_validator("product_id")
    @classmethod
    def validate_product(cls, v):
        valid = product_ids()
        if v not in valid:
            raise ValueError(f"product_id '{v}' not in catalog: {valid}")
        return v


def _build_prompt(article_text: str) -> str:
    catalog_summary = "\n".join(f"- {pid}" for pid in product_ids())
    return f"""You are a B2B sales intelligence analyst. Read the article below and extract
structured intelligence for outbound sales targeting.

Urgency scoring rubric:
{URGENCY_RUBRIC}

Available product_ids (choose exactly one, the best fit):
{catalog_summary}

Return ONLY valid JSON matching this schema, no prose, no markdown fences:
{{
  "entity": string,
  "city": string or null,
  "state": string or null,
  "country": string or null,
  "catalyst": string (one sentence),
  "pain_points": [string, string, string],
  "product_id": string (must be one of the listed product_ids),
  "urgency_score": integer 1-10
}}

Article:
\"\"\"
{article_text[:8000]}
\"\"\"
"""


async def extract_context(article_text: str) -> CampaignContext:
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
            return CampaignContext(**data)
        except Exception as e:
            last_error = e
            continue
    raise ValueError(f"Context extraction failed after {MAX_RETRIES} attempts: {last_error}")
