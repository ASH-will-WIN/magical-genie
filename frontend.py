"""
Streamlit UI. Uses session_state so results persist across reruns without
re-calling the API on every widget interaction. Never shows raw stack traces.
"""
import io

import pandas as pd
import requests
import streamlit as st

API_BASE = "http://localhost:8000"

st.set_page_config(page_title="Magical Genie", page_icon="🧞", layout="wide")
st.title("🧞 Magical Genie")
st.caption("Paste a news article about a company → get verified leads + personalized outreach copy.")

if "result" not in st.session_state:
    st.session_state.result = None
if "show_manual_paste" not in st.session_state:
    st.session_state.show_manual_paste = False
if "pending_message" not in st.session_state:
    st.session_state.pending_message = None

url = st.text_input("News article URL", placeholder="https://...")

col1, col2 = st.columns([1, 4])
run_clicked = col1.button("Run Campaign", type="primary")

if run_clicked and url:
    with st.spinner("Scraping, analyzing, finding leads, writing copy... (15-30s)"):
        try:
            resp = requests.post(f"{API_BASE}/campaign", json={"url": url}, timeout=90)
            resp.raise_for_status()
            st.session_state.result = resp.json()
            st.session_state.show_manual_paste = st.session_state.result.get("status") == "paywalled"
        except requests.RequestException as e:
            st.error(f"Couldn't reach the backend. Is `uvicorn main:app --reload` running? ({e})")
            st.session_state.result = None

if st.session_state.show_manual_paste:
    st.warning("This looks paywalled. Paste the article text manually below.")
    manual_text = st.text_area("Article text", height=200)
    if st.button("Run with pasted text") and manual_text:
        with st.spinner("Analyzing, finding leads, writing copy..."):
            try:
                resp = requests.post(f"{API_BASE}/campaign", json={"manual_text": manual_text}, timeout=90)
                resp.raise_for_status()
                st.session_state.result = resp.json()
                st.session_state.show_manual_paste = False
            except requests.RequestException as e:
                st.error(f"Backend error: {e}")

result = st.session_state.result

if st.session_state.pending_message:
    st.warning(st.session_state.pending_message)
    st.session_state.pending_message = None

if result:
    status = result.get("status")

    if status == "scrape_failed":
        st.error(f"Couldn't fetch that article. {result.get('error', '')}")
    elif status == "extraction_failed":
        st.error("Couldn't extract intelligence from that article. Try a different URL or paste text manually.")
    elif status == "no_domain":
        st.warning("Couldn't resolve a domain for this company, so no leads were found. Context below is still useful.")
    elif status == "zero_leads":
        st.info("No verified leads found at this company (valid result, not an error).")
    elif status == "no_candidates":
        st.warning("Couldn't identify a market theme for this article, so no ICP candidates could be found. Context below is still useful.")
    elif status == "awaiting_review":
        st.info("Some candidate companies need review before leads can be fetched — see the Needs Review queue below.")

    ctx = result.get("context")
    if ctx:
        st.subheader("📰 Campaign Intelligence")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Company", ctx["entity"])
        c2.metric("Product Match", ctx["product_id"])
        c3.metric("Urgency", f"{ctx['urgency_score']}/10")
        c4.metric("Location", ctx.get("location") or "—")
        st.write(f"**Catalyst:** {ctx['catalyst']}")
        st.write("**Pain points:** " + " · ".join(ctx["pain_points"]))

    theme = result.get("theme")
    if theme:
        st.write(f"**Market theme:** {theme['theme_summary']}")

    candidates = result.get("candidates") or []
    needs_review = [c for c in candidates if c["bucket"] == "needs_review" and not c.get("human_override")]
    approved = [c for c in candidates if c["bucket"] == "approved" or c.get("human_override") == "approved"]
    rejected = [c for c in candidates if c["bucket"] in ("rejected", "dropped_at_prefilter") or c.get("human_override") == "rejected"]

    if needs_review:
        st.subheader(f"🔍 Needs Review ({len(needs_review)})")
        campaign_id = result["campaign_id"]
        for c in needs_review:
            with st.expander(f"{c['company_name']} ({c['domain']}) — score {c['score']}"):
                st.write(f"**Industry:** {c.get('apollo_industry') or '—'}  |  **Employees:** {c.get('apollo_employee_count') or '—'}")
                st.write(f"**Score reason:** {c.get('score_reason') or '—'}")
                if c.get("apollo_description"):
                    st.caption(c["apollo_description"][:500])
                b1, b2 = st.columns(2)
                if b1.button("✅ Approve", key=f"approve_{c['id']}"):
                    with st.spinner(f"Fetching leads for {c['company_name']}..."):
                        try:
                            resp = requests.post(f"{API_BASE}/campaigns/{campaign_id}/candidates/{c['id']}/approve", timeout=60)
                            resp.raise_for_status()
                            data = resp.json()
                            c["human_override"] = "approved"
                            st.session_state.result["leads"] = st.session_state.result.get("leads", []) + data.get("results", [])
                            if data.get("message"):
                                st.session_state.pending_message = data["message"]
                            st.rerun()
                        except requests.RequestException as e:
                            st.error(f"Approve failed: {e}")
                if b2.button("❌ Reject", key=f"reject_{c['id']}"):
                    try:
                        resp = requests.post(f"{API_BASE}/campaigns/{campaign_id}/candidates/{c['id']}/reject", timeout=30)
                        resp.raise_for_status()
                        c["human_override"] = "rejected"
                        st.rerun()
                    except requests.RequestException as e:
                        st.error(f"Reject failed: {e}")

    if approved or rejected:
        with st.expander(f"📋 Auto-decided candidates ({len(approved)} approved, {len(rejected)} rejected)"):
            for c in approved:
                st.write(f"✅ **{c['company_name']}** ({c['domain']}) — score {c.get('score')} — {c.get('score_reason') or ''}")
            for c in rejected:
                reason = c.get("score_reason") or c.get("prefilter_reason") or "—"
                st.write(f"❌ **{c['company_name']}** ({c['domain']}) — score {c.get('score')} — {reason}")

    leads = result.get("leads", [])
    if leads:
        st.subheader(f"🎯 {len(leads)} Leads")
        csv_rows = []

        for item in leads:
            lead = item["lead"]
            copy = item["copy"]
            name = f"{lead.get('first_name', '')} {lead.get('last_name', '')}".strip()
            with st.expander(f"{name} — {lead.get('title', 'Unknown title')} ({lead.get('seniority', '')})"):
                st.write(f"📧 {lead.get('email') or '—'}  |  🔗 {lead.get('linkedin') or '—'}")
                tabs = st.tabs(["Email", "WhatsApp", "Google Ads"])
                for tab, channel in zip(tabs, ["email", "whatsapp", "google_ads"]):
                    with tab:
                        c = copy.get(channel, {})
                        if "error" in c:
                            st.error(f"Copy generation failed for this channel: {c['error']}")
                        else:
                            if c.get("subject_line"):
                                st.markdown(f"**Subject:** {c['subject_line']}")
                            st.code(c.get("body_text", ""), language=None)

            for channel in ["email", "whatsapp", "google_ads"]:
                c = copy.get(channel, {})
                csv_rows.append({
                    "name": name,
                    "title": lead.get("title"),
                    "seniority": lead.get("seniority"),
                    "email": lead.get("email"),
                    "linkedin": lead.get("linkedin"),
                    "channel": channel,
                    "subject_line": c.get("subject_line"),
                    "body_text": c.get("body_text"),
                    "tracking_url": c.get("tracking_url"),
                })

        if csv_rows:
            df = pd.DataFrame(csv_rows)
            buf = io.StringIO()
            df.to_csv(buf, index=False)
            st.download_button("⬇️ Download CSV (leads + copy)", buf.getvalue(), file_name=f"campaign_{result['campaign_id']}.csv", mime="text/csv")
