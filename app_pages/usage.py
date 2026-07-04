"""Usage & Cost Page - Monitor API usage and costs."""

import streamlit as st
import pandas as pd

from api_client import health_keys, list_campaigns, get_campaign
from config import get_llm_pricing, get_apollo_credit_cost_usd, APOLLO_CREDITS_LIMIT


def render_usage():
    st.title("📊 Usage & Cost")
    st.caption("Account-wide spend and Apollo credit usage.")

    health = health_keys()

    # Summary metrics
    st.subheader("💰 Cost Summary")

    try:
        campaigns = list_campaigns()

        total_llm_cost = 0.0
        total_apollo_cost = 0.0
        total_campaigns = len(campaigns)

        # Aggregate costs from campaigns
        for campaign in campaigns:
            try:
                detail = get_campaign(campaign["id"])
                if detail:
                    usage = detail.get("usage", {})
                    total_llm_cost += usage.get("llm_cost", 0.0)
                    total_apollo_cost += usage.get("apollo_cost", 0.0)
            except Exception:
                pass

        total_cost = total_llm_cost + total_apollo_cost

        col1, col2, col3 = st.columns(3)
        col1.metric("Total Spend", f"${total_cost:.2f}")
        col2.metric("OpenAI Spend", f"${total_llm_cost:.2f}")
        col3.metric("Apollo Spend", f"${total_apollo_cost:.2f}")

        # Apollo credit usage
        st.subheader("🎯 Apollo Credit Usage")

        col1, col2 = st.columns(2)
        with col1:
            st.metric("Credits Used", int(total_apollo_cost / get_apollo_credit_cost_usd()))
            st.metric("Monthly Limit", f"{APOLLO_CREDITS_LIMIT:,}")

        with col2:
            usage_pct = (total_apollo_cost / (APOLLO_CREDITS_LIMIT * get_apollo_credit_cost_usd())) * 100
            st.metric("Usage", f"{usage_pct:.1f}%")

            # Progress bar
            if usage_pct > 90:
                st.error(f"⚠️ Critical: {usage_pct:.1f}% of monthly budget used")
            elif usage_pct > 75:
                st.warning(f"⚠️ Warning: {usage_pct:.1f}% of monthly budget used")
            else:
                st.success(f"✅ Healthy: {usage_pct:.1f}% of monthly budget used")

        # Cost breakdown
        if total_campaigns > 0:
            st.subheader("📋 Cost by Campaign")

            cost_data = []
            for campaign in campaigns:
                try:
                    detail = get_campaign(campaign["id"])
                    if detail:
                        usage = detail.get("usage", {})
                        leads = len(detail.get("leads", []))
                        cost_per_lead = 0
                        if leads > 0:
                            cost_per_lead = usage.get("total_cost", 0.0) / leads

                        cost_data.append({
                            "Campaign ID": campaign["id"],
                            "OpenAI Cost": f"${usage.get('llm_cost', 0):.2f}",
                            "Apollo Cost": f"${usage.get('apollo_cost', 0):.2f}",
                            "Total": f"${usage.get('total_cost', 0):.2f}",
                            "Leads": leads,
                            "Cost/Lead": f"${cost_per_lead:.2f}"
                        })
                except Exception:
                    pass

            if cost_data:
                df = pd.DataFrame(cost_data)
                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.info("No campaigns with cost data yet.")
        else:
            st.info("Run a campaign to see cost data.")

    except Exception as e:
        st.error(f"Could not load usage data: {str(e)}")


# Call the render function when the page loads
render_usage()