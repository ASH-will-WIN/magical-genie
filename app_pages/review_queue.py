# Review Queue Page - Review flagged companies and leads.

import streamlit as st
import pandas as pd
from datetime import datetime

from api_client import list_campaigns, get_campaign, approve_candidate, reject_candidate
from config import get_approve_threshold, get_review_threshold
from styles import signal_bar_html, mono

def render_review_queue():
    st.title("🔍 Review queue")
    st.caption("Candidates awaiting a human decision, across all campaigns.")

    # Initialize session state for this page
    if "review_state" not in st.session_state:
        st.session_state.review_state = {
            "refresh_key": 0,
            "selected_campaign": None,
            "candidates_data": [],
            "last_updated": None
        }

    # Refresh button
    col1, col2, col3 = st.columns([1, 1, 2])
    if col1.button("🔄 Refresh", help="Reload candidate data from server"):
        st.session_state.review_state["refresh_key"] += 1
        st.rerun()

    # Auto-refresh controls
    auto_refresh = col2.checkbox("Auto-refresh", value=False)
    if auto_refresh:
        refresh_interval = col3.selectbox(
            "Interval",
            options=[30, 60, 120, 300],
            index=1,
            format_func=lambda x: f"{x} seconds",
            key=f"refresh_interval_{st.session_state.review_state['refresh_key']}"
        )
        # Auto-refresh would be implemented with st.experimental_rerun() in a real app
        # For now we'll just show a message
        st.caption(f"⏱️ Auto-refresh every {refresh_interval}s (simulated)")

    try:
        # Fetch campaigns
        campaigns = list_campaigns()
        if not campaigns:
            st.info("No campaigns found. Run a campaign to see candidates here.")
            return

        # Collect all candidates needing review
        all_candidates = []
        candidates_by_campaign = {}

        for campaign in campaigns:
            campaign_id = campaign["id"]
            try:
                campaign_detail = get_campaign(campaign_id)
                candidates = campaign_detail.get("candidates", [])

                # Filter for needs_review candidates without human override
                needs_review = [
                    c for c in candidates
                    if c.get("bucket") == "needs_review" and not c.get("human_override")
                ]

                if needs_review:
                    candidates_by_campaign[campaign_id] = {
                        "campaign": campaign,
                        "candidates": needs_review
                    }
                    # Add to flat list with campaign context
                    for candidate in needs_review:
                        candidate_copy = candidate.copy()
                        candidate_copy["_campaign_id"] = campaign_id
                        candidate_copy["_campaign_url"] = campaign.get("url", "Unknown")
                        all_candidates.append(candidate_copy)

            except Exception as e:
                # If we can't get details for a specific campaign, skip it but continue
                st.warning(f"Could not load details for campaign {campaign_id}: {str(e)}")
                continue

        # Display summary
        total_needs_review = len(all_candidates)
        if total_needs_review > 0:
            st.subheader(f"📋 {total_needs_review} candidates awaiting review")

            # Campaign filter
            campaign_options = ["All Campaigns"] + [
                f"{cid}: {c['campaign'].get('url', 'Unknown')[:50]}..."
                for cid, c in candidates_by_campaign.items()
            ]
            selected_campaign_idx = st.selectbox(
                "Filter by campaign",
                options=range(len(campaign_options)),
                format_func=lambda x: campaign_options[x],
                key=f"campaign_filter_{st.session_state.review_state['refresh_key']}"
            )

            # Filter candidates based on selection
            if selected_campaign_idx == 0:  # All Campaigns
                filtered_candidates = all_candidates
            else:
                selected_campaign_id = list(candidates_by_campaign.keys())[selected_campaign_idx - 1]
                filtered_candidates = [
                    c for c in all_candidates
                    if c.get("_campaign_id") == selected_campaign_id
                ]

            # Sort options
            sort_by = st.selectbox(
                "Sort by",
                options=["Score (Low to High)", "Score (High to Low)", "Company Name", "Date Added"],
                index=0,
                key=f"sort_by_{st.session_state.review_state['refresh_key']}"
            )

            # Sort candidates
            if sort_by == "Score (Low to High)":
                filtered_candidates.sort(key=lambda x: x.get("score", 0))
            elif sort_by == "Score (High to Low)":
                filtered_candidates.sort(key=lambda x: x.get("score", 0), reverse=True)
            elif sort_by == "Company Name":
                filtered_candidates.sort(key=lambda x: x.get("company_name", "").lower())
            # Date Added would require a timestamp field

            # Display candidates
            if filtered_candidates:
                # Display as expandable cards
                for candidate in filtered_candidates:
                    with st.expander(
                        f"{candidate.get('company_name', 'Unknown')} "
                        f"({candidate.get('domain', '—')}) — "
                        f"Score {candidate.get('score', '—')} "
                        f"(Campaign: {candidate.get('_campaign_url', 'Unknown')[:30]}..."
                    ):
                        col1, col2 = st.columns([3, 1])

                        with col1:
                            st.write(f"**Company:** {candidate.get('company_name', '—')}")
                            st.write(f"**Domain:** {candidate.get('domain', '—')}")
                            st.write(f"**Score:** {candidate.get('score', '—')}/100")
                            st.write(f"**Reason:** {candidate.get('score_reason', '—')}")
                            if candidate.get("apollo_description"):
                                st.caption(candidate["apollo_description"][:200] + "...")

                        with col2:
                            if st.button("✅ Approve", key=f"approve_{candidate['id']}_{candidate['_campaign_id']}"):
                                # In a real app, we'd call the approve endpoint
                                result = approve_candidate(
                                    candidate["_campaign_id"],
                                    candidate["id"]
                                )
                                if result and not result.get("error"):
                                    st.success("Approved!")
                                    # Clear candidate from list (would refresh in real app)
                                    st.rerun()
                                else:
                                    st.error("Failed to approve")

                            if st.button("❌ Reject", key=f"reject_{candidate['id']}_{candidate['_campaign_id']}"):
                                # In a real app, we'd call the reject endpoint
                                result = reject_candidate(
                                    candidate["_campaign_id"],
                                    candidate["id"]
                                )
                                if result and not result.get("error"):
                                    st.success("Rejected!")
                                    # Clear candidate from list (would refresh in real app)
                                    st.rerun()
                                else:
                                    st.error("Failed to reject")

                            # Show signal bar
                            score = candidate.get("score", 0)
                            bucket = "needs_review"
                            st.markdown(
                                f'<div class="gs-signal-track"><div class="text-align: none; "> <div class="gs-signal-fill" style="width:{score}%; background:#E8AA4C;"></div></div><span class="gs-mono" style="font-size:0.8rem; color:#E8AA4C;">{score}/100</span>',
                                unsafe_allow_html=True
                            )
            else:
                st.info("No candidates match the current filters.")
        else:
            st.success("🎉 All candidates have been reviewed! Great job.")

    except Exception as e:
        st.error(f"Could not load review queue: {str(e)}")
        st.exception(e)

# Call the render function when the page loads
render_review_queue()