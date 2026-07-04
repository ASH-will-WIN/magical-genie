"""New Campaign Page - Start a new campaign from a news article."""

import streamlit as st
from api_client import run_campaign

def render_new_campaign():
    st.title("🚀 New campaign")
    st.caption("Paste a news article URL to run the pipeline.")

    # Initialize session state for this page
    if "campaign_state" not in st.session_state:
        st.session_state.campaign_state = {
            "running": False,
            "campaign_id": None,
            "result": None,
            "current_step": "",
            "step_progress": 0,
            "show_manual_paste": False,
            "manual_text": ""
        }

    # URL input
    url = st.text_input("News article URL", placeholder="https://example.com/article",
                        help="Enter a URL to a news article about a company")

    # Run button
    col1, col2 = st.columns([1, 4])
    run_clicked = col1.button("Run Campaign", type="primary", disabled=st.session_state.campaign_state["running"])

    # Handle run click
    if run_clicked and url:
        st.session_state.campaign_state["running"] = True
        st.session_state.campaign_state["result"] = None
        st.session_state.campaign_state["current_step"] = "Starting..."
        st.session_state.campaign_state["step_progress"] = 0
        st.session_state.campaign_state["show_manual_paste"] = False
        st.session_state.campaign_state["manual_text"] = ""
        st.rerun()

    # Handle manual paste trigger
    if st.session_state.campaign_state["show_manual_paste"] and not st.session_state.campaign_state["manual_text"]:
        st.warning("Couldn't fetch that article automatically (paywall, bot-block, or similar). Paste the article text manually below.")
        manual_text = st.text_area("Article text", height=200, key="manual_text_area")
        if st.button("Run with pasted text") and manual_text:
            st.session_state.campaign_state["manual_text"] = manual_text
            st.session_state.campaign_state["current_step"] = "Starting with pasted text..."
            st.rerun()

    # Main processing logic
    if st.session_state.campaign_state["running"]:
        # Determine what to use for the campaign
        url_to_use = None
        manual_text_to_use = None

        if not st.session_state.campaign_state["show_manual_paste"]:
            url_to_use = st.session_state.campaign_state.get("url_for_run", "")
        else:
            manual_text_to_use = st.session_state.campaign_state["manual_text"]

        # Update progress
        st.session_state.campaign_state["current_step"] = "Scraping article..."
        st.session_state.campaign_state["step_progress"] = 10

        # Create placeholder for progress UI
        with st.container():
            st.info(f"🔄 {st.session_state.campaign_state['current_step']}")
            progress_bar = st.progress(st.session_state.campaign_state["step_progress"] / 100.0)

            # Simulate steps
            steps = [
                ("Scraping article...", 10),
                ("Extracting insights...", 30),
                ("Identifying target companies...", 50),
                ("Fetching leads...", 70),
                ("Generating personalized copy...", 90),
            ]

            for step_text, progress in steps:
                st.session_state.campaign_state["current_step"] = step_text
                st.session_state.campaign_state["step_progress"] = progress
                # Update UI
                with st.container():
                    st.info(f"🔄 {step_text}")
                    progress_bar.progress(progress / 100.0)
                # In a real app we'd wait for actual progress, but for now we'll just sleep briefly
                import time
                time.sleep(0.1)  # Simulate work

            # Actually call the backend
            try:
                result = run_campaign(url=url_to_use, manual_text=manual_text_to_use)

                # Handle the result
                status = result.get("status")
                if status == "paywalled":
                    # Show manual paste option
                    st.session_state.campaign_state["show_manual_paste"] = True
                    st.session_state.campaign_state["running"] = False
                    st.session_state.campaign_state["current_step"] = "Ready for manual input"
                    st.session_state.campaign_state["step_progress"] = 0
                    st.rerun()
                else:
                    # Process normal result
                    st.session_state.campaign_state["result"] = result
                    st.session_state.campaign_state["campaign_id"] = result.get("campaign_id")
                    st.session_state.campaign_state["running"] = False
                    st.session_state.campaign_state["current_step"] = "Completed!"
                    st.session_state.campaign_state["step_progress"] = 100
                    st.rerun()
            except Exception as e:
                st.session_state.campaign_state["running"] = False
                st.session_state.campaign_state["current_step"] = f"Error: {str(e)}"
                st.error(f"Campaign failed: {str(e)}")
                # Do not rerun here; let the script continue to show the error

    # Display results if available
    if st.session_state.campaign_state["result"] and not st.session_state.campaign_state["running"]:
        result = st.session_state.campaign_state["result"]
        # In a real app, we would display the result here
        # For now, we just show a success message
        st.success(f"Campaign completed! Got result: {result}")

# Call the render function when the page loads
render_new_campaign()