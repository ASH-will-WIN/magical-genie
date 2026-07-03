"""
Phase 7 (scaffolded, not yet wired into main.py's request flow).

Logs OpenAI token usage and Apollo credit usage per campaign so spend is
visible before it surprises anyone. Unknown model -> log warning, cost=$0,
continue (never raise — cost logging is best-effort, per CLAUDE.md).
"""
from database import get_conn, now_iso
import config
from config import get_llm_pricing, get_apollo_credit_costs


def log_llm_usage(campaign_id: int, model: str, operation: str, input_tokens: int, output_tokens: int):
    pricing = get_llm_pricing().get(model)
    if pricing is None:
        print(f"[usage_tracker] WARNING: unknown model '{model}', logging cost=$0")
        cost = 0.0
    else:
        cost = (input_tokens / 1_000_000) * pricing["input"] + (output_tokens / 1_000_000) * pricing["output"]

    try:
        with get_conn() as conn:
            conn.execute(
                """INSERT INTO usage_log
                   (campaign_id, service, model, operation, input_tokens, output_tokens, credits_used, cost_usd, created_at)
                   VALUES (?, 'openai', ?, ?, ?, ?, 0, ?, ?)""",
                (campaign_id, model, operation, input_tokens, output_tokens, cost, now_iso()),
            )
    except Exception as e:
        print(f"[usage_tracker] WARNING: failed to log LLM usage: {e}")


def log_apollo_usage(campaign_id: int, operation: str, emails: int = 0, phones: int = 0):
    costs = get_apollo_credit_costs()
    credits = emails * costs["email"] + phones * costs["phone"]
    try:
        with get_conn() as conn:
            conn.execute(
                """INSERT INTO usage_log
                   (campaign_id, service, model, operation, credits_used, cost_usd, created_at)
                   VALUES (?, 'apollo', NULL, ?, ?, 0, ?)""",
                (campaign_id, operation, credits, now_iso()),
            )
    except Exception as e:
        print(f"[usage_tracker] WARNING: failed to log Apollo usage: {e}")


def get_campaign_cost_summary(campaign_id: int) -> dict:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM usage_log WHERE campaign_id = ?", (campaign_id,)).fetchall()
    total_llm_cost = sum(r["cost_usd"] for r in rows if r["service"] == "openai")
    total_apollo_credits = sum(r["credits_used"] for r in rows if r["service"] == "apollo")
    return {"llm_cost_usd": total_llm_cost, "apollo_credits_used": total_apollo_credits}
