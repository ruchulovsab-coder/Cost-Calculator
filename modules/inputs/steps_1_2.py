"""
Step 1 — Monthly Workload Totals
Step 2 — Severity Distribution, Effort Minutes & Resolution Split
"""
import streamlit as st
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
    st.markdown(f'<div class="section-hdr">{text}</div>', unsafe_allow_html=True)


def callout(text: str, kind: str = "info"):
    st.markdown(f'<div class="callout-{kind}">{text}</div>', unsafe_allow_html=True)


# ── Step 1 ─────────────────────────────────────────────────────────────────────

def render_step1() -> bool:
    page_header(1, "Monthly Workload Volumes",
                "Enter the total monthly ticket / alert volume for each category.")

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

    if grand == 0:
        callout("Enter at least one volume to proceed to Step 2.", "warning")
        return False
    return True


# ── Step 2 ─────────────────────────────────────────────────────────────────────

def _render_category_block(cat_key: str, cat_label: str) -> bool:
    """
    Render the full distribution block for one ticket category.
    Columns: Severity | Dist% | Count (derived) | Effort(Min) | Total Hrs | L1% | L2% | L3% | L1Hrs | L2Hrs | Split✓
    Returns True when all rows are valid.
    """
    import math
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

    all_valid = True

    # ── Column headers ────────────────────────────────────────
    cols_w = [1.8, 1.2, 1.2, 1.2, 1.2, 1.2, 1.2, 1.2, 1.2, 1.2, 1.4]
    hc = st.columns(cols_w)
    headers = [
        "Severity / Type", "Dist %", "Count", "Effort (Min)",
        "Total Hrs", "L1 %", "L2 %", "L3 %", "L1 Hrs", "L2 Hrs", "Split ✓"
    ]
    for col, txt in zip(hc, headers):
        col.markdown(
            f"<div style='font-size:0.76rem;font-weight:700;color:#0D1B2A;"
            f"padding-bottom:2px'>{txt}</div>",
            unsafe_allow_html=True,
        )

    dist_pct_sum = 0.0
    for label in sublabels:
        row = cat_data.get(label, {})
        cc  = st.columns(cols_w)

        cc[0].markdown(f"<div style='padding-top:5px'><em>{label}</em></div>",
                       unsafe_allow_html=True)

        # ── Dist % (editable, default from settings) ─────────
        dist_pct_val = cc[1].number_input(
            "dp", min_value=0.0, max_value=100.0, step=1.0, format="%.0f",
            value=float(row.get("dist_pct", DEFAULT_VOLUME_DIST_PCT[cat_key][label])),
            key=f"{cat_key}_{label}_dist_pct",
            label_visibility="collapsed",
            help=f"% of total {cat_label} volume that are {label}. "
                 f"All rows must sum to 100%.",
        )
        dist_pct_sum += dist_pct_val

        # ── Count (derived — read only) ───────────────────────
        derived_count = round(total_vol * dist_pct_val / 100)
        cc[2].markdown(
            f"<div style='padding-top:5px;text-align:right;font-weight:600;"
            f"color:#0D1B2A'>{derived_count:,}</div>",
            unsafe_allow_html=True,
        )

        # ── Effort minutes (editable) ─────────────────────────
        minutes = cc[3].number_input(
            "min", min_value=0.0, step=1.0, format="%.0f",
            value=float(row.get("minutes", DEFAULT_EFFORT_MINUTES[cat_key][label])),
            key=f"{cat_key}_{label}_min",
            label_visibility="collapsed",
            help=f"Average minutes to fully resolve one {label} {cat_label}.",
        )

        total_h = (derived_count * minutes) / 60.0
        cc[4].markdown(
            f"<div style='padding-top:5px;text-align:right;font-weight:600;"
            f"color:#00C4B4'>{total_h:.1f}</div>",
            unsafe_allow_html=True,
        )

        # ── L1 / L2 / L3 % (editable) ────────────────────────
        l1p = cc[5].number_input(
            "l1p", min_value=0.0, max_value=100.0, step=1.0, format="%.0f",
            value=float(row.get("L1_pct", DEFAULT_RESOLUTION_PCT[cat_key][label]["L1"])),
            key=f"{cat_key}_{label}_l1p",
            label_visibility="collapsed",
            help="% of these tickets resolved by L1.",
        )
        l2p = cc[6].number_input(
            "l2p", min_value=0.0, max_value=100.0, step=1.0, format="%.0f",
            value=float(row.get("L2_pct", DEFAULT_RESOLUTION_PCT[cat_key][label]["L2"])),
            key=f"{cat_key}_{label}_l2p",
            label_visibility="collapsed",
            help="% of these tickets resolved by L2.",
        )
        l3p = cc[7].number_input(
            "l3p", min_value=0.0, max_value=100.0, step=1.0, format="%.0f",
            value=float(row.get("L3_pct", DEFAULT_RESOLUTION_PCT[cat_key][label]["L3"])),
            key=f"{cat_key}_{label}_l3p",
            label_visibility="collapsed",
            help="% of these tickets resolved by L3.",
        )

        # ── Derived role hours (display only) ─────────────────
        l1h = total_h * l1p / 100.0
        l2h = total_h * l2p / 100.0

        cc[8].markdown(
            f"<div style='padding-top:5px;text-align:right;color:#1A7A6A'>{l1h:.1f}</div>",
            unsafe_allow_html=True,
        )
        cc[9].markdown(
            f"<div style='padding-top:5px;text-align:right;color:#0D1B2A'>{l2h:.1f}</div>",
            unsafe_allow_html=True,
        )

        # ── L1+L2+L3 split validation pill ───────────────────
        pct_sum = l1p + l2p + l3p
        if abs(pct_sum - 100.0) < 0.5:
            cc[10].markdown('<span class="pill-ok">✓ 100%</span>', unsafe_allow_html=True)
        else:
            cc[10].markdown(
                f'<span class="pill-err">✗ {pct_sum:.0f}%</span>',
                unsafe_allow_html=True,
            )
            all_valid = False

        # Write back all fields including dist_pct and derived count
        cat_data[label] = {
            "dist_pct": dist_pct_val,
            "count":    derived_count,
            "minutes":  minutes,
            "L1_pct":   l1p,
            "L2_pct":   l2p,
            "L3_pct":   l3p,
        }

    # ── Dist % sum validation ────────────────────────────────
    if abs(dist_pct_sum - 100.0) < 0.5:
        # Show category summary
        role_h = calc_category_role_hours(cat_data)
        _, cat_total_h = calc_category_hours(cat_data)
        st.markdown(
            f"<div style='text-align:right;color:#1A5F6A;font-size:0.84rem;"
            f"font-weight:600;padding:4px 0'>"
            f"✅ Distribution: 100% &nbsp;|&nbsp; "
            f"Category Total: {cat_total_h:.1f} hrs &nbsp;|&nbsp; "
            f"L1: {role_h['L1']:.1f} hrs &nbsp;|&nbsp; "
            f"L2: {role_h['L2']:.1f} hrs &nbsp;|&nbsp; "
            f"L3: {role_h['L3']:.1f} hrs"
            f"</div>",
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
        "All three tables below are <strong>pre-filled with industry-standard defaults</strong> "
        "based on the total volumes you entered in Step 1. "
        "Edit any value — counts, effort minutes, or L1/L2/L3 split percentages. "
        "Each row's L1 + L2 + L3 must sum to 100%. "
        "Each category's sub-counts must sum to its total volume.",
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
    section_hdr("📊 Total Ticket-Derived Hours by Role")
    m1, m2, m3 = st.columns(3)
    m1.metric("L1 Total Hours", f"{role_hours['L1']:.1f} hrs")
    m2.metric("L2 Total Hours", f"{role_hours['L2']:.1f} hrs")
    m3.metric("L3 Total Hours", f"{role_hours['L3']:.1f} hrs")

    st.divider()

    # ── Overhead roles ────────────────────────────────────────
    section_hdr("🏗️ Overhead Role Effort (% of Total Operational Hours)")
    callout(
        "Architect, SDM and SSDM hours are calculated as a percentage of total operational effort. "
        "These are <strong>additive</strong> — they do not reduce L1/L2/L3 hours.",
        "info",
    )
    overhead = st.session_state.overhead_pcts
    oc1, oc2, oc3 = st.columns(3)
    with oc1:
        arch = st.number_input(
            "Architect (%)", min_value=0.0, max_value=50.0, step=0.5,
            value=float(overhead.get("Architect", 5.0)), key="overhead_architect",
            help="Architect hours = this % × total operational effort.",
        )
    with oc2:
        sdm = st.number_input(
            "SDM (%)", min_value=0.0, max_value=50.0, step=0.5,
            value=float(overhead.get("SDM", 5.0)), key="overhead_sdm",
        )
    with oc3:
        ssdm = st.number_input(
            "SSDM (%)", min_value=0.0, max_value=50.0, step=0.5,
            value=float(overhead.get("SSDM", 3.0)), key="overhead_ssdm",
        )
    overhead["Architect"] = arch
    overhead["SDM"]       = sdm
    overhead["SSDM"]      = ssdm
    if arch + sdm + ssdm > 30:
        callout(f"⚠️ Overhead total {arch+sdm+ssdm:.1f}% — above typical range. Please confirm.", "warning")

    st.divider()

    # ── Patching role ─────────────────────────────────────────
    section_hdr("🔧 Patching Effort Assignment")
    callout(
        "All patching effort hours will be added to this role's total. "
        "Typically L2 for tool-based patching, L1 for manual bulk patching.",
        "info",
    )
    from config.settings import ALL_ROLES
    _pr = st.selectbox(
        "Assign patching effort to role:",
        options=ALL_ROLES,
        index=ALL_ROLES.index(st.session_state.get("patching_role", "L2")),
        key="patching_role_w",
        help="Patching hours are added to this role's monthly hours.",
    )
    st.session_state["patching_role"] = _pr

    if not all_valid:
        callout(
            "❌ One or more rows have validation errors. "
            "Fix all L1+L2+L3 sums (must = 100%) and count totals before proceeding.",
            "error",
        )
    return all_valid
