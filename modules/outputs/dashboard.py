"""
Step 8 — Cost, Expenses, Pricing & Output Dashboard
Everything from exchange rates through to multi-currency selling price and charts.
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
from modules.calculations.engine import (
    convert_rate_to_inr, calc_resource_cost, calc_total_delivery_cost,
    calc_selling_price, convert_to_currency, build_exchange_rates,
    calc_category_hours, calc_patching_effort, calc_base_effort,
    calc_overhead_hours, calc_contingency, calc_all_ticket_role_hours,
)
from config.settings import ALL_ROLES, DEFAULT_CURRENCIES, CURRENCY_SYMBOLS
from utils.formatters import fmt_currency, fmt_pct, fmt_hours


def render_step8() -> bool:
    page_header(8, "Cost, Pricing & Output Dashboard",
                "Configure expenses, margin — then view complete results.")

    # ══════════════════════════════════════════════════════════
    # ══════════════════════════════════════════════════════════
    # SECTION A: CURRENCY CONFIGURATION
    # ══════════════════════════════════════════════════════════
    # Currency configuration removed per user request. Hardcoded to INR.
    all_fx = {"INR": 1.0}
    st.session_state["_all_fx"] = all_fx
    
    rate_currency = "INR"
    role_genus = st.session_state.get("role_genus", {})
    df_rate_card = st.session_state.get("rate_card_df")
    
    raw_rates = st.session_state.get("_role_rates_raw", {})
    
    # Dynamically pull rates as fallback
    if df_rate_card is not None:
        filtered = df_rate_card[df_rate_card["country"].str.lower().str.contains("india", na=False)]
        if len(filtered) == 0:
            filtered = df_rate_card # fallback if India not found
            
        for role, genus in role_genus.items():
            if genus and role not in raw_rates:
                row = filtered[filtered["genus"] == genus]
                if len(row) > 0:
                    raw_rates[role] = float(row.iloc[0]["hourly rate"])

    rates_inr = raw_rates

    # ══════════════════════════════════════════════════════════
    # SECTION B: RESOURCE COST SUMMARY
    # ══════════════════════════════════════════════════════════
    st.divider()
    section_hdr("💰 Resource Cost Summary")

    fte_result = st.session_state.get("_fte_result", {})
    monthly_working_hours = float(st.session_state.get("monthly_working_hours", 160.0))
    role_genus = st.session_state.get("role_genus", {})
    
    resource_costs = calc_resource_cost(fte_result, monthly_working_hours, rates_inr, role_genus)
    total_resource_cost = sum(v["cost_inr"] for v in resource_costs.values())
    st.session_state["_resource_costs"]      = resource_costs
    st.session_state["_total_resource_cost"] = total_resource_cost

    rc_rows_html = ""
    for role in ALL_ROLES:
        r = resource_costs[role]
        rc_rows_html += (
            f"<tr><td>{role}</td>"
            f"<td>{r['genus'] or '—'}</td>"
            f"<td class='r'>{r['fte']:.1f}</td>"
            f"<td class='r'>{r['billed_hours']:,.0f}</td>"
            f"<td class='r'>₹{r['rate_inr']:,.0f}</td>"
            f"<td class='r'>₹{r['cost_inr']:,.0f}</td></tr>"
        )
    rc_rows_html += (
        f"<tr class='total-row'>"
        f"<td colspan='5'><strong>Total Resource Cost</strong></td>"
        f"<td class='r'><strong>₹{total_resource_cost:,.0f}</strong></td></tr>"
    )
    st.markdown(f"""
    <table class="styled-table">
      <thead><tr>
        <th>Role</th><th>Genus</th>
        <th class="r">Required FTE</th>
        <th class="r">Billed Hours</th>
        <th class="r">Rate (INR/hr)</th>
        <th class="r">Cost (INR)</th>
      </tr></thead>
      <tbody>{rc_rows_html}</tbody>
    </table>""", unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════
    # SECTION C: TRANSITION COST
    # ══════════════════════════════════════════════════════════
    st.divider()
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
        st.info(f"One-Time Transition Cost: **₹{transition_total_cost:,.0f}** (This will not be included in the monthly delivery cost)")
    st.session_state["transition_total_cost"] = transition_total_cost

    # ══════════════════════════════════════════════════════════
    # SECTION D: ADDITIONAL COST COMPONENTS
    # ══════════════════════════════════════════════════════════
    st.divider()
    section_hdr("📝 Additional Cost Components")
    add_costs = st.session_state.additional_costs
    to_remove = []

    for i, row in enumerate(add_costs):
        name_val = row["name"]
        if name_val in ["Shift Allowance", "On-Call Allowance"]:
            st.markdown(f"**{name_val}**")
            ac1, ac2, ac3 = st.columns(3)
            # Default missing keys just in case
            p_val = float(row.get("people", 0))
            h_val = float(row.get("hours", 0))
            r_val = float(row.get("rate", 0.0))

            p = ac1.number_input("Number of People", min_value=0.0, step=1.0, value=p_val if p_val else None, placeholder="0", key=f"ac_p_{i}")
            h = ac2.number_input("Monthly Hours per Person", min_value=0.0, step=10.0, value=h_val if h_val else None, placeholder="0", key=f"ac_h_{i}")
            r = ac3.number_input("Cost per Shift/Hr (INR)", min_value=0.0, step=100.0, value=r_val if r_val else None, placeholder="0", key=f"ac_r_{i}")
            
            p = p or 0.0
            h = h or 0.0
            r = r or 0.0
            # Assuming rate is per hour or user scales it correctly
            # Math: total = people * hours * rate
            cost_v = p * h * r
            
            add_costs[i]["people"] = p
            add_costs[i]["hours"] = h
            add_costs[i]["rate"] = r
            add_costs[i]["cost"] = cost_v
            st.markdown(f"<div style='margin-bottom: 15px; font-size: 0.85rem;'>Calculated Cost: <b>₹{cost_v:,.0f}</b></div>", unsafe_allow_html=True)
            
        else:
            ac1, ac2, ac3 = st.columns([4, 2.5, 0.8])
            if row.get("custom"):
                name = ac1.text_input("Name", value=row["name"],
                                      key=f"addcost_name_{i}", label_visibility="collapsed")
                add_costs[i]["name"] = name
            else:
                ac1.markdown(f"*{row['name']}*")

            val = float(row["cost"])
            cost_v = ac2.number_input(
                "cost", min_value=0.0, step=100.0, format="%.0f",
                value=val if val else None, placeholder="0",
                key=f"addcost_{i}",
                label_visibility="collapsed",
                help="Monthly cost in INR",
            )
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

    total_additional = sum(r["cost"] for r in add_costs)
    st.info(f"Total Additional Expenses: **₹{total_additional:,.0f}**")
    st.session_state["_total_additional_expenses"] = total_additional

    # ══════════════════════════════════════════════════════════
    # SECTION E: SLA PROVISION + MARGIN
    # ══════════════════════════════════════════════════════════
    st.divider()
    section_hdr("⚖️ SLA Penalty Provision")
    sla_inc = st.radio("Include SLA Penalty Provision?", ["Yes", "No"],
                       index=0 if st.session_state.get("sla_provision_included") == "Yes" else 1,
                       key="sla_provision_included", horizontal=True)
    sla_pct = 0.0
    if sla_inc == "Yes":
        val = float(st.session_state.get("sla_provision_pct", 2.0))
        sla_pct_input = st.number_input(
            "SLA Provision (% of Delivery Cost before provision)",
            min_value=0.0, max_value=15.0, step=0.5, format="%.1f",
            value=val if val else None, placeholder="0",
            key="sla_provision_pct",
        )
        sla_pct = sla_pct_input or 0.0
    st.session_state["_sla_pct"] = sla_pct

    st.divider()
    section_hdr("📈 Target Gross Margin")
    val_margin = float(st.session_state.get("target_margin_pct", 20.0))
    margin_input = st.number_input(
        "**Target Gross Margin (%)** *(required)*",
        min_value=0.0, max_value=80.0, step=0.5, format="%.1f",
        value=val_margin if val_margin else None, placeholder="0",
        key="target_margin_pct",
        help="Selling Price = Delivery Cost ÷ (1 − Margin%). E.g., 20% margin on ₹100 cost → ₹125 selling price.",
    )
    margin = margin_input or 0.0

    # ══════════════════════════════════════════════════════════
    # SECTION F: CALCULATIONS
    # ══════════════════════════════════════════════════════════
    # Monthly transition cost is REMOVED from the monthly delivery cost computation
    cost_result = calc_total_delivery_cost(
        total_resource_cost, 0.0, total_additional, sla_pct
    )
    try:
        price_result = calc_selling_price(cost_result["total_delivery_cost"], margin)
    except ValueError as e:
        callout(f"❌ {e}", "error")
        return False

    st.session_state["_cost_result"]  = cost_result
    st.session_state["_price_result"] = price_result

    # ══════════════════════════════════════════════════════════
    # OUTPUT DASHBOARD
    # ══════════════════════════════════════════════════════════
    st.divider()
    st.markdown("---")
    st.markdown(
        '<div style="text-align:center; font-size:1.5rem; font-weight:700; color:#0D1B2A; '
        'padding:8px 0;">📊 OUTPUT DASHBOARD</div>',
        unsafe_allow_html=True,
    )

    # ── Reporting Currency (Hardcoded to INR) ────────────────────────
    currency = "INR"
    st.session_state["reporting_currency"] = "INR"

    def conv(inr_val):
        return convert_to_currency(inr_val, currency, all_fx)

    # ── Panel 1: Executive Metrics ─────────────────────────────
    st.divider()
    section_hdr("📊 Executive Summary")
    total_effort  = st.session_state.get("_total_effort", 0.0)
    fte_result    = st.session_state.get("_fte_result", {})
    total_fte     = sum(v["final_fte"] for v in fte_result.values())
    contingency_pct = float(st.session_state.get("contingency_pct", 0.0))
    base_effort   = total_effort / (1 + contingency_pct / 100) if contingency_pct < 100 else total_effort
    cont_hours    = total_effort - base_effort

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Effort",    fmt_hours(total_effort))
    m2.metric("Total FTE",       f"{total_fte:.1f}")
    m3.metric("Delivery Cost",   fmt_currency(conv(cost_result["total_delivery_cost"]), currency))
    m4.metric("Selling Price",   fmt_currency(conv(price_result["selling_price"]), currency))

    m5, m6, m7, m8 = st.columns(4)
    m5.metric("Base Effort",     fmt_hours(base_effort))
    m6.metric("Contingency",     fmt_hours(cont_hours))
    m7.metric("Gross Margin",    fmt_pct(margin))
    m8.metric("Coverage Model",  st.session_state.get("coverage_model", "—"))

    # ── Panel 2: Effort Breakdown + Charts ────────────────────
    st.divider()
    section_hdr("⏱️ Effort Breakdown")

    # Recompute effort sources for charts
    _, alert_h = calc_category_hours(st.session_state.alerts)
    _, sr_h    = calc_category_hours(st.session_state.service_requests)
    _, inc_h   = calc_category_hours(st.session_state.incidents)
    _, chg_h   = calc_category_hours(st.session_state.changes)
    patch_h = calc_patching_effort(
        st.session_state.get("patching_included") == "Yes",
        st.session_state.get("num_servers", 0),
        st.session_state.get("patching_method") or "Manual",
        st.session_state.get("manual_effort_per_server", 0),
        st.session_state.get("patch_failure_rate", 0),
        st.session_state.get("patch_remediation_effort", 0),
    )["hours"]
    add_h = sum(r["hours"] for r in st.session_state.additional_activities)

    effort_sources = {
        "Monitoring Alerts":  alert_h,
        "Service Requests":   sr_h,
        "Incidents":          inc_h,
        "Change Requests":    chg_h,
        "Patching":           patch_h,
        "Additional Activities": add_h,
        "Contingency":        cont_hours,
    }

    col_chart1, col_chart2 = st.columns(2)
    with col_chart1:
        st.markdown("**By Source (hrs)**")
        if PLOTLY_OK:
            fig = px.bar(
                x=list(effort_sources.values()),
                y=list(effort_sources.keys()),
                orientation="h",
                color_discrete_sequence=["#00C4B4"],
                text=[f"{v:.0f}" for v in effort_sources.values()],
            )
            fig.update_layout(height=300, margin=dict(l=0, r=0, t=10, b=10),
                              xaxis_title="Hours", yaxis_title="", showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
        else:
            for k, v in effort_sources.items():
                st.write(f"{k}: {v:.1f} hrs")

    with col_chart2:
        st.markdown("**By Role (hrs)**")
        role_hours = st.session_state.get("_role_hours", {r: 0.0 for r in ALL_ROLES})
        role_hrs_nonzero = {r: role_hours.get(r, 0) for r in ALL_ROLES if role_hours.get(r, 0) > 0}
        if PLOTLY_OK and role_hrs_nonzero:
            fig2 = px.pie(
                values=list(role_hrs_nonzero.values()),
                names=list(role_hrs_nonzero.keys()),
                color_discrete_sequence=px.colors.qualitative.Set2,
            )
            fig2.update_layout(height=300, margin=dict(l=0, r=0, t=10, b=10))
            st.plotly_chart(fig2, use_container_width=True)

    # Effort table
    eff_rows = ""
    for k, v in effort_sources.items():
        pct = (v / total_effort * 100) if total_effort > 0 else 0
        eff_rows += f"<tr><td>{k}</td><td class='r'>{v:.1f}</td><td class='r'>{pct:.1f}%</td></tr>"
    eff_rows += (
        f"<tr class='total-row'><td><strong>Total Effort</strong></td>"
        f"<td class='r'><strong>{total_effort:.1f}</strong></td>"
        f"<td class='r'><strong>100.0%</strong></td></tr>"
    )
    st.markdown(f"""
    <table class="styled-table">
      <thead><tr><th>Source</th><th class="r">Hours</th><th class="r">%</th></tr></thead>
      <tbody>{eff_rows}</tbody>
    </table>""", unsafe_allow_html=True)

    # -- Panel 3: Resolution Detail ------------------------------------------
    st.divider()
    section_hdr("🎯 Resolution Detail — Tickets, Minutes & Role Hours")
    from config.settings import CATEGORY_SUBLABELS
    from modules.calculations.engine import calc_category_role_hours

    CATEGORY_DISPLAY = [
        ("alerts",           "🚨 Monitoring Alerts"),
        ("service_requests", "📋 Service Requests"),
        ("incidents",        "🔥 Incidents"),
        ("changes",          "🔄 Change Requests"),
    ]
    res_rows = ""
    for cat_key, cat_label in CATEGORY_DISPLAY:
        cat_data = st.session_state.get(cat_key, {})
        sublabels = CATEGORY_SUBLABELS[cat_key]
        for label in sublabels:
            row = cat_data.get(label, {})
            cnt = row.get("count", 0)
            mins = row.get("minutes", 0)
            l1p = row.get("L1_pct", 0); l2p = row.get("L2_pct", 0); l3p = row.get("L3_pct", 0)
            total_h = (cnt * mins) / 60.0
            l1h = total_h * l1p / 100; l2h = total_h * l2p / 100; l3h = total_h * l3p / 100
            res_rows += (
                f"<tr><td>{cat_label}</td><td>{label}</td>"
                f"<td class='r'>{cnt:,}</td><td class='r'>{mins:.0f}</td>"
                f"<td class='r'>{total_h:.1f}</td>"
                f"<td class='r'>{l1p:.0f}% ({l1h:.1f}h)</td>"
                f"<td class='r'>{l2p:.0f}% ({l2h:.1f}h)</td>"
                f"<td class='r'>{l3p:.0f}% ({l3h:.1f}h)</td></tr>"
            )

    st.markdown(f"""
    <table class="styled-table">
      <thead><tr>
        <th>Category</th><th>Severity</th>
        <th class="r">Count</th><th class="r">Min/Ticket</th>
        <th class="r">Total Hrs</th>
        <th class="r">L1 %(Hrs)</th><th class="r">L2 %(Hrs)</th><th class="r">L3 %(Hrs)</th>
      </tr></thead>
      <tbody>{res_rows}</tbody>
    </table>""", unsafe_allow_html=True)


    # ── Panel 4: FTE Summary ───────────────────────────────────
    st.divider()
    section_hdr("👥 FTE Summary")
    fte_rows = ""
    for role in ALL_ROLES:
        r = fte_result.get(role, {})
        cov = "✅" if r.get("coverage_applied") else "—"
        fte_rows += (
            f"<tr><td>{role}</td>"
            f"<td class='r'>{r.get('hours', 0):.1f}</td>"
            f"<td class='r'>{r.get('raw_fte', 0):.3f}</td>"
            f"<td style='text-align:center'>{cov}</td>"
            f"<td class='r'><strong>{r.get('final_fte', 0):.1f}</strong></td></tr>"
        )
    fte_rows += (
        f"<tr class='total-row'><td><strong>TOTAL</strong></td>"
        f"<td class='r'></td><td class='r'></td><td></td>"
        f"<td class='r'><strong>{total_fte:.1f}</strong></td></tr>"
    )
    st.markdown(f"""
    <table class="styled-table">
      <thead><tr>
        <th>Role</th><th class="r">Hours</th>
        <th class="r">Raw FTE</th>
        <th style="text-align:center">Cov. Applied</th>
        <th class="r">Final FTE</th>
      </tr></thead>
      <tbody>{fte_rows}</tbody>
    </table>""", unsafe_allow_html=True)

    # ── Panel 5: Cost Waterfall ────────────────────────────────
    st.divider()
    section_hdr("📉 Cost Waterfall")

    wf_labels   = ["Resource Cost"]
    wf_values   = [cost_result["resource_cost"]]
    wf_measure  = ["relative"]

    if cost_result["transition_cost"] > 0:
        wf_labels.append("Transition Cost")
        wf_values.append(cost_result["transition_cost"])
        wf_measure.append("relative")

    for row in st.session_state.additional_costs:
        if row["cost"] > 0:
            wf_labels.append(row["name"])
            wf_values.append(row["cost"])
            wf_measure.append("relative")

    if cost_result["sla_provision"] > 0:
        wf_labels.append("SLA Provision")
        wf_values.append(cost_result["sla_provision"])
        wf_measure.append("relative")

    wf_labels.append("Total Delivery Cost")
    wf_values.append(cost_result["total_delivery_cost"])
    wf_measure.append("total")

    wf_labels.append("Gross Profit")
    wf_values.append(price_result["gross_profit"])
    wf_measure.append("relative")

    wf_labels.append("Selling Price")
    wf_values.append(price_result["selling_price"])
    wf_measure.append("total")

    wf_conv = [conv(v) for v in wf_values]

    if PLOTLY_OK:
        fig_wf = go.Figure(go.Waterfall(
            orientation="v",
            measure=wf_measure,
            x=wf_labels,
            y=wf_conv,
            connector={"line": {"color": "rgba(42, 138, 138, 0.5)"}},
            increasing={"marker": {"color": "#00C4B4"}},
            decreasing={"marker": {"color": "#E74C3C"}},
            totals={"marker": {"color": "#1A5F6A"}},
            texttemplate="%{y:,.0f}",
            textposition="outside",
        ))
        fig_wf.update_layout(
            showlegend=False, height=420,
            margin=dict(l=0, r=0, t=20, b=40),
            yaxis_title=f"Amount ({currency})",
        )
        st.plotly_chart(fig_wf, use_container_width=True)

    # ── Panel 6: Financial Summary ─────────────────────────────
    st.divider()
    section_hdr("📋 Financial Summary")
    fin_items = [
        ("Total Resource Cost",      cost_result["resource_cost"],        False),
        ("Amortised Transition Cost",cost_result["transition_cost"],       False),
        ("Total Additional Expenses",cost_result["additional_expenses"],   False),
        ("SLA Penalty Provision",    cost_result["sla_provision"],         False),
        ("TOTAL DELIVERY COST",      cost_result["total_delivery_cost"],   True),
        ("Gross Margin %",           None,                                 False),
        ("Gross Profit",             price_result["gross_profit"],         False),
        ("MONTHLY SELLING PRICE",    price_result["selling_price"],        True),
    ]
    fin_rows = ""
    for label, inr_val, total in fin_items:
        cls = " class='total-row'" if total else ""
        b   = "<strong>" if total else ""
        eb  = "</strong>" if total else ""
        if inr_val is None:
            fin_rows += f"<tr{cls}><td>{b}{label}{eb}</td><td class='r'>—</td><td class='r'>{b}{fmt_pct(margin)}{eb}</td></tr>"
        else:
            fin_rows += (
                f"<tr{cls}><td>{b}{label}{eb}</td>"
                f"<td class='r'>{b}₹{inr_val:,.0f}{eb}</td>"
                f"<td class='r'>{b}{fmt_currency(conv(inr_val), currency)}{eb}</td></tr>"
            )
    st.markdown(f"""
    <table class="styled-table">
      <thead><tr><th>Component</th><th class="r">INR</th><th class="r">{currency}</th></tr></thead>
      <tbody>{fin_rows}</tbody>
    </table>""", unsafe_allow_html=True)

    return True
