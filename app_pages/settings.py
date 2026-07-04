"""Settings Page - Configure application settings."""

import streamlit as st

from api_client import health_keys
from config import get_approve_threshold, set_approve_threshold, get_review_threshold, set_review_threshold


def render_settings():
    st.title("⚙️ Settings")
    st.caption("Configure ICP settings, thresholds, pricing, and connection status")

    # API Connection Status
    st.subheader("🔌 Connection Status")
    health = health_keys()
    col1, col2 = st.columns(2)
    col1.metric("OpenAI", "✅ Connected" if health["openai"] else "❌ Disconnected")
    col2.metric("Apollo.io", "✅ Connected" if health["apollo"] else "❌ Disconnected")

    if not health["openai"] or not health["apollo"]:
        st.warning("⚠️ One or more services are not configured. Check your API keys.")
        st.write("**To fix:** Set environment variables or update .env:")
        st.code("""
OPENAI_API_KEY=sk-...
APOLLO_API_KEY=...
""", language="bash")

    # Scoring Thresholds
    st.subheader("📊 Candidate Scoring Thresholds")

    col1, col2 = st.columns(2)

    with col1:
        st.write("**Approve Threshold** (auto-approve above this score)")
        approve_threshold = st.slider(
            "Approval score",
            min_value=0,
            max_value=100,
            value=get_approve_threshold(),
            step=5,
            help="Companies scoring above this will be automatically approved"
        )
        if approve_threshold != get_approve_threshold():
            set_approve_threshold(approve_threshold)
            st.success(f"Updated to {approve_threshold}")

    with col2:
        st.write("**Review Threshold** (flag for review between thresholds)")
        review_threshold = st.slider(
            "Review score",
            min_value=0,
            max_value=100,
            value=get_review_threshold(),
            step=5,
            help="Companies between review and approve thresholds need human review"
        )
        if review_threshold != get_review_threshold():
            set_review_threshold(review_threshold)
            st.success(f"Updated to {review_threshold}")

    # Thresholds explanation
    st.info("""
    **How it works:**
    - Score ≥ Approve: Automatically approved ✅
    - Review ≤ Score < Approve: Needs human review 🔍
    - Score < Review: Automatically rejected ❌
    """)

    # About section
    st.subheader("ℹ️ About")
    st.write("""
    **Magical Genie** v1.0

    A news-triggered B2B micro-campaign engine that extracts sales intelligence from articles
    and finds verified leads to reach out to.

    **Features:**
    - 📰 Automated article scraping and analysis
    - 🎯 ICP-based lead qualification
    - 💬 Personalized outreach copy generation
    - 📊 Campaign performance tracking
    """)


# Call the render function when the page loads
render_settings()