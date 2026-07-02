"""
Deterministic, non-LLM pre-filter: drops candidate companies that are
obviously outside the ICP on industry or headcount before spending an LLM
call scoring them. No network calls, no cost.

Only reads name/industry/employee_count from each candidate dict (domain is
carried through as an identity field but not used in filtering logic).
Missing/null industry or employee_count is NOT treated as exclusion grounds —
there's nothing to match against, and per CLAUDE.md's "failure is always
soft" principle, incomplete data shouldn't silently drop a candidate that
might be a great fit. Those cases are deferred to LLM scoring instead.
"""


def prefilter_candidates(candidates: list[dict], icp: dict) -> list[dict]:
    hard_exclude = [term.lower() for term in icp["hard_exclude_industries"]]
    min_emp = icp["size_band"]["employee_count_min"]
    max_emp = icp["size_band"]["employee_count_max"]

    kept = []
    for c in candidates:
        name = c.get("name", "<unknown>")
        industry = (c.get("industry") or "").strip().lower()
        employee_count = c.get("employee_count")

        if industry:
            excluded_term = next((term for term in hard_exclude if term in industry or industry in term), None)
            if excluded_term:
                print(f"[prefilter] DROP {name}: industry '{industry}' matches hard-exclude term '{excluded_term}'")
                continue
        else:
            print(f"[prefilter] {name}: industry unknown, not excluded on industry")

        if employee_count is None:
            print(f"[prefilter] KEEP {name}: employee_count unknown, size check skipped, deferring to LLM scoring")
            kept.append(c)
            continue

        if employee_count < min_emp or employee_count > max_emp:
            print(f"[prefilter] DROP {name}: employee_count {employee_count} outside band [{min_emp}, {max_emp}]")
            continue

        kept.append(c)

    print(f"[prefilter] {len(kept)}/{len(candidates)} candidates survived")
    return kept
