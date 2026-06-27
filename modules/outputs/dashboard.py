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
import copy
from modules.calculations.engine import convert_to_currency, compute_full_model
from modules.state.session_manager import run_model, build_model_state
from config.settings import (
    ALL_ROLES, CATEGORY_SUBLABELS, CURRENCY_SYMBOLS, REPORTING_CURRENCIES, COVERAGE_MODELS,
    DEFAULT_ROLE_BUFFER_PCT, THEME,
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

    # ── FTE basis for costing ─────────────────────────────────
    st.divider()
    section_hdr("🧮 FTE Basis (Resource Cost & Executive Summary)")
    basis_label = st.radio(
        "Calculate cost and FTE using",
        ["Rounded FTE (⌈0.5⌉)", "Raw FTE"],
        index=1 if st.session_state.get("fte_basis", "rounded") == "raw" else 0,
        key="fte_basis_w", horizontal=True,
        help="Rounded: bills to the next 0.5 FTE, min 0.5 per active role (delivery view). "
             "Raw: bills the exact computed FTE (cost-basis view). Affects Resource Cost, "
             "Executive Summary, delivery cost and price.",
    )
    st.session_state["fte_basis"] = "raw" if basis_label.startswith("Raw") else "rounded"


def _render_what_if(base_model, conv, currency):
    """Live sensitivity panel. Recomputes a modified copy of the state without
    mutating the user's saved inputs."""
    st.divider()
    section_hdr("🔮 What-If Analysis")
    callout("Drag the drivers below to see live impact on cost and price. "
            "These adjustments do <strong>not</strong> change your saved inputs.", "info")

    base_state = build_model_state()
    c1, c2 = st.columns(2)
    with c1:
        vol_steps = st.slider(
            "Ticket volume scale-up", 0.0, 5.0, 0.0, 0.5, key="wi_vol",
            help="0 = your entered volumes (no change). Moving the slider scales volumes up: "
                 "1 → 2×, 2 → 3× … 5 → 6×.",
        )
        vol_scale = 1.0 + vol_steps
        st.caption(f"Effective volume: **{vol_scale:.1f}×** your entered tickets")
        margin = st.slider("Target gross margin (%)", 0.0, 80.0,
                           float(base_state.get("target_margin_pct", 20) or 20), 0.5, key="wi_margin")
    with c2:
        cont = st.slider("Contingency (%)", 0.0, 50.0,
                         float(base_state.get("contingency_pct", 10) or 10), 1.0, key="wi_cont")
        cov_models = list(COVERAGE_MODELS.keys())
        cur_cov = base_state.get("coverage_model") or "8×5"
        cov = st.selectbox(
            "Coverage model", cov_models,
            index=cov_models.index(cur_cov) if cur_cov in cov_models else 0, key="wi_cov",
            help="Defaults to the model selected in Step 6; change it here to test alternatives.",
        )

    s = copy.deepcopy(base_state)
    s["target_margin_pct"] = margin
    s["contingency_pct"] = cont
    s["coverage_model"] = cov
    if vol_scale != 1.0:
        for cat in ("alerts", "service_requests", "incidents", "changes"):
            for row in (s.get(cat) or {}).values():
                row["count"] = round(row.get("count", 0) * vol_scale)

    try:
        wm = compute_full_model(s)
    except ValueError as e:
        callout(f"❌ {e}", "error")
        return

    base_dc = conv(base_model["cost_result"]["total_delivery_cost"])
    base_sp = conv(base_model["price_result"]["selling_price"])
    new_dc = conv(wm["cost_result"]["total_delivery_cost"])
    new_sp = conv(wm["price_result"]["selling_price"])

    w1, w2, w3 = st.columns(3)
    w1.metric("Total FTE", f"{wm['total_fte']:.1f}",
              delta=f"{wm['total_fte'] - base_model['total_fte']:+.1f}")
    w2.metric(f"Delivery Cost ({currency})", fmt_currency(new_dc, currency),
              delta=f"{new_dc - base_dc:+,.0f}")
    w3.metric(f"Selling Price ({currency})", fmt_currency(new_sp, currency),
              delta=f"{new_sp - base_sp:+,.0f}")

    # ── Save this what-if as a new version ────────────────────
    # Bakes the moved drivers into the live inputs, then saves a draft version whose
    # note records exactly which drivers were applied.
    st.divider()
    drivers = []
    if vol_scale != 1.0:
        drivers.append(f"volume {vol_scale:.1f}×")
    drivers += [f"margin {margin:.0f}%", f"contingency {cont:.0f}%", f"coverage {cov}"]
    note_txt = "what-if: " + ", ".join(drivers)
    st.caption("Apply these what-if drivers as a new saved version (a draft that needs "
               "its own approval). Your other saved versions are untouched.")
    note = st.text_input("Version note", value=note_txt, key="wi_save_note",
                         help="Records which what-if drivers were applied to this version.")
    if st.button("💾 Save what-if as new version", type="primary", key="wi_save_btn"):
        st.session_state["target_margin_pct"] = float(margin)
        st.session_state["contingency_pct"] = float(cont)
        st.session_state["coverage_model"] = cov
        if vol_scale != 1.0:
            totals = dict(st.session_state.get("workload_totals") or {})
            for cat in ("alerts", "service_requests", "incidents", "changes"):
                sec = st.session_state.get(cat) or {}
                for row in sec.values():
                    row["count"] = round(row.get("count", 0) * vol_scale)
                st.session_state[cat] = sec
                totals[cat] = sum(r.get("count", 0) for r in sec.values())
            st.session_state["workload_totals"] = totals
        from modules.outputs.approval import save_version
        meta = save_version(note)
        if meta:
            st.success(f"Saved {meta['project']} — v{meta['version']} (draft) with the "
                       "what-if applied. Request approval on the panel above.")
            st.rerun()


def _get_model_conv():
    """Compute the full model once and build a currency converter.
    Returns (model, conv, currency) or (None, None, None) if the model is
    invalid (error already rendered)."""
    try:
        model = run_model()
    except ValueError as e:
        callout(f"❌ {e}", "error")
        return None, None, None
    st.session_state["_model"] = model  # reused by exports / scenarios
    currency = model["reporting_currency"]
    fx = dict(st.session_state.get("exchange_rates", {}) or {}); fx.setdefault("INR", 1.0)
    def conv(v): return convert_to_currency(v, currency, fx)
    return model, conv, currency


def _render_divergence_gate():
    """Approved estimate changed: red banner + inline 'save as new version'. The new
    version starts as a draft and needs its own approval."""
    from modules.outputs.approval import inline_save_version
    callout("🔴 <strong>This approved estimate has changed.</strong> The approved version "
            "must stay unchanged — save your changes as a <strong>new version</strong> "
            "(it starts as a draft and needs its own approval).", "error")
    inline_save_version(note_default="manual edit", key="diverge",
                        button_label="💾 Save as new version",
                        success_suffix="Now request approval below.")


def _render_reviewer_summary(model, conv, currency):
    """Compact estimate summary shown to a reviewer on the approval landing page, so
    the decision is made with the key numbers (and margin) in view rather than buried
    behind the Results Dashboard / downloads."""
    section_hdr("📋 Estimate Summary (for review)")
    cr = model["cost_result"]; pr = model["price_result"]
    _raw = model["fte_basis"] == "raw"
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Effort", fmt_hours(model["total_effort"]))
    m2.metric("Total FTE (Raw)" if _raw else "Total FTE (Rounded)",
              f"{model['total_fte']:.2f}" if _raw else f"{model['total_fte']:.1f}")
    m3.metric(f"Delivery Cost ({currency})", fmt_currency(conv(cr["total_delivery_cost"]), currency))
    m4.metric(f"Selling Price ({currency})", fmt_currency(conv(pr["selling_price"]), currency))
    m5, m6, m7, m8 = st.columns(4)
    m5.metric("Gross Margin", fmt_pct(pr["margin_pct"]))
    m6.metric("Contingency", fmt_hours(model["contingency"]["contingency_hours"]))
    m7.metric("Coverage Model", st.session_state.get("coverage_model") or "—")
    if model.get("transition_cost", 0) > 0:
        m8.metric(f"One-time Transition ({currency})",
                  fmt_currency(conv(model["transition_cost"]), currency))
    st.caption("Full breakdown is on the **Results Dashboard** (sidebar) and in the "
               "downloadable reports below.")
    st.divider()


# ════════════════════════════════════════════════════════════════════════════
# STEP 8 — Costing Inputs
# ════════════════════════════════════════════════════════════════════════════
def render_step8() -> bool:
    page_header(8, "Costing Inputs",
                "Configure expenses, provisions and target margin. "
                "The full breakdown follows on the Results Dashboard.")

    _render_cost_inputs()

    # Validate the model (e.g. margin < 100) and show a compact headline so the
    # user sees the effect of the cost inputs without leaving the page.
    model, conv, currency = _get_model_conv()
    if model is None:
        return False

    st.divider()
    section_hdr("📊 Estimate Headline")
    _raw = model["fte_basis"] == "raw"
    h1, h2, h3 = st.columns(3)
    h1.metric("Total FTE (Raw)" if _raw else "Total FTE (Rounded)",
              f"{model['total_fte']:.2f}" if _raw else f"{model['total_fte']:.1f}")
    h2.metric(f"Delivery Cost ({currency})",
              fmt_currency(conv(model["cost_result"]["total_delivery_cost"]), currency))
    h3.metric(f"Selling Price ({currency})",
              fmt_currency(conv(model["price_result"]["selling_price"]), currency))
    st.caption("➡️ Continue to **Results Dashboard** for the complete breakdown.")
    return True


# ════════════════════════════════════════════════════════════════════════════
# STEP 9 — Results Dashboard (read-only outputs)
# ════════════════════════════════════════════════════════════════════════════
def render_step9() -> bool:
    page_header(9, "Results Dashboard",
                "The complete computed estimate. Inputs live on the previous pages.")

    # Chat-built estimates land here unnamed; let the user name it in place (kept out
    # of the chat/LLM) so it can be saved or sent for approval. Manual estimates
    # always have a name by Step 1, so this only shows for the chat route.
    if not (st.session_state.get("project_name") or "").strip():
        callout("📝 <strong>Name this estimate</strong> (Customer / RFP) to save it or send "
                "it for approval.", "info")
        _nm = st.text_input("Customer / RFP name", key="results_proj_name",
                            placeholder="e.g. Acme Corp — Infra RFP 2026")
        if _nm.strip():
            st.session_state["project_name"] = _nm.strip()
            st.rerun()

    model, conv, currency = _get_model_conv()
    if model is None:
        return False

    if not st.session_state.get("_review"):
        from modules.outputs.approval import change_state
        if change_state()["diverged"]:
            callout("🔴 This approved estimate has changed. Open <strong>Approve &amp; Export</strong> "
                    "to save it as a new version before exporting or re-requesting approval.", "error")

    cost_result   = model["cost_result"]
    price_result  = model["price_result"]
    fte_result    = model["fte_result"]
    resource_costs = model["resource_costs"]
    total_fte     = model["total_fte"]
    total_effort  = model["total_effort"]
    margin        = price_result["margin_pct"]

    st.markdown(
        '<div style="text-align:center; font-size:1.5rem; font-weight:700; color:#0D1B2A; '
        'padding:8px 0;">📊 OUTPUT DASHBOARD</div>', unsafe_allow_html=True)

    # ── Resource cost summary ─────────────────────────────────
    basis_txt = "Raw FTE" if model["fte_basis"] == "raw" else "Rounded FTE (⌈0.5⌉)"
    section_hdr("💰 Resource Cost Summary")
    st.caption(f"Costed on **{basis_txt}** — change this with the FTE Basis toggle above.")
    rc_rows_html = ""
    _raw = model["fte_basis"] == "raw"
    for role in ALL_ROLES:
        r = resource_costs[role]
        fte_disp = f"{r['fte']:.2f}" if _raw else f"{r['fte']:.1f}"
        rc_rows_html += (
            f"<tr><td>{role}</td><td>{r['genus'] or '—'}</td>"
            f"<td class='r'>{fte_disp}</td><td class='r'>{r['billed_hours']:,.0f}</td>"
            f"<td class='r'>{fmt_currency(r['rate_inr'])}</td><td class='r'>{fmt_currency(r['cost_inr'])}</td></tr>"
        )
    rc_rows_html += (
        f"<tr class='total-row'><td colspan='5'><strong>Total Resource Cost</strong></td>"
        f"<td class='r'><strong>{fmt_currency(model['total_resource_cost'])}</strong></td></tr>"
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
    _raw_fte = model["fte_basis"] == "raw"
    m2.metric("Total FTE (Raw)" if _raw_fte else "Total FTE (Rounded)",
              f"{total_fte:.2f}" if _raw_fte else f"{total_fte:.1f}")
    m3.metric("Delivery Cost", fmt_currency(conv(cost_result["total_delivery_cost"]), currency))
    m4.metric("Selling Price", fmt_currency(conv(price_result["selling_price"]), currency))
    m5, m6, m7, m8 = st.columns(4)
    m5.metric("Base Effort",    fmt_hours(base_effort))
    m6.metric("Contingency",    fmt_hours(cont_hours))
    m7.metric("Gross Margin",   fmt_pct(margin))
    m8.metric("Coverage Model", st.session_state.get("coverage_model") or "—")

    # ── Effort breakdown + charts ─────────────────────────────
    st.divider()
    section_hdr("⏱️ Effort Breakdown")
    effort_sources = model["effort_sources"]
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**By Source (hrs)**")
        if PLOTLY_OK:
            fig = px.bar(x=list(effort_sources.values()), y=list(effort_sources.keys()),
                         orientation="h", color_discrete_sequence=[THEME["primary"]],
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
            # Sorted horizontal bar (brand teal) — matches the "By Source" chart and
            # reads better than a 6-slice pie.
            ordered = dict(sorted(nz.items(), key=lambda kv: kv[1]))
            fig2 = px.bar(x=list(ordered.values()), y=list(ordered.keys()),
                          orientation="h", color_discrete_sequence=[THEME["primary"]],
                          text=[f"{v:.0f}" for v in ordered.values()])
            fig2.update_layout(height=300, margin=dict(l=0, r=0, t=10, b=10),
                               xaxis_title="Hours", yaxis_title="", showlegend=False)
            st.plotly_chart(fig2, use_container_width=True)
        elif nz:
            for k, v in sorted(nz.items(), key=lambda kv: -kv[1]):
                st.write(f"{k}: {v:.1f} hrs")
        else:
            callout("No role hours yet — enter volumes on Step 1.", "info")

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
            l1b = row.get("L1_buffer", DEFAULT_ROLE_BUFFER_PCT)
            l2b = row.get("L2_buffer", DEFAULT_ROLE_BUFFER_PCT)
            l3b = row.get("L3_buffer", DEFAULT_ROLE_BUFFER_PCT)
            total_h = (cnt * mins) / 60.0
            # Buffered role hours (match Step 2)
            l1h = total_h * l1p / 100 * (1 + l1b / 100)
            l2h = total_h * l2p / 100 * (1 + l2b / 100)
            l3h = total_h * l3p / 100 * (1 + l3b / 100)
            res_rows += (
                f"<tr><td>{cat_label}</td><td>{label}</td>"
                f"<td class='r'>{cnt:,}</td><td class='r'>{mins:.0f}</td><td class='r'>{total_h:.1f}</td>"
                f"<td class='r'>{l1p:.0f}% +{l1b:.0f}% ({l1h:.1f}h)</td>"
                f"<td class='r'>{l2p:.0f}% +{l2b:.0f}% ({l2h:.1f}h)</td>"
                f"<td class='r'>{l3p:.0f}% +{l3b:.0f}% ({l3h:.1f}h)</td></tr>"
            )
    st.markdown(f"""
    <table class="styled-table"><thead><tr>
        <th>Category</th><th>Severity</th><th class="r">Count</th><th class="r">Min/Ticket</th>
        <th class="r">Total Hrs</th><th class="r">L1 %+Buf (Hrs)</th><th class="r">L2 %+Buf (Hrs)</th><th class="r">L3 %+Buf (Hrs)</th>
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
            increasing={"marker": {"color": THEME["primary"]}},
            decreasing={"marker": {"color": THEME["error"]}},
            totals={"marker": {"color": THEME["teal_dark"]}},
            texttemplate="%{y:,.0f}", textposition="outside"))
        fig_wf.update_layout(showlegend=False, height=420, margin=dict(l=0, r=0, t=20, b=40),
                             yaxis_title=f"Amount ({currency})")
        st.plotly_chart(fig_wf, use_container_width=True)
    else:
        # Plotly unavailable — fall back to a labelled value list so the section
        # never renders blank.
        for lbl, val in zip(wf_labels, wf_conv):
            st.write(f"{lbl}: {fmt_currency(val, currency)}")

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
            fin_rows += (f"<tr{cls}><td>{b}{label}{eb}</td><td class='r'>{b}{fmt_currency(inr_val)}{eb}</td>"
                         f"<td class='r'>{b}{fmt_currency(conv(inr_val), currency)}{eb}</td></tr>")
    st.markdown(f"""
    <table class="styled-table"><thead><tr><th>Component</th><th class="r">INR</th><th class="r">{currency}</th></tr></thead>
      <tbody>{fin_rows}</tbody></table>""", unsafe_allow_html=True)

    return True


# ════════════════════════════════════════════════════════════════════════════
# STEP 10 — Approve & Export
# ════════════════════════════════════════════════════════════════════════════
def render_step10() -> bool:
    page_header(10, "Approve & Export",
                "Request approval, test what-if scenarios, and download the reports.")

    model, conv, currency = _get_model_conv()
    if model is None:
        return False

    review = st.session_state.get("_review")
    from modules.outputs.approval import render_approval_panel, change_state
    cs = None if review else change_state()

    # Approved estimate with unsaved edits: block the commit actions (downloads + a
    # new approval request) until it's saved as a new version.
    if cs and cs["diverged"]:
        _render_divergence_gate()
        try:
            render_approval_panel(locked=True, rec=cs["rec"])
        except Exception as _e:
            st.caption(f"Approval panel unavailable: {_e}")
        st.divider()
        section_hdr("⬇️ Download Reports")
        callout("🔒 Downloads are disabled until you save the changed estimate as a new "
                "version above.", "warning")
        return True

    # Reviewer (opened via tokened link): show what they're approving up front.
    if review:
        _render_reviewer_summary(model, conv, currency)

    # ── Approval (reviewer approve/reject via tokened link; preparer sees status).
    # The panel renders its own header ("Approval" for the preparer, "Approval
    # Review" for a reviewer), so we don't add another one here.
    try:
        render_approval_panel(rec=cs["rec"] if cs else None)
    except Exception as _e:
        st.caption(f"Approval panel unavailable: {_e}")

    # ── What-if ───────────────────────────────────────────────
    _render_what_if(model, conv, currency)

    # ── Downloads ─────────────────────────────────────────────
    st.divider()
    section_hdr("⬇️ Download Reports")
    ec1, ec2, ec3 = st.columns(3)
    with ec1:
        try:
            from modules.outputs.excel_export import generate_excel_report
            xl = generate_excel_report()
            st.download_button(
                "⬇️ Excel Report", data=xl,
                file_name="IT_MS_Calculator_Report.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary", key="dl_excel", use_container_width=True)
        except Exception as e:
            st.error(f"Excel error: {e}")
    with ec2:
        try:
            from modules.outputs.excel_model import generate_excel_model
            xlm = generate_excel_model()
            st.download_button(
                "⬇️ Editable Excel (formulas)", data=xlm,
                file_name="IT_MS_Editable_Model.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary", key="dl_excel_model", use_container_width=True)
        except Exception as e:
            st.error(f"Editable Excel error: {e}")
    with ec3:
        try:
            from modules.outputs.pdf_export import generate_pdf_report
            pdf = generate_pdf_report()
            st.download_button(
                "⬇️ PDF Proposal", data=pdf,
                file_name="IT_MS_Proposal.pdf", mime="application/pdf",
                type="primary", key="dl_pdf", use_container_width=True)
        except Exception as e:
            st.error(f"PDF error: {e}")

    st.caption("Use the **Compare** step in the sidebar to view saved scenarios side-by-side.")
    return True
