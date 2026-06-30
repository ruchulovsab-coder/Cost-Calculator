"""
Step 1 — Monthly Workload Totals
Step 2 — Severity Distribution, Effort Minutes & Resolution Split
"""
import streamlit as st
import pandas as pd
from config.settings import (
    CATEGORY_SUBLABELS, DEFAULT_VOLUME_DIST_PCT,
    DEFAULT_EFFORT_MINUTES, DEFAULT_RESOLUTION_PCT,
    TICKET_CATEGORIES,
)
from modules.calculations.engine import (
    calc_category_hours, calc_category_role_hours,
    validate_sublabel_row, validate_category_counts,
)


# ── Shared UI helpers ──────────────────────────────────────────────────────────

def page_header(step: int, title: str, subtitle: str = ""):
    st.markdown(f"""
    <div class="page-header">
      <h2><span class="step-badge">Step {step}</span>{title}</h2>
      {"<p>" + subtitle + "</p>" if subtitle else ""}
    </div>""", unsafe_allow_html=True)


def section_hdr(text: str):
    # Semantic <h3> (styled by .section-hdr) — better for accessibility/scannability.
    st.markdown(f'<h3 class="section-hdr">{text}</h3>', unsafe_allow_html=True)


def callout(text: str, kind: str = "info"):
    st.markdown(f'<div class="callout-{kind}">{text}</div>', unsafe_allow_html=True)


def render_glossary():
    """Plain-language glossary of the domain terms used across the tool."""
    with st.expander("📖 Glossary — what the terms mean"):
        st.markdown(
            "- **L1 / L2 / L3** — support tiers (frontline → specialist). Each ticket's effort "
            "is split across them.\n"
            "- **Genus** — the grade/band in your rate card that sets a role's hourly rate.\n"
            "- **FTE** — Full-Time Equivalent (one full-time person = 1.0 FTE).\n"
            "- **Raw vs Rounded FTE** — *Raw* is the exact computed FTE; *Rounded* rounds up to the "
            "next 0.5 with a 0.5 minimum (the delivery staffing view).\n"
            "- **Buffer %** — per-row padding added to effort for unknowns (default 20%).\n"
            "- **Contingency %** — an overall effort buffer applied across the whole estimate.\n"
            "- **Overhead roles** — Architect / SDM effort, set as a % of total operational effort.\n"
            "- **Coverage model** — the support window (e.g. 24×7); scales L1/L2 staffing.\n"
            "- **Utilisation %** — share of working hours spent on billable delivery (typical ~75%).\n"
            "- **SLA provision %** — a percentage added to cover potential SLA penalties.\n"
            "- **Transition cost** — a one-time onboarding cost, billed separately from the monthly fee."
        )


# ── Relocatable input blocks (same session keys → calculations unchanged) ──────

def render_coverage_model():
    """Support coverage model selector (lives on Step 1; multiplier used on Step 6)."""
    from config.settings import COVERAGE_MODELS
    section_hdr("📅 Support Coverage Model")
    model_options = list(COVERAGE_MODELS.keys())
    prev = st.session_state.get("coverage_model")
    idx = model_options.index(prev) if prev in model_options else 0
    model = st.radio("**Support Coverage Model** *(required)*", options=model_options,
                     index=idx, key="coverage_model_w", horizontal=True,
                     help="Coverage window sets the shift multiplier applied to L1 & L2 staffing.")
    st.session_state["coverage_model"] = model
    if model == "Custom":
        cc1, cc2 = st.columns(2)
        hpd = cc1.number_input("Hours Per Day", min_value=1, max_value=24, step=1,
                               value=int(st.session_state.get("custom_hours_per_day", 8)),
                               key="custom_hours_per_day_w")
        st.session_state["custom_hours_per_day"] = hpd
        dpw = cc2.number_input("Days Per Week", min_value=1, max_value=7, step=1,
                               value=int(st.session_state.get("custom_days_per_week", 5)),
                               key="custom_days_per_week_w")
        st.session_state["custom_days_per_week"] = dpw


def render_overhead_inputs():
    """Architect/SDM overhead % (lives on Step 5)."""
    section_hdr("🏗️ Overhead Role Effort (% of Total Operational Hours)")
    callout("Architect and SDM hours are a percentage of total operational effort. "
            "These are <strong>additive</strong> — they don't reduce L1/L2/L3 hours.", "info")
    overhead = st.session_state.overhead_pcts
    overhead.pop("SSDM", None)              # SSDM removed from the model
    oc1, oc2 = st.columns(2)
    arch = oc1.number_input("Architect (%)", min_value=0.0, max_value=50.0, step=0.5,
                            value=float(overhead.get("Architect", 5.0)), key="overhead_architect",
                            help="Architect hours = this % × total operational effort.")
    sdm = oc2.number_input("SDM (%)", min_value=0.0, max_value=50.0, step=0.5,
                           value=float(overhead.get("SDM", 5.0)), key="overhead_sdm")
    overhead["Architect"], overhead["SDM"] = arch, sdm
    if arch + sdm > 30:
        callout(f"⚠️ Overhead total {arch+sdm:.1f}% — above typical range. Please confirm.", "warning")


def render_patching_role():
    """Which role absorbs patching effort (lives on Step 3)."""
    from config.settings import ALL_ROLES
    section_hdr("🔧 Patching Effort Assignment")
    callout("All patching effort hours are added to this role's total. "
            "Typically L2 for tool-based, L1 for manual bulk patching.", "info")
    _pr = st.selectbox("Assign patching effort to role:", options=ALL_ROLES,
                       index=ALL_ROLES.index(st.session_state.get("patching_role", "L2")),
                       key="patching_role_w",
                       help="Patching hours are added to this role's monthly hours.")
    st.session_state["patching_role"] = _pr


# ── Step 1 ─────────────────────────────────────────────────────────────────────

def render_step1() -> bool:
    page_header(1, "Monthly Workload Volumes",
                "Enter the total monthly ticket / alert volume for each category.")

    render_glossary()

    # ── Estimate identity (required) ──────────────────────────
    section_hdr("📇 Estimate Details")
    proj = st.text_input(
        "Customer / RFP Name *", value=st.session_state.get("project_name", ""),
        key="project_name_w", placeholder="e.g. Acme Corp — Infra RFP 2026",
        help="Every estimate is identified and saved under this name.")
    st.session_state["project_name"] = proj
    st.caption(f"👤 Prepared by **{st.session_state.get('user_email', '')}** — used on "
               "approval emails and to label your saved versions and drafts.")
    st.divider()

    # ── Engagement setup: coverage + rate card + delivery location (on Step 1) ──
    render_coverage_model()
    try:
        from modules.inputs.steps_6_7 import render_rate_card_source, render_delivery_location
        st.divider()
        render_rate_card_source()
        render_delivery_location()
    except Exception as _e:
        callout(f"Rate card / delivery location unavailable here: {_e}", "info")
    st.divider()

    callout(
        "Enter <strong>one number per category</strong> — the total tickets or alerts "
        "your team handles per month. Step 2 will automatically distribute these across "
        "severity levels and pre-fill resolution effort using industry-standard defaults, "
        "which you can then adjust.",
        "info",
    )

    from modules.state.session_manager import apply_total_volume

    totals = st.session_state.workload_totals

    CATEGORIES = [
        ("alerts",           "🚨 Monitoring Alerts",
         "Total monitoring alerts fired per month across all severities."),
        ("service_requests", "📋 Service Requests",
         "Total service requests raised per month across all complexity levels."),
        ("incidents",        "🔥 Incidents",
         "Total incidents raised per month across all severity levels."),
        ("changes",          "🔄 Change Requests",
         "Total change requests per month across standard, normal and complex types."),
    ]

    cols = st.columns(4)
    changed = {}
    for i, (key, label, tip) in enumerate(CATEGORIES):
        with cols[i]:
            new_val = st.number_input(
                label,
                min_value=0, step=10,
                value=int(totals.get(key, 0)),
                key=f"total_{key}",
                help=tip,
            )
            if new_val != totals.get(key, 0):
                changed[key] = new_val
            totals[key] = new_val

    # Re-distribute whenever a total changes
    for key, val in changed.items():
        apply_total_volume(key, val)
        st.rerun()

    # Summary row
    grand = sum(totals.values())
    st.divider()
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Monitoring Alerts",  f"{totals['alerts']:,}")
    c2.metric("Service Requests",   f"{totals['service_requests']:,}")
    c3.metric("Incidents",          f"{totals['incidents']:,}")
    c4.metric("Change Requests",    f"{totals['changes']:,}")
    c5.metric("Grand Total",        f"{grand:,}")

    ok = True
    if not proj.strip():
        callout("Enter a <strong>Customer / RFP name</strong> above to begin.", "warning")
        ok = False
    if grand == 0:
        callout("Enter at least one volume to proceed to Step 2.", "warning")
        ok = False
    return ok


# ── Step 2 ─────────────────────────────────────────────────────────────────────

def _render_category_block(cat_key: str, cat_label: str) -> bool:
    """
    Distribution + effort + resolution-split for one ticket category.

    Inputs (Dist %, Min/Ticket, L1/L2/L3 %) are edited in a single st.data_editor;
    Count and role-hours are derived and shown in a read-only results table below.
    A single set of L1/L2/L3 buffer % is set at the category heading and applied to
    every row: hours = base × (1 + role_buffer/100). Default 20% each.
    The session_state contract (count, minutes, dist_pct, L*_pct, L*_buffer) is
    unchanged, so the calculation engine is unaffected.
    """
    from config.settings import DEFAULT_ROLE_BUFFER_PCT
    sublabels = CATEGORY_SUBLABELS[cat_key]
    cat_data  = st.session_state[cat_key]
    total_vol = st.session_state.workload_totals.get(cat_key, 0)

    st.markdown(
        f"<div style='background:#FFFFFF;border-left:4px solid #00C4B4;"
        f"padding:8px 14px;border-radius:0 6px 6px 0;margin-bottom:8px'>"
        f"<strong>{cat_label}</strong> — Total volume: "
        f"<strong>{total_vol:,}</strong> tickets/month</div>",
        unsafe_allow_html=True,
    )

    if total_vol == 0:
        st.caption("Volume is 0 — set a total in Step 1 first.")
        return True

    # ── Per-category buffers (one L1/L2/L3, applied to every row below) ──
    first = cat_data.get(sublabels[0], {})
    st.markdown("<div style='font-size:0.8rem;color:#1A5F6A;font-weight:600;margin:2px 0'>"
                "Buffer % — applied to every row in this category</div>", unsafe_allow_html=True)
    bcols = st.columns([1, 1, 1, 4])
    cat_buf = {}
    for j, role in enumerate(("L1", "L2", "L3")):
        cat_buf[role] = bcols[j].number_input(
            role, min_value=0.0, max_value=200.0, step=5.0, format="%.0f",
            value=float(first.get(f"{role}_buffer", DEFAULT_ROLE_BUFFER_PCT)),
            key=f"{cat_key}_buf_{role}",
            help=f"Buffer % added to all {role} effort in {cat_label}. Default 20%.")

    # ── Editable inputs — individual number_inputs (single-entry, like Step 1) ──
    _w = [1.6, 1, 1, 1, 1, 1]
    _hdr = st.columns(_w)
    for _c, _t in zip(_hdr, ["Severity / Type", "Dist %", "Min/Ticket", "L1 %", "L2 %", "L3 %"]):
        _c.markdown(f"<div style='font-size:0.76rem;color:#1A5F6A;font-weight:600'>{_t}</div>",
                    unsafe_allow_html=True)
    row_vals = {}
    for label in sublabels:
        cur = cat_data.get(label, {})
        rc = st.columns(_w)
        rc[0].markdown(f"<div style='padding-top:6px;font-size:0.85rem'>{label}</div>",
                       unsafe_allow_html=True)
        dist_pct = rc[1].number_input(
            f"{label} Dist %", min_value=0.0, max_value=100.0, step=1.0,
            value=float(cur.get("dist_pct", DEFAULT_VOLUME_DIST_PCT[cat_key][label])),
            key=f"{cat_key}_{label}_dist", label_visibility="collapsed")
        minutes = rc[2].number_input(
            f"{label} Min", min_value=0.0, step=1.0,
            value=float(cur.get("minutes", DEFAULT_EFFORT_MINUTES[cat_key][label])),
            key=f"{cat_key}_{label}_min", label_visibility="collapsed")
        l1p = rc[3].number_input(
            f"{label} L1", min_value=0.0, max_value=100.0, step=1.0,
            value=float(cur.get("L1_pct", DEFAULT_RESOLUTION_PCT[cat_key][label]["L1"])),
            key=f"{cat_key}_{label}_l1", label_visibility="collapsed")
        l2p = rc[4].number_input(
            f"{label} L2", min_value=0.0, max_value=100.0, step=1.0,
            value=float(cur.get("L2_pct", DEFAULT_RESOLUTION_PCT[cat_key][label]["L2"])),
            key=f"{cat_key}_{label}_l2", label_visibility="collapsed")
        l3p = rc[5].number_input(
            f"{label} L3", min_value=0.0, max_value=100.0, step=1.0,
            value=float(cur.get("L3_pct", DEFAULT_RESOLUTION_PCT[cat_key][label]["L3"])),
            key=f"{cat_key}_{label}_l3", label_visibility="collapsed")
        row_vals[label] = (dist_pct, minutes, l1p, l2p, l3p)

    # ── Recompute, persist to the session contract, and validate ──
    all_valid = True
    dist_pct_sum = 0.0
    cat_total_h = 0.0
    role_buffered = {"L1": 0.0, "L2": 0.0, "L3": 0.0}
    detail = ""
    for i, label in enumerate(sublabels):
        dist_pct, minutes, l1p, l2p, l3p = row_vals[label]
        dist_pct = float(dist_pct or 0); minutes = float(minutes or 0)
        l1p = float(l1p or 0); l2p = float(l2p or 0); l3p = float(l3p or 0)
        dist_pct_sum += dist_pct

        count = round(total_vol * dist_pct / 100)
        total_h = (count * minutes) / 60.0
        cat_total_h += total_h
        l1h = total_h * l1p / 100.0 * (1.0 + cat_buf["L1"] / 100.0)
        l2h = total_h * l2p / 100.0 * (1.0 + cat_buf["L2"] / 100.0)
        l3h = total_h * l3p / 100.0 * (1.0 + cat_buf["L3"] / 100.0)
        role_buffered["L1"] += l1h; role_buffered["L2"] += l2h; role_buffered["L3"] += l3h

        cat_data[label] = {
            "dist_pct": dist_pct, "count": count, "minutes": minutes,
            "L1_pct": l1p, "L2_pct": l2p, "L3_pct": l3p,
            "L1_buffer": cat_buf["L1"], "L2_buffer": cat_buf["L2"], "L3_buffer": cat_buf["L3"],
        }

        pct_sum = l1p + l2p + l3p
        ok = abs(pct_sum - 100.0) < 0.5
        if not ok:
            all_valid = False
        pill = ('<span class="pill-ok">✓</span>' if ok
                else f'<span class="pill-err">{pct_sum:.0f}%</span>')
        detail += (
            f"<tr><td>{label}</td><td class='r'>{count:,}</td><td class='r'>{minutes:.0f}</td>"
            f"<td class='r'>{total_h:.1f}</td><td class='r'>{l1h:.1f}</td>"
            f"<td class='r'>{l2h:.1f}</td><td class='r'>{l3h:.1f}</td>"
            f"<td style='text-align:center'>{pill}</td></tr>"
        )

    st.markdown(f"""
    <table class="styled-table"><thead><tr>
      <th>Severity / Type</th><th class="r">Count</th><th class="r">Min</th>
      <th class="r">Total Hrs</th><th class="r">L1 Hrs</th><th class="r">L2 Hrs</th>
      <th class="r">L3 Hrs</th><th style="text-align:center">L1+L2+L3</th>
    </tr></thead><tbody>{detail}</tbody></table>""", unsafe_allow_html=True)

    if abs(dist_pct_sum - 100.0) < 0.5:
        st.markdown(
            f"<div style='text-align:right;color:#1A5F6A;font-size:0.84rem;"
            f"font-weight:600;padding:4px 0'>"
            f"✅ Distribution 100% &nbsp;|&nbsp; Category Total (pre-buffer): {cat_total_h:.1f} hrs "
            f"&nbsp;|&nbsp; Buffered → L1: {role_buffered['L1']:.1f} &nbsp; "
            f"L2: {role_buffered['L2']:.1f} &nbsp; L3: {role_buffered['L3']:.1f} hrs</div>",
            unsafe_allow_html=True,
        )
    else:
        diff = 100.0 - dist_pct_sum
        sign = "+" if diff > 0 else ""
        callout(
            f"⚠️ Distribution percentages sum to <strong>{dist_pct_sum:.0f}%</strong> "
            f"(need {sign}{diff:.0f}% more). All severity rows must sum to 100%.",
            "warning",
        )
        all_valid = False

    return all_valid


def render_step2() -> bool:
    page_header(2, "Severity Distribution, Effort & Resolution Split",
                "Review and adjust auto-populated defaults for each ticket category.")

    callout(
        "Each category has an editable grid <strong>pre-filled with industry-standard "
        "defaults</strong> based on the totals from Step 1. Edit <strong>Dist %</strong>, "
        "<strong>Min/Ticket</strong> or the <strong>L1/L2/L3 split</strong> directly in the "
        "grid — counts and role-hours recompute in the results table below each grid. "
        "Each row's L1 + L2 + L3 must sum to 100%, and each category's Dist % must sum to 100%.",
        "info",
    )

    CATEGORY_CONFIG = [
        ("alerts",           "🚨 Monitoring Alerts"),
        ("service_requests", "📋 Service Requests"),
        ("incidents",        "🔥 Incidents"),
        ("changes",          "🔄 Change Requests"),
    ]

    all_valid = True
    for cat_key, cat_label in CATEGORY_CONFIG:
        valid = _render_category_block(cat_key, cat_label)
        if not valid:
            all_valid = False
        st.divider()

    # ── Role hours grand total ────────────────────────────────
    from modules.calculations.engine import calc_all_ticket_role_hours
    role_hours = calc_all_ticket_role_hours(
        st.session_state.alerts,
        st.session_state.service_requests,
        st.session_state.incidents,
        st.session_state.changes,
    )
    section_hdr("📊 Total Ticket-Derived Hours by Role (incl. per-row buffer)")
    m1, m2, m3 = st.columns(3)
    m1.metric("L1 Total Hours", f"{role_hours['L1']:.1f} hrs")
    m2.metric("L2 Total Hours", f"{role_hours['L2']:.1f} hrs")
    m3.metric("L3 Total Hours", f"{role_hours['L3']:.1f} hrs")

    if not all_valid:
        callout(
            "❌ One or more rows have validation errors. "
            "Fix all L1+L2+L3 sums (must = 100%) and count totals before proceeding.",
            "error",
        )
    return all_valid
