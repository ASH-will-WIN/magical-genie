"""
Usage dashboard module for Phase 7: Cost & Usage Dashboard
Provides aggregation functions for displaying usage and cost statistics.
"""

from typing import Optional, List, Dict, Any
from database import get_conn
from config import LLM_PRICING, APOLLO_CREDIT_COSTS, APOLLO_CREDIT_COST_USD


def get_total_cost(campaign_id: Optional[int] = None) -> Dict[str, float]:
    """
    Get total cost across all campaigns or for a specific campaign.

    Args:
        campaign_id: Optional campaign ID to filter by. None means all campaigns.

    Returns:
        Dictionary with openai_usd, apollo_credits, apollo_usd, and total_usd
    """
    with get_conn() as conn:
        if campaign_id is not None:
            rows = conn.execute(
                "SELECT * FROM usage_log WHERE campaign_id = ?",
                (campaign_id,)
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM usage_log").fetchall()

    openai_cost = 0.0
    apollo_credits = 0

    for row in rows:
        if row["service"] == "openai":
            # Calculate cost from tokens at query time (ignore stored cost_usd)
            model = row["model"]
            input_tokens = row["input_tokens"]
            output_tokens = row["output_tokens"]

            pricing = LLM_PRICING.get(model)
            if pricing:
                cost = (input_tokens / 1_000_000) * pricing["input"] + \
                       (output_tokens / 1_000_000) * pricing["output"]
                openai_cost += cost
            # If model unknown, cost remains 0 (consistent with usage_tracker)
        elif row["service"] == "apollo":
            apollo_credits += row["credits_used"]

    # Calculate Apollo cost in USD
    apollo_usd = apollo_credits * APOLLO_CREDIT_COST_USD

    return {
        "openai_usd": round(openai_cost, 4),
        "apollo_credits": apollo_credits,
        "apollo_usd": round(apollo_usd, 4),
        "total_usd": round(openai_cost + apollo_usd, 4)
    }


def get_cost_by_operation(campaign_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Get cost breakdown by operation type.

    Args:
        campaign_id: Optional campaign ID to filter by. None means all campaigns.

    Returns:
        List of dictionaries with operation, call_count, total_input_tokens,
        total_output_tokens, and total_usd
    """
    with get_conn() as conn:
        if campaign_id is not None:
            rows = conn.execute(
                """SELECT operation, model, input_tokens, output_tokens
                   FROM usage_log
                   WHERE service = 'openai' AND campaign_id = ?""",
                (campaign_id,)
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT operation, model, input_tokens, output_tokens
                   FROM usage_log
                   WHERE service = 'openai'"""
            ).fetchall()

    # Group by operation
    operation_stats = {}
    for row in rows:
        operation = row["operation"]
        if operation not in operation_stats:
            operation_stats[operation] = {
                "operation": operation,
                "call_count": 0,
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "total_usd": 0.0
            }

        stats = operation_stats[operation]
        stats["call_count"] += 1
        stats["total_input_tokens"] += row["input_tokens"]
        stats["total_output_tokens"] += row["output_tokens"]

        # Calculate cost for this entry
        model = row["model"]
        pricing = LLM_PRICING.get(model)
        if pricing:
            cost = (row["input_tokens"] / 1_000_000) * pricing["input"] + \
                   (row["output_tokens"] / 1_000_000) * pricing["output"]
            stats["total_usd"] += cost

    # Convert to list and round
    result = []
    for stats in operation_stats.values():
        result.append({
            "operation": stats["operation"],
            "call_count": stats["call_count"],
            "total_input_tokens": stats["total_input_tokens"],
            "total_output_tokens": stats["total_output_tokens"],
            "total_usd": round(stats["total_usd"], 4)
        })

    # Sort by operation name for consistent ordering
    result.sort(key=lambda x: x["operation"])
    return result


def get_cost_by_model(campaign_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Get cost breakdown by model.

    Args:
        campaign_id: Optional campaign ID to filter by. None means all campaigns.

    Returns:
        List of dictionaries with model, call_count, total_tokens, and total_usd
    """
    with get_conn() as conn:
        if campaign_id is not None:
            rows = conn.execute(
                """SELECT model, input_tokens, output_tokens
                   FROM usage_log
                   WHERE service = 'openai' AND campaign_id = ?""",
                (campaign_id,)
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT model, input_tokens, output_tokens
                   FROM usage_log
                   WHERE service = 'openai'"""
            ).fetchall()

    # Group by model
    model_stats = {}
    for row in rows:
        model = row["model"]
        if model not in model_stats:
            model_stats[model] = {
                "model": model,
                "call_count": 0,
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "total_tokens": 0,
                "total_usd": 0.0
            }

        stats = model_stats[model]
        stats["call_count"] += 1
        stats["total_input_tokens"] += row["input_tokens"]
        stats["total_output_tokens"] += row["output_tokens"]
        stats["total_tokens"] = stats["total_input_tokens"] + stats["total_output_tokens"]

        # Calculate cost for this entry
        pricing = LLM_PRICING.get(model)
        if pricing:
            cost = (row["input_tokens"] / 1_000_000) * pricing["input"] + \
                   (row["output_tokens"] / 1_000_000) * pricing["output"]
            stats["total_usd"] += cost

    # Convert to list and round
    result = []
    for stats in model_stats.values():
        result.append({
            "model": stats["model"],
            "call_count": stats["call_count"],
            "total_tokens": stats["total_tokens"],
            "total_usd": round(stats["total_usd"], 4)
        })

    # Sort by model name for consistent ordering
    result.sort(key=lambda x: x["model"])
    return result


def get_cost_per_campaign() -> List[Dict[str, Any]]:
    """
    Get cost breakdown per campaign.

    Returns:
        List of dictionaries with campaign_id, article_url, run_at, total_usd,
        apollo_credits, lead_count, cost_per_lead, and model_costs (per-LLM
        model USD breakdown for that campaign)
    """
    with get_conn() as conn:
        # Get campaigns with their URLs
        campaigns = conn.execute(
            """SELECT c.id, c.url, c.created_at
               FROM campaigns c
               ORDER BY c.created_at DESC"""
        ).fetchall()

        result = []
        for campaign in campaigns:
            campaign_id = campaign["id"]
            article_url = campaign["url"] or "Unknown"
            run_at = campaign["created_at"]

            # Get usage stats for this campaign
            usage_rows = conn.execute(
                """SELECT service, model, input_tokens, output_tokens, credits_used
                   FROM usage_log
                   WHERE campaign_id = ?""",
                (campaign_id,)
            ).fetchall()

            # Calculate costs
            openai_cost = 0.0
            apollo_credits = 0
            model_costs: Dict[str, float] = {}

            for row in usage_rows:
                if row["service"] == "openai":
                    model = row["model"]
                    input_tokens = row["input_tokens"]
                    output_tokens = row["output_tokens"]

                    pricing = LLM_PRICING.get(model)
                    if pricing:
                        cost = (input_tokens / 1_000_000) * pricing["input"] + \
                               (output_tokens / 1_000_000) * pricing["output"]
                        openai_cost += cost
                        model_costs[model] = model_costs.get(model, 0.0) + cost
                    else:
                        model_costs.setdefault(model, 0.0)
                elif row["service"] == "apollo":
                    apollo_credits += row["credits_used"]

            # Get lead count for this campaign
            lead_count = conn.execute(
                "SELECT COUNT(*) as count FROM leads WHERE campaign_id = ?",
                (campaign_id,)
            ).fetchone()["count"]

            # Calculate Apollo cost in USD
            apollo_usd = apollo_credits * APOLLO_CREDIT_COSTS["email"] * 0.0206
            total_usd = openai_cost + apollo_usd

            # Calculate cost per lead
            cost_per_lead = None
            if lead_count > 0:
                cost_per_lead = total_usd / lead_count

            result.append({
                "campaign_id": campaign_id,
                "article_url": article_url,
                "run_at": run_at,
                "total_usd": round(total_usd, 4),
                "apollo_credits": apollo_credits,
                "lead_count": lead_count,
                "cost_per_lead": round(cost_per_lead, 4) if cost_per_lead is not None else None,
                "model_costs": {model: round(cost, 4) for model, cost in model_costs.items()}
            })

        # Sort by total cost descending (most expensive first)
        result.sort(key=lambda x: x["total_usd"], reverse=True)
        return result


def get_apollo_credit_status() -> Dict[str, Any]:
    """
    Get Apollo credit usage status vs. monthly limit.

    Returns:
        Dictionary with used, limit, remaining, and pct (percentage used)
    """
    # Get total Apollo credits used across all time
    with get_conn() as conn:
        apollo_credits_used = conn.execute(
            """SELECT SUM(credits_used) as total
               FROM usage_log
               WHERE service = 'apollo'"""
        ).fetchone()["total"] or 0

    # Get monthly limit from config (already loaded from env)
    from config import APOLLO_CREDITS_LIMIT
    credits_limit = APOLLO_CREDITS_LIMIT

    credits_remaining = max(0, credits_limit - apollo_credits_used)
    pct_used = (apollo_credits_used / credits_limit * 100) if credits_limit > 0 else 0

    return {
        "used": apollo_credits_used,
        "limit": credits_limit,
        "remaining": credits_remaining,
        "pct": round(pct_used, 2)
    }