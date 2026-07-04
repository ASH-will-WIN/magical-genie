"""History Page - View past campaigns and results."""

import streamlit as st
import pandas as pd
from datetime import datetime

from api_client import list_campaigns, get_campaign


def render_history():
    st.title("📊 History")
    st.caption("View past campaigns and their results.")

    # Initialize session state
    if "history_state" not in st.session_state:
        st.session_state.history_state = {
            "refresh_key": 0,
            "selected_campaign": None
        }

    # Refresh button
    if st.button("🔄 Refresh", help="Reload campaign history"):
        st.session_state.history_state["refresh_key"] += 1
        st.rerun()

    try:
        # Fetch campaigns
        campaigns = list_campaigns()
        if not campaigns:
            st.info("No campaigns yet. Start with the New Campaign page to run your first campaign.")
            return

        st.subheader(f"📋 {len(campaigns)} campaigns")

        # Display campaigns as a table
        campaign_data = []
        for campaign in campaigns:
            try:
                detail = get_campaign(campaign["id"])
                lead_count = len(detail.get("leads", [])) if detail else 0
                candidate_count = len(detail.get("candidates", [])) if detail else 0
            except Exception:
                lead_count = 0
                candidate_count = 0

            campaign_data.append({
                "Campaign ID": campaign["id"],
                "URL": campaign.get("url", "—")[:60] + "..." if len(campaign.get("url", "")) > 60 else campaign.get("url", "—"),
                "Status": campaign.get("status", "—"),
                "Leads Found": lead_count,
                "Candidates": candidate_count,
                "Created": campaign.get("created_at", "—")
            })

        if campaign_data:
            df = pd.DataFrame(campaign_data)
            st.dataframe(df, use_container_width=True, hide_index=True)

            # Show detail view for selected campaign
            st.subheader("Campaign Details")
            selected_id = st.selectbox(
                "Select a campaign to view details",
                options=[c["id"] for c in campaigns],
                format_func=lambda cid: f"Campaign {cid}",
                key=f"campaign_select_{st.session_state.history_state['refresh_key']}"
            )

            if selected_id:
                try:
                    campaign_detail = get_campaign(selected_id)
                    if campaign_detail:
                        col1, col2, col3 = st.columns(3)
                        col1.metric("Leads", len(campaign_detail.get("leads", [])))
                        col2.metric("Candidates", len(campaign_detail.get("candidates", [])))
                        col3.metric("Status", campaign_detail.get("status", "—"))

                        # Show context if available
                        context = campaign_detail.get("context", {})
                        if context:
                            st.write("**Campaign Context:**")
                            st.write(f"- Company: {context.get('entity', '—')}")
                            st.write(f"- Product: {context.get('product_id', '—')}")
                            st.write(f"- Urgency: {context.get('urgency_score', '—')}/10")
                            st.write(f"- Location: {context.get('location', '—')}")
                except Exception as e:
                    st.warning(f"Could not load campaign {selected_id} details: {str(e)}")
        else:
            st.info("No campaigns to display.")

    except Exception as e:
        st.error(f"Could not load campaign history: {str(e)}")


# Call the render function when the page loads
render_history()