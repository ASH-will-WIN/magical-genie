"""
Standalone calibration harness for ICP theme-extraction and scoring.
Run: python services/icp_matching/test_calibration.py

Not a pytest suite -- output is meant to be read by a human to judge whether
prefilter + scoring produce a clean positive/negative score separation, and
whether theme_extraction produces usable Apollo search keywords. No Apollo
calls, no DB, no pipeline wiring -- see handoff-1-icp-scoring-spec.md.
"""
import asyncio
import traceback

from config import load_icp_config
from services.scraper import scrape_article
from services.icp_matching.prefilter import prefilter_candidates
from services.icp_matching.scoring import score_candidates_batch
from services.icp_matching.theme_extraction import extract_theme

# --- Step A: labeled test set --------------------------------------------
# `description` is populated at runtime via scrape_article(url), never
# hand-written. `industry`/`employee_count` are manual best-effort real-world
# approximations (Apollo isn't called in this handoff) gathered via web
# search at implementation time -- not exact Apollo data.
#
# Note on MedHaul/Audact Health and "hospital & health care": a first run of
# this harness had "hospital & health care" in icp_config.json's
# hard_exclude_industries. That string is what Apollo-style directories
# often use for BOTH actual hospital systems (Kaiser Permanente) AND
# health-tech vendors that sell INTO the hospital vertical (MedHaul, Audact
# Health) -- the taxonomy doesn't distinguish "is a hospital" from "sells to
# hospitals." That run showed MedHaul/Audact getting wrongly dropped at
# prefilter before ever reaching the LLM, while the LLM scorer (which reads
# the actual description, not just the industry tag) correctly separated
# real vendors from real care-delivery orgs on every other case. So
# "hospital & health care" was removed from hard_exclude_industries --
# insurance/pharmaceuticals/medical practice stayed, since those showed zero
# false-positive collisions. Hospital systems like Kaiser Permanente are now
# expected to survive the deterministic prefilter and get correctly
# excluded by the LLM scorer instead, based on the description text.
LABELED_COMPANIES = [
    # --- positives: small health-tech AI software vendors ---
    {
        "name": "MedHaul", "url": "https://gomedhaul.com/",
        "industry": "hospital & health care", "employee_count": 15,
        "expected": "positive",
    },
    {
        "name": "Mediphant", "url": "https://mediphant.ai/",
        "industry": "information technology and services", "employee_count": 12,
        "expected": "positive",
    },
    {
        "name": "Audact Health", "url": "https://www.audacthealth.com/",
        "industry": "hospital & health care", "employee_count": 20,
        "expected": "positive",
    },
    {
        "name": "Careforce", "url": "https://careforce.ai/",
        "industry": "information technology and services", "employee_count": 20,
        "expected": "positive",
    },
    {
        "name": "Arini", "url": "https://www.arini.ai/",
        "industry": "information technology and services", "employee_count": 40,
        "expected": "positive",
    },
    # --- negatives ---
    {
        # hospital system (care delivery org). No longer hard-excluded on
        # industry (see note above) -- this now has to survive prefilter and
        # get correctly excluded by the LLM scorer reading the description.
        "name": "Kaiser Permanente", "url": "https://about.kaiserpermanente.org/who-we-are/fast-facts",
        "industry": "hospital & health care", "employee_count": 241462,
        "expected": "negative",
    },
    {
        # payer / insurance carrier -- should be excluded on industry
        "name": "UnitedHealthcare", "url": "https://www.uhc.com/employer",
        "industry": "insurance", "employee_count": 400000,
        "expected": "negative",
    },
    {
        # pharma -- should be excluded on industry
        "name": "Pfizer", "url": "https://www.pfizer.com/",
        "industry": "pharmaceuticals", "employee_count": 75000,
        "expected": "negative",
    },
    {
        # large (500+ employee) enterprise health-tech company -- industry
        # tag alone would NOT hard-exclude this (it's a software vendor, not
        # a care-delivery/payer/pharma org), so this specifically tests that
        # size_band does real filtering work independent of industry.
        "name": "Epic Systems", "url": "https://www.epic.com/about/",
        "industry": "information technology and services", "employee_count": 13000,
        "expected": "negative",
    },
    # --- hard negatives: real companies picked specifically because they
    # survive BOTH the industry and size prefilter checks, so they reach the
    # LLM scorer -- unlike every negative above, which the previous
    # calibration run showed getting caught (rightly or wrongly) before ever
    # reaching scoring. These test whether the scorer's software-vendor
    # judgment holds up on genuinely ambiguous middle-ground companies, not
    # just on clean hospital/payer/pharma cases.
    {
        # healthcare IT/value-based-care CONSULTING firm -- sells advisory
        # services and staff expertise, not a software product. Small
        # boutique shop (exact headcount not publicly listed; ~40 is a
        # best-effort estimate, not exact Apollo data). Industry tag
        # "management consulting" isn't in hard_exclude_industries and its
        # headcount is within size_band, so this should reach the scorer --
        # it should score low/exclude despite being small and health-adjacent,
        # because it has no software product of its own to sell.
        "name": "HSG Global", "url": "https://www.hsg.global/",
        "industry": "management consulting", "employee_count": 40,
        "expected": "negative",
    },
    {
        # small AI-enabled wearable medical DEVICE startup (EEG headband +
        # ML model for stroke detection), not a SaaS platform. Genuinely
        # ambiguous under icp_config.json's company_type.exclude entry
        # "medical device hardware manufacturer (unless software-attached)"
        # -- it IS software/AI-attached, so this tests whether the scorer
        # can navigate a case the ICP definition itself flags as a judgment
        # call, rather than a clean-cut exclude. Headcount is a rough
        # estimate for an early-stage (~$2M seed) startup, not exact data.
        "name": "Zeit Medical", "url": "https://www.zeitmedical.com/",
        "industry": "medical devices", "employee_count": 20,
        "expected": "negative",
    },
]

# --- Step D: real recent HealthcareDive article URLs ----------------------
ARTICLE_URLS = [
    "https://www.healthcaredive.com/news/digital-health-funding-concentrates-fewer-startups-q1-2026-rock-health/816777/",
    "https://www.healthcaredive.com/news/healthcare-ai-adoption-accelerates-provider-worries-deskilling-wolters-kluwer/821653/",
    "https://www.healthcaredive.com/news/oracle-launch-ai-patient-portal/759894/",
]


async def run_pipeline_on_labeled_set(icp: dict) -> list[tuple]:
    """Step B: scrape each labeled company, prefilter, then batch-score
    whatever survives. Returns rows for the printed table."""
    candidates = []
    descriptions = {}
    for entry in LABELED_COMPANIES:
        scrape = await scrape_article(entry["url"])
        if scrape.text:
            descriptions[entry["name"]] = scrape.text
        else:
            reason = "paywalled" if scrape.is_paywalled else (scrape.error or "unknown")
            print(f"[scrape] {entry['name']}: failed ({reason}), scoring will use empty description")
            descriptions[entry["name"]] = ""

        candidates.append({
            "name": entry["name"],
            "domain": entry["url"],
            "industry": entry["industry"],
            "employee_count": entry["employee_count"],
        })

    survivors = prefilter_candidates(candidates, icp)
    survivor_names = {c["name"] for c in survivors}

    scoring_input = [{**c, "description": descriptions[c["name"]]} for c in survivors]
    scores = await score_candidates_batch(scoring_input, icp) if scoring_input else []
    score_by_name = {c["name"]: s for c, s in zip(survivors, scores)}

    rows = []
    for entry in LABELED_COMPANIES:
        name = entry["name"]
        if name in survivor_names:
            s = score_by_name[name]
            rows.append((name, entry["expected"], "kept", s.score, s.reason, s.exclude))
        else:
            rows.append((name, entry["expected"], "dropped_at_prefilter", None, None, None))
    return rows


def print_table(rows: list[tuple]) -> None:
    header = f"{'name':<20} {'expected':<10} {'prefilter':<22} {'score':<6} {'exclude':<8} reason"
    print(header)
    print("-" * len(header))
    for name, expected, prefilter_result, score, reason, exclude in rows:
        print(f"{name:<20} {expected:<10} {prefilter_result:<22} {str(score):<6} {str(exclude):<8} {reason or ''}")


def print_separation(rows: list[tuple]) -> None:
    """Step C: min/max/mean per expected group. A prefilter-dropped company
    never reaches Apollo either, so it's counted as score=0 in this
    aggregate (noted explicitly per row when that happens)."""
    for group in ("positive", "negative"):
        scores = [row[3] if row[3] is not None else 0 for row in rows if row[1] == group]
        if scores:
            print(f"{group}: min={min(scores)} max={max(scores)} mean={sum(scores) / len(scores):.1f} n={len(scores)}")
        else:
            print(f"{group}: no candidates")


async def run_theme_extraction_demo() -> None:
    for url in ARTICLE_URLS:
        scrape = await scrape_article(url)
        if not scrape.text:
            reason = "paywalled" if scrape.is_paywalled else (scrape.error or "unknown")
            print(f"[theme] SKIP {url}: {reason}")
            continue
        theme = await extract_theme(scrape.text)
        print(f"\n=== {url} ===")
        print(theme.model_dump_json(indent=2))


async def main() -> None:
    icp = load_icp_config()

    print("=== Step B: labeled candidate scoring ===")
    try:
        rows = await run_pipeline_on_labeled_set(icp)
        print_table(rows)
    except Exception:
        print("[Step B] FAILED:")
        traceback.print_exc()
        rows = []

    print("\n=== Step C: score separation ===")
    try:
        if rows:
            print_separation(rows)
        else:
            print("skipped, no rows from Step B")
    except Exception:
        print("[Step C] FAILED:")
        traceback.print_exc()

    print("\n=== Step D: article theme extraction ===")
    try:
        await run_theme_extraction_demo()
    except Exception:
        print("[Step D] FAILED:")
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
