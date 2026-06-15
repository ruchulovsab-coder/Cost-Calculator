"""
Step 8 — Cost, Expenses, Pricing & Output Dashboard

Cost inputs (transition, expenses, SLA, margin, reporting currency) are collected
first; then the entire model is computed once via engine.compute_full_model so the
dashboard, Excel and PDF exports can never disagree. Every output panel below
reads from that single `model` dict.
"""
import streamlit as st
import pandas as pd

try:
    import plotly.graph_objects as go
    import plotly.express as px
    PLOTLY_OK = True
except ImportError:
    PLOTLY_OK = False

from modules.inputs.steps_1_2 import page_header, section_hdr, callout
from modules.calculations.engine import compute_full_model, convert_to_currency
from modules.state.session_manager import build_model_state
from config.settings import (
    ALL_ROLES, CATEGORY_SUBLABELS, CURRENCY_SYMBOLS, REPORTING_CURRENCIES,
)
from utils.formatters import fmt_currency, fmt_pct, fmt_hours


def _render_cost_inputs():
    """Render all cost-side input widgets (they write to session_state)."""
    # ── Transition ────────────────────────────────────────────
    section_hdr("🚀 Transition & Onboarding Cost")
    trans_inc = st.radio("Include Transition / Onboarding Cost?", ["Yes", "No"],
                         index=0 if st.session_state.get("transition_included") == "Yes" else 1,
                         key="transition_included", horizontal=True)
    transition_total_cost = 0.0
    if trans_inc == "Yes":
        val = float(st.session_state.get("transition_total_cost", 0.0))
        total_tc = st.number_input(
            "Total Transition Cost (One-time, charged independently)", min_value=0.0, step=10000.0, format="%.0f",
            value=val if val else None, placeholder="0",
            key="transition_total_cost_input",
        )
        transition_total_cost = total_tc or 0.0
        st.info(f"One-Time Transition Cost: **₹{transition_total_cost:,.0f}** (not included in the monthly delivery cost)")
    st.session_state["transition_total_cost"] = transition_total_cost

    # ── Additional cost components ────────────────────────────
    st.divider()
    section_hdr("📝 Additional Cost Components")
    add_costs = st.session_state.additional_costs
    to_remove = []
    for i, row in enumerate(add_costs):
        name_val = row["name"]
        if name_val in ["Shift Allowance", "On-Call Allowance"]:
            st.markdown(f"**{name_val}**")
            ac1, ac2, ac3 = st.columns(3)
            p_val = float(row.get("people", 0)); h_val = float(row.get("hours", 0)); r_val = float(row.get("rate", 0.0))
            p = ac1.number_input("Number of People", min_value=0.0, step=1.0, value=p_val if p_val else None, placeholder="0", key=f"ac_p_{i}")
            h = ac2.number_input("Monthly Hours per Person", min_value=0.0, step=10.0, value=h_val if h_val else None, placeholder="0", key=f"ac_h_{i}")
            r = ac3.number_input("Cost per Shift/Hr (INR)", min_value=0.0, step=100.0, value=r_val if r_val else None, placeholder="0", key=f"ac_r_{i}")
            p = p or 0.0; h = h or 0.0; r = r or 0.0
            cost_v = p * h * r
            add_costs[i].update({"people": p, "hours": h, "rate": r, "cost": cost_v})
            st.markdown(f"<div style='margin-bottom: 15px; font-size: 0.85rem;'>Calculated Cost: <b>₹{cost_v:,.0f}</b></div>", unsafe_allow_html=True)
        else:
            ac1, ac2, ac3 = st.columns([4, 2.5, 0.8])
            if row.get("custom"):
                add_costs[i]["name"] = ac1.text_input("Name", value=row["name"], key=f"addcost_name_{i}", label_visibility="collapsed")
            else:
                ac1.markdown(f"*{row['name']}*")
            val = float(row["cost"])
            cost_v = ac2.number_input("cost", min_value=0.0, step=100.0, format="%.0f",
                                      value=val if val else None, placeholder="0",
                                      key=f"addcost_{i}", label_visibility="collapsed", help="Monthly cost in INR")
            add_costs[i]["cost"] = cost_v or 0.0
            if row.get("custom"):
                if ac3.button("🗑️", key=f"del_addcost_{i}"):
                    to_remove.append(i)
            else:
                ac3.markdown("")
    for idx in reversed(to_remove):
        add_costs.pop(idx)
    if st.button("➕ Add Cost Item", type="secondary"):
        add_costs.append({"name": "Custom Cost", "cost": 0.0, "custom": True})
        st.rerun()
    st.info(f"Total Additional Expenses: **₹{sum(r['cost'] for r in add_costs):,.0f}**")

    # ── SLA provision ─────────────────────────────────────────
    st.divider()
    section_hdr("⚖️ SLA Penalty Provision")
    sla_inc = st.radio("Include SLA Penalty Provision?", ["Yes", "No"],
                       index=0 if st.session_state.get("sla_provision_included") == "Yes" else 1,
                       key="sla_provision_included", horizontal=True)
    if sla_inc == "Yes":
        val = float(st.session_state.get("sla_provision_pct", 2.0))
        st.number_input("SLA Provision (% of Delivery Cost before provision)",
                        min_value=0.0, max_value=15.0, step=0.5, format="%.1f",
                        value=val if val else None, placeholder="0", key="sla_provision_pct")

    # ── Target margin ─────────────────────────────────────────
    st.divider()
    section_hdr("📈 Target Gross Margin")
    val_margin = float(st.session_state.get("target_margin_pct", 20.0))
    st.number_input(
        "**Target Gross Margin (%)** *(required)*",
        min_value=0.0, max_value=80.0, step=0.5, format="%.1f",
        value=val_margin if val_margin else None, placeholder="0", key="target_margin_pct",
        help="Selling Price = Delivery Cost ÷ (1 − Margin%). E.g., 20% margin on ₹100 cost → ₹125 selling price.",
    )

    # ── Reporting currency + FX ───────────────────────────────
    st.divider()
    section_hdr("💱 Reporting Currency")
    cur = st.selectbox(
        "Display the final estimate in", REPORTING_CURRENCIES,
        index=REPORTING_CURRENCIES.index(st.session_state.get("reporting_currency", "INR"))
        if st.session_state.get("reporting_currency", "INR") in REPORTING_CURRENCIES else 0,
        key="reporting_currency",
        help="All internal calculations stay in INR; only the output view is converted.",
    )
    # Currencies that need an INR exchange rate: the reporting currency plus any
    # non-INR currencies quoted in the uploaded rate card.
    needed = set()
    if cur != "INR":
        needed.add(cur)
    df = st.session_state.get("rate_card_df")
    if df is not None and "rate currency" in df.columns:
        for c in df["rate currency"].dropna().astype(str).str.upper().str.strip().unique():
            if c and c != "INR":
                needed.add(c)
    fx = dict(st.session_state.get("exchange_rates", {}) or {})
    if needed:
        st.caption("Enter exchange rates (used for both rate-card conversion and the reporting view):")
        cols = st.columns(min(len(needed), 4))
        for i, c in enumerate(sorted(needed)):
            with cols[i % len(cols)]:
                rate = st.number_input(f"1 {c} = ? INR", min_value=0.0, step=0.5, format="%.4f",
                                       value=float(fx.get(c, 0.0)) or None, placeholder="0",
                                       key=f"fx_{c}")
                if rate:
                    fx[c] = float(rate)
    st.session_state["exchange_rates"] = fx
    if cur != "INR" and not fx.get(cur):
        callout(f"⚠️ Enter an exchange rate for {cur} above to convert the output.", "warning")


def render_step8() -> bool:
    page_header(8, "Cost, Pricing & Output Dashboard",
                "Configure expenses and margin, then view the complete results.")

    _render_cost_inputs()

    # ── Single compute ────────────────────────────────────────
    try:
        model = compute_full_model(build_model_state())
    except ValueError as e:
        callout(f"❌ {e}", "error")
        return False
    st.session_state["_model"] = model  # reused by exports / scenarios

    currency = model["reporting_currency"]
    fx = dict(st.session_state.get("exchange_rates", {}) or {}); fx.setdefault("INR", 1.0)
    def conv(v): return convert_to_currency(v, currency, fx)

    cost_result   = model["cost_result"]
    price_result  = model["price_result"]
    fte_result    = model["fte_result"]
    resource_costs = model["resource_costs"]
    total_fte     = model["total_fte"]
    total_effort  = model["total_effort"]
    margin        = price_result["margin_pct"]

    # ══════════════════════════════════════════════════════════
    # OUTPUT DASHBOARD
    # ══════════════════════════════════════════════════════════
    st.divider()
    st.markdown(
        '<div style="text-align:center; font-size:1.5rem; font-weight:700; color:#0D1B2A; '
        'padding:8px 0;">📊 OUTPUT DASHBOARD</div>', unsafe_allow_html=True)

    # ── Resource cost summary ─────────────────────────────────
    st.divider()
    section_hdr("💰 Resource Cost Summary")
    rc_rows_html = ""
    for role in ALL_ROLES:
        r = resource_costs[role]
        rc_rows_html += (
            f"<tr><td>{role}</td><td>{r['genus'] or '—'}</td>"
            f"<td class='r'>{r['fte']:.1f}</td><td class='r'>{r['billed_hours']:,.0f}</td>"
            f"<td class='r'>₹{r['rate_inr']:,.0f}</td><td class='r'>₹{r['cost_inr']:,.0f}</td></tr>"
        )
    rc_rows_html += (
        f"<tr class='total-row'><td colspan='5'><strong>Total Resource Cost</strong></td>"
        f"<td class='r'><strong>₹{model['total_resource_cost']:,.0f}</strong></td></tr>"
    )
    st.markdown(f"""
    <table class="styled-table">
      <thead><tr><th>Role</th><th>Genus</th><th class="r">Required FTE</th>
        <th class="r">Billed Hours</th><th class="r">Rate (INR/hr)</th><th class="r">Cost (INR)</th>
      </tr></thead><tbody>{rc_rows_html}</tbody></table>""", unsafe_allow_html=True)

    # ── Executive summary ─────────────────────────────────────
    st.divider()
    section_hdr("📊 Executive Summary")
    base_effort = model["base_effort"]
    cont_hours  = model["contingency"]["contingency_hours"]

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Effort",  fmt_hours(total_effort))
    m2.metric("Total FTE",     f"{total_fte:.1f}")
    m3.metric("Delivery Cost", fmt_currency(conv(cost_result["total_delivery_cost"]), currency))
    m4.metric("Selling Price", fmt_currency(conv(price_result["selling_price"]), currency))
    m5, m6, m7, m8 = st.columns(4)
    m5.metric("Base Effort",    fmt_hours(base_effort))
    m6.metric("Contingency",    fmt_hours(cont_hours))
    m7.metric("Gross Margin",   fmt_pct(margin))
    m8.metric("Coverage Model", st.session_state.get("coverage_model", "—"))

    # ── Effort breakdown + charts ─────────────────────────────
    st.divider()
    section_hdr("⏱️ Effort Breakdown")
    effort_sources = model["effort_sources"]
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**By Source (hrs)**")
        if PLOTLY_OK:
            fig = px.bar(x=list(effort_sources.values()), y=list(effort_sources.keys()),
                         orientation="h", color_discrete_sequence=["#00C4B4"],
                         text=[f"{v:.0f}" for v in effort_sources.values()])
            fig.update_layout(height=300, margin=dict(l=0, r=0, t=10, b=10),
                              xaxis_title="Hours", yaxis_title="", showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
        else:
            for k, v in effort_sources.items():
                st.write(f"{k}: {v:.1f} hrs")
    with col2:
        st.markdown("**By Role (hrs)**")
        role_hours = model["role_hours"]
        nz = {r: role_hours.get(r, 0) for r in ALL_ROLES if role_hours.get(r, 0) > 0}
        if PLOTLY_OK and nz:
            fig2 = px.pie(values=list(nz.values()), names=list(nz.keys()),
                          color_discrete_sequence=px.colors.qualitative.Set2)
            fig2.update_layout(height=300, margin=dict(l=0, r=0, t=10, b=10))
            st.plotly_chart(fig2, use_container_width=True)

    eff_rows = ""
    for k, v in effort_sources.items():
        pct = (v / total_effort * 100) if total_effort > 0 else 0
        eff_rows += f"<tr><td>{k}</td><td class='r'>{v:.1f}</td><td class='r'>{pct:.1f}%</td></tr>"
    eff_rows += (f"<tr class='total-row'><td><strong>Total Effort</strong></td>"
                 f"<td class='r'><strong>{total_effort:.1f}</strong></td>"
                 f"<td class='r'><strong>100.0%</strong></td></tr>")
    st.markdown(f"""
    <table class="styled-table"><thead><tr><th>Source</th><th class="r">Hours</th><th class="r">%</th></tr></thead>
      <tbody>{eff_rows}</tbody></table>""", unsafe_allow_html=True)

    # ── Resolution detail ─────────────────────────────────────
    st.divider()
    section_hdr("🎯 Resolution Detail — Tickets, Minutes & Role Hours")
    CATEGORY_DISPLAY = [("alerts", "🚨 Monitoring Alerts"), ("service_requests", "📋 Service Requests"),
                        ("incidents", "🔥 Incidents"), ("changes", "🔄 Change Requests")]
    res_rows = ""
    for cat_key, cat_label in CATEGORY_DISPLAY:
        cat_data = st.session_state.get(cat_key, {})
        for label in CATEGORY_SUBLABELS[cat_key]:
            row = cat_data.get(label, {})
            cnt = row.get("count", 0); mins = row.get("minutes", 0)
            l1p = row.get("L1_pct", 0); l2p = row.get("L2_pct", 0); l3p = row.get("L3_pct", 0)
            total_h = (cnt * mins) / 60.0
            l1h = total_h * l1p / 100; l2h = total_h * l2p / 100; l3h = total_h * l3p / 100
            res_rows += (
                f"<tr><td>{cat_label}</td><td>{label}</td>"
                f"<td class='r'>{cnt:,}</td><td class='r'>{mins:.0f}</td><td class='r'>{total_h:.1f}</td>"
                f"<td class='r'>{l1p:.0f}% ({l1h:.1f}h)</td><td class='r'>{l2p:.0f}% ({l2h:.1f}h)</td>"
                f"<td class='r'>{l3p:.0f}% ({l3h:.1f}h)</td></tr>"
            )
    st.markdown(f"""
    <table class="styled-table"><thead><tr>
        <th>Category</th><th>Severity</th><th class="r">Count</th><th class="r">Min/Ticket</th>
        <th class="r">Total Hrs</th><th class="r">L1 %(Hrs)</th><th class="r">L2 %(Hrs)</th><th class="r">L3 %(Hrs)</th>
      </tr></thead><tbody>{res_rows}</tbody></table>""", unsafe_allow_html=True)

    # ── FTE summary ───────────────────────────────────────────
    st.divider()
    section_hdr("👥 FTE Summary")
    fte_rows = ""
    for role in ALL_ROLES:
        r = fte_result.get(role, {})
        cov = "✅" if r.get("coverage_applied") else "—"
        fte_rows += (f"<tr><td>{role}</td><td class='r'>{r.get('hours', 0):.1f}</td>"
                     f"<td class='r'>{r.get('raw_fte', 0):.3f}</td><td style='text-align:center'>{cov}</td>"
                     f"<td class='r'><strong>{r.get('final_fte', 0):.1f}</strong></td></tr>")
    fte_rows += (f"<tr class='total-row'><td><strong>TOTAL</strong></td><td class='r'></td>"
                 f"<td class='r'></td><td></td><td class='r'><strong>{total_fte:.1f}</strong></td></tr>")
    st.markdown(f"""
    <table class="styled-table"><thead><tr>
        <th>Role</th><th class="r">Hours</th><th class="r">Raw FTE</th>
        <th style="text-align:center">Cov. Applied</th><th class="r">Final FTE</th>
      </tr></thead><tbody>{fte_rows}</tbody></table>""", unsafe_allow_html=True)

    # ── Cost waterfall ────────────────────────────────────────
    st.divider()
    section_hdr("📉 Cost Waterfall")
    wf_labels = ["Resource Cost"]; wf_values = [cost_result["resource_cost"]]; wf_measure = ["relative"]
    if cost_result["transition_cost"] > 0:
        wf_labels.append("Transition Cost"); wf_values.append(cost_result["transition_cost"]); wf_measure.append("relative")
    for row in st.session_state.additional_costs:
        if row["cost"] > 0:
            wf_labels.append(row["name"]); wf_values.append(row["cost"]); wf_measure.append("relative")
    if cost_result["sla_provision"] > 0:
        wf_labels.append("SLA Provision"); wf_values.append(cost_result["sla_provision"]); wf_measure.append("relative")
    wf_labels.append("Total Delivery Cost"); wf_values.append(cost_result["total_delivery_cost"]); wf_measure.append("total")
    wf_labels.append("Gross Profit"); wf_values.append(price_result["gross_profit"]); wf_measure.append("relative")
    wf_labels.append("Selling Price"); wf_values.append(price_result["selling_price"]); wf_measure.append("total")
    wf_conv = [conv(v) for v in wf_values]
    if PLOTLY_OK:
        fig_wf = go.Figure(go.Waterfall(
            orientation="v", measure=wf_measure, x=wf_labels, y=wf_conv,
            connector={"line": {"color": "rgba(42, 138, 138, 0.5)"}},
            increasing={"marker": {"color": "#00C4B4"}},
            decreasing={"marker": {"color": "#E74C3C"}},
            totals={"marker": {"color": "#1A5F6A"}},
            texttemplate="%{y:,.0f}", textposition="outside"))
        fig_wf.update_layout(showlegend=False, height=420, margin=dict(l=0, r=0, t=20, b=40),
                             yaxis_title=f"Amount ({currency})")
        st.plotly_chart(fig_wf, use_container_width=True)

    # ── Financial summary ─────────────────────────────────────
    st.divider()
    section_hdr("📋 Financial Summary")
    fin_items = [
        ("Total Resource Cost",       cost_result["resource_cost"],       False),
        ("Total Additional Expenses", cost_result["additional_expenses"], False),
        ("SLA Penalty Provision",     cost_result["sla_provision"],       False),
        ("TOTAL DELIVERY COST",       cost_result["total_delivery_cost"], True),
        ("Gross Margin %",            None,                               False),
        ("Gross Profit",              price_result["gross_profit"],       False),
        ("MONTHLY SELLING PRICE",     price_result["selling_price"],      True),
    ]
    if model["transition_cost"] > 0:
        fin_items.append(("ONE-TIME TRANSITION COST", model["transition_cost"], True))
    fin_rows = ""
    for label, inr_val, total in fin_items:
        cls = " class='total-row'" if total else ""
        b = "<strong>" if total else ""; eb = "</strong>" if total else ""
        if inr_val is None:
            fin_rows += f"<tr{cls}><td>{b}{label}{eb}</td><td class='r'>—</td><td class='r'>{b}{fmt_pct(margin)}{eb}</td></tr>"
        else:
            fin_rows += (f"<tr{cls}><td>{b}{label}{eb}</td><td class='r'>{b}₹{inr_val:,.0f}{eb}</td>"
                         f"<td class='r'>{b}{fmt_currency(conv(inr_val), currency)}{eb}</td></tr>")
    st.markdown(f"""
    <table class="styled-table"><thead><tr><th>Component</th><th class="r">INR</th><th class="r">{currency}</th></tr></thead>
      <tbody>{fin_rows}</tbody></table>""", unsafe_allow_html=True)

    return True
