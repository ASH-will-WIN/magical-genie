"""Entrypoint for the Magical Genie control panel. Defines the sidebar
navigation and injects the shared theme CSS before any page renders."""
import streamlit as st

from styles import inject_base_styles

st.set_page_config(page_title="Magical Genie", page_icon=":material/auto_awesome:", layout="wide")
inject_base_styles()

page = st.navigation([
    st.Page("app_pages/dashboard.py", title="Dashboard", icon=":material/dashboard:"),
    st.Page("app_pages/new_campaign.py", title="New campaign", icon=":material/add_circle:"),
    st.Page("app_pages/review_queue.py", title="Review queue", icon=":material/fact_check:"),
    st.Page("app_pages/history.py", title="Calendar history", icon=":material/history:"),
    st.Page("app_pages/settings.py", title="Settings", icon=":material/tune:"),
    st.Page("app_pages/usage.py", title="Usage & cost", icon=":material/query_stats:"),
], position="sidebar")

page.run()