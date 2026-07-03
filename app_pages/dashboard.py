"""Dashboard Page - Overview of campaigns and metrics."""

import streamlit as st
from datetime import datetime

from services.usage_dashboard import (
    get_total_cost,
    get_cost_by_operation,
    get_cost_by_model,
    get_cost_per_campaign,
    get_apollo_credit_status
)
from config import get_approve_threshold, get_review_threshold
from styles import mono

def render_dashboard():
    st.title("📊 Dashboard")
    st.caption("Campaign summary, pending review count, spend vs. budget.")

    # Fetch data with error handling
    try:
        total_cost = get_total_cost()
        apollo_status = get_apollo_credit_status()
        cost_by_operation = get_cost_by_operation()
        cost_by_model = get_cost_by_model()
        recent_campaigns = get_cost_per_campaign()[:5]  # Latest 5 campaigns
    except Exception as e:
        st.error(f"Could not load dashboard data: {str(e)}")
        return

    # Account-wide summary metrics
    st.subheader("📊 Account-wide Summary")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total OpenAI Spend", f"${total_cost['openai_usd']:.2f}")
    with col2:
        st.metric("Total Apollo Credits", f"{total_cost['apollo_credits']:,}")
    with col3:
        st.metric("Total Estimated USD", f"${total_cost['total_usd']:.2f}")
    with col4:
        # Get campaign count from recent_campaigns length or separate call
        campaign_count = len(recent_campaigns) if recent_campaigns else 0
        st.metric("Recent Campaigns", campaign_count)

    # Apollo Credit Usage
    st.markdown("#### Apollo Credit Usage")
    progress_value = min(apollo_status["pct"] / 100.0, 1.0)
    st.progress(progress_value)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Credits Used", f"{apollo_status['used']:,}/{apollo_status['limit']:,}")
    with col2:
        st.metric("Credits Remaining", f"{apollo_status['remaining']:,}")
    with col3:
        st.metric("Usage Percentage", f"{apollo_status['pct']:.1f}%")

    if apollo_status["pct"] >= 90:
        st.error("⚠️ High usage — nearing monthly limit!")
    elif apollo_status["pct"] >= 75:
        st.warning("⚠️ Moderate usage — monitor closely")
    else:
        st.success("✅ Usage within normal range")

    # Cost by Operation Chart
    if cost_by_operation:
        st.subheader("⚙️ Cost by Operation")
        chart_data = {item["operation"]: item["total_usd"] for item in cost_by_operation}
        st.bar_chart(chart_data)
    else:
        st.info("No operation cost data available yet.")

    # Cost by Model Chart
    if cost_by_model:
        st.subheader("🤖 Cost by Model")
        chart_data = {item["model"]: item["total_usd"] for item in cost_by_model}
        st.bar_chart(chart_data)
    else:
        st.info("No model cost data available yet.")

    # Recent Campaigns Table
    st.subheader("🕒 Recent Campaigns")
    if recent_campaigns:
        # Format data for display
        formatted_campaigns = []
        for campaign in recent_campaigns:
            formatted_campaigns.append({
                "Campaign": f"#{campaign['campaign_id']}",
                "Run At": campaign['run_at'][:16] if len(campaign['run_at']) > 16 else campaign['run_at'],
                "Total Cost": f"${campaign['total_usd']:.2f}",
                "Apollo Credits": f"{campaign['apollo_credits']:,}",
                "Leads Found": campaign['lead_count'],
                "Cost/Lead": mono(f"${campaign['cost_per_lead']:.2f}" if campaign['cost_per_lead'] is not None else "—")
            })

        st.dataframe(
            formatted_campaigns,
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No campaign data available yet.")

# Call the render function when the page loads
render_dashboard()