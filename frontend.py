"""
Streamlit UI. Uses session_state so results persist across reruns without
re-calling the API on every widget interaction. Never shows raw stack traces.
"""
import io

import pandas as pd
import requests
import streamlit as st

from config import MAX_LEAD_FETCH_COMPANIES, MAX_LEADS_PER_CAMPAIGN
from services.usage_dashboard import (
    get_apollo_credit_status,
    get_cost_by_model,
    get_cost_by_operation,
    get_cost_per_campaign,
    get_total_cost,
)

API_BASE = "http://localhost:8000"

st.set_page_config(page_title="Magical Genie", page_icon="🧞", layout="wide")
st.title("🧞 Magical Genie")

if "result" not in st.session_state:
    st.session_state.result = None
if "show_manual_paste" not in st.session_state:
    st.session_state.show_manual_paste = False
if "pending_message" not in st.session_state:
    st.session_state.pending_message = None

campaign_tab, usage_tab = st.tabs(["🧞 Campaign", "💰 Usage & Cost"])

# ---------------------------------------------------------------------------
# Campaign tab
# ---------------------------------------------------------------------------
with campaign_tab:
    st.caption("Paste a news article about a company → get verified leads + personalized outreach copy.")

    url = st.text_input("News article URL", placeholder="https://...")

    col1, col2 = st.columns([1, 4])
    run_clicked = col1.button("Run Campaign", type="primary")

    if run_clicked and url:
        with st.spinner("Scraping, analyzing, finding leads, writing copy... (15-30s)"):
            try:
                resp = requests.post(f"{API_BASE}/campaign", json={"url": url}, timeout=90)
                resp.raise_for_status()
                st.session_state.result = resp.json()
                st.session_state.show_manual_paste = st.session_state.result.get("status") in ("paywalled", "scrape_failed")
            except requests.RequestException as e:
                st.error(f"Couldn't reach the backend. Is `uvicorn main:app --reload` running? ({e})")
                st.session_state.result = None

    if st.session_state.show_manual_paste:
        if st.session_state.result.get("status") == "scrape_failed":
            st.warning("Couldn't fetch that article automatically (paywall, bot-block, or similar). Paste the article text manually below.")
        else:
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
        company_summaries = result.get("company_summaries") or []
        leads_found_by_domain = {cs["domain"]: cs["leads_found"] for cs in company_summaries if cs.get("domain")}
        fetch_status_by_domain = {cs["domain"]: cs["status"] for cs in company_summaries if cs.get("domain")}

        search_stats = result.get("search_stats")
        if search_stats:
            st.subheader("🔬 Search Funnel")
            cc = search_stats["cluster_counts"]
            f1, f2, f3, f4, f5 = st.columns(5)
            f1.metric("Article-only", cc.get("article-only", 0))
            f2.metric("ICP-only", cc.get("icp-only", 0))
            f3.metric("Blended", cc.get("blended", 0))
            f4.metric("Unique (deduped)", search_stats["unique_candidates_found"])
            f5.metric("Passed Prefilter", search_stats["prefilter_kept"],
                      delta=f"-{search_stats['prefilter_dropped']} dropped", delta_color="inverse")
            st.caption("Raw org-search hit counts per cluster (pre-dedupe) → unique companies → survivors of the free deterministic prefilter, before LLM scoring.")

        # Cap-hit visibility: surface plainly if the testing caps stopped
        # lead-fetching partway through, and which companies were skipped.
        skipped_for_cap = [cs for cs in company_summaries if cs["status"] == "skipped_cap"]
        if skipped_for_cap:
            cap_reason = skipped_for_cap[0].get("reason") or "testing cap reached"
            st.warning(
                f"🛑 **Lead-fetch cap hit** — {cap_reason}. "
                f"{len(skipped_for_cap)} approved company(s) were never fetched: "
                + ", ".join(f"{cs['company_name']} ({cs['domain']})" for cs in skipped_for_cap)
            )

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
                                if data.get("company_summary"):
                                    st.session_state.result["company_summaries"] = \
                                        st.session_state.result.get("company_summaries", []) + [data["company_summary"]]
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
                    fetch_status = fetch_status_by_domain.get(c["domain"])
                    if fetch_status == "fetched":
                        fetch_note = f" → 🎯 {leads_found_by_domain[c['domain']]} lead(s) found"
                    elif fetch_status == "zero_leads":
                        fetch_note = " → 0 leads found at this company"
                    elif fetch_status == "skipped_cap":
                        fetch_note = " → ⏭️ skipped, lead-fetch cap reached"
                    elif fetch_status == "error":
                        fetch_note = " → ⚠️ lead-fetch errored"
                    else:
                        fetch_note = " → not yet fetched"
                    st.write(f"✅ **{c['company_name']}** ({c['domain']}) — score {c.get('score')} — {c.get('score_reason') or ''}{fetch_note}")
                for c in rejected:
                    reason = c.get("score_reason") or c.get("prefilter_reason") or "—"
                    st.write(f"❌ **{c['company_name']}** ({c['domain']}) — score {c.get('score')} — {reason}")

        if candidates:
            with st.expander(f"📊 Full company funnel — every candidate found ({len(candidates)})"):
                funnel_rows = []
                for c in candidates:
                    decision = c.get("human_override") or c["bucket"]
                    fetch_status = fetch_status_by_domain.get(c["domain"], "—")
                    leads_n = leads_found_by_domain.get(c["domain"])
                    funnel_rows.append({
                        "Company": c["company_name"],
                        "Domain": c["domain"],
                        "Industry": c.get("apollo_industry") or "—",
                        "Employees": c.get("apollo_employee_count") or "—",
                        "Prefilter": c["prefilter_result"],
                        "Score": c.get("score") if c.get("score") is not None else "—",
                        "Decision": decision,
                        "Fetch Status": fetch_status,
                        "Leads Found": leads_n if leads_n is not None else "—",
                        "Reason": c.get("score_reason") or c.get("prefilter_reason") or "—",
                    })
                st.dataframe(pd.DataFrame(funnel_rows), use_container_width=True, hide_index=True)

        leads = result.get("leads", [])
        if leads:
            st.subheader(f"🎯 {len(leads)} Leads")

            # Group by the company the lead actually works at (not the article's
            # company) so it's clear at a glance where each lead came from.
            leads_by_company: dict[str, list] = {}
            for item in leads:
                key = item["lead"].get("company_name") or "Unknown company"
                leads_by_company.setdefault(key, []).append(item)

            csv_rows = []

            for company_key, items in leads_by_company.items():
                company_domain = items[0]["lead"].get("domain") or "—"
                st.markdown(f"#### 🏢 {company_key}  `{company_domain}` — {len(items)} lead(s)")

                for item in items:
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
                            "company": lead.get("company_name") or "—",
                            "domain": lead.get("domain") or "—",
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

        # Section C: inline cost summary for the campaign just run — visible
        # here without switching tabs, per the handoff's real-time-visibility ask.
        campaign_id = result.get("campaign_id")
        if campaign_id is not None:
            st.divider()
            st.subheader("💰 This Campaign's Cost")
            current_cost = get_total_cost(campaign_id)
            lead_count = len(leads)
            cost_per_lead = current_cost["total_usd"] / lead_count if lead_count > 0 else None

            c1, c2, c3 = st.columns(3)
            c1.metric("Total Cost", f"${current_cost['total_usd']:.4f}")
            c2.metric("Apollo Credits", current_cost["apollo_credits"])
            c3.metric("Cost per Lead", f"${cost_per_lead:.4f}" if cost_per_lead is not None else "—")

# ---------------------------------------------------------------------------
# Usage & Cost tab — always rendered, regardless of campaign state
# ---------------------------------------------------------------------------
with usage_tab:
    st.subheader("📊 Account-wide Summary")

    total_cost = get_total_cost()
    apollo_status = get_apollo_credit_status()

    try:
        resp = requests.get(f"{API_BASE}/campaigns", timeout=10)
        campaigns = resp.json() if resp.status_code == 200 else []
        campaign_count = len(campaigns) if isinstance(campaigns, list) else 0
    except requests.RequestException:
        campaign_count = "—"

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total OpenAI Spend", f"${total_cost['openai_usd']:.4f}")
    c2.metric("Total Apollo Credits", total_cost["apollo_credits"])
    c3.metric("Total Estimated USD", f"${total_cost['total_usd']:.4f}")
    c4.metric("Campaigns Run", campaign_count)

    st.markdown("#### Apollo Credit Usage")
    progress_value = min(apollo_status["pct"] / 100.0, 1.0)
    st.progress(progress_value)

    c1, c2, c3 = st.columns(3)
    c1.metric("Credits Used", f"{apollo_status['used']}/{apollo_status['limit']}")
    c2.metric("Credits Remaining", apollo_status["remaining"])
    c3.metric("Usage Percentage", f"{apollo_status['pct']:.1f}%")

    if apollo_status["pct"] >= 90:
        st.error("⚠️ High usage — nearing monthly limit!")
    elif apollo_status["pct"] >= 75:
        st.warning("⚠️ Moderate usage — monitor closely")
    else:
        st.success("✅ Usage within normal range")

    if MAX_LEADS_PER_CAMPAIGN is not None or MAX_LEAD_FETCH_COMPANIES is not None:
        st.info("💡 **Testing caps are currently active** — actual spend is suppressed below what a full run would cost.")

    st.divider()

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("#### Cost by Operation")
        cost_by_op = get_cost_by_operation()
        if cost_by_op:
            st.bar_chart({item["operation"]: item["total_usd"] for item in cost_by_op})
        else:
            st.info("No usage logged yet.")

    with col_b:
        st.markdown("#### Cost by Model")
        cost_by_model = get_cost_by_model()
        if cost_by_model:
            st.bar_chart({item["model"]: item["total_usd"] for item in cost_by_model})
        else:
            st.info("No usage logged yet.")

    st.divider()

    st.subheader("📈 Per-campaign Breakdown")
    cost_per_campaign = get_cost_per_campaign()
    if cost_per_campaign:
        df_data = [
            {
                "Campaign": f"#{item['campaign_id']}",
                "Run At": item["run_at"],
                "Article": (item["article_url"][:50] + "...") if len(item["article_url"]) > 50 else item["article_url"],
                "Total Cost (USD)": f"${item['total_usd']:.4f}",
                "LLM Cost by Model": ", ".join(
                    f"{model}: ${cost:.4f}" for model, cost in item["model_costs"].items()
                ) if item["model_costs"] else "—",
                "Apollo Credits": item["apollo_credits"],
                "Leads Found": item["lead_count"],
                "Cost per Lead (USD)": f"${item['cost_per_lead']:.4f}" if item["cost_per_lead"] is not None else "—",
            }
            for item in cost_per_campaign
        ]
        st.dataframe(pd.DataFrame(df_data), use_container_width=True, hide_index=True)
    else:
        st.info("No campaigns run yet.")
