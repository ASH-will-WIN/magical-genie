"""
Article extraction: httpx (async fetch) + trafilatura (DOM-aware text extraction).
Detects likely paywalls so the caller can fall back to a manual-paste UI path.
"""
import httpx
import trafilatura

PAYWALL_MARKERS = [
    "subscribe to continue",
    "subscription required",
    "you have reached your limit",
    "create a free account to continue",
    "sign in to continue reading",
]

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


class ScrapeResult:
    def __init__(self, text: str | None, is_paywalled: bool, error: str | None = None):
        self.text = text
        self.is_paywalled = is_paywalled
        self.error = error


async def scrape_article(url: str) -> ScrapeResult:
    try:
        async with httpx.AsyncClient(timeout=15, headers={"User-Agent": USER_AGENT}, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            html = resp.text
    except httpx.HTTPError as e:
        return ScrapeResult(text=None, is_paywalled=False, error=f"fetch_failed: {e}")

    extracted = trafilatura.extract(html, include_comments=False, include_tables=False)

    if not extracted or len(extracted.strip()) < 200:
        lowered = (html or "").lower()
        if any(marker in lowered for marker in PAYWALL_MARKERS):
            return ScrapeResult(text=None, is_paywalled=True)
        return ScrapeResult(text=None, is_paywalled=False, error="extraction_too_short")

    return ScrapeResult(text=extracted, is_paywalled=False)
