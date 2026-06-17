"""
Step 3 — Patching Effort
Step 4 — Additional Operational Activities
Step 5 — Effort Summary & Contingency
"""
import streamlit as st
import pandas as pd
from modules.inputs.steps_1_2 import page_header, section_hdr, callout
from modules.calculations.engine import (
    calc_patching_effort, calc_category_hours, calc_base_effort, calc_contingency,
    calc_overhead_hours, assemble_role_hours, calc_all_ticket_role_hours,
)
from config.settings import ALERT_SEVERITIES, SR_COMPLEXITIES, INCIDENT_SEVERITIES, CHANGE_TYPES


# ── Step 3: Patching ───────────────────────────────────────────────────────────

def render_step3() -> bool:
    page_header(3, "Server Patching Effort",
                "Define patching scope, method, and per-server effort.")

    # Widgets write to plain (non-widget) keys via the *_w proxy so values survive
    # navigation to later steps (Streamlit evicts unrendered widget keys).
    included = st.radio(
        "**Is Server Patching Included in Scope?**",
        options=["Yes", "No"],
        index=0 if st.session_state.get("patching_included") == "Yes" else 1,
        key="patching_included_w",
        horizontal=True,
    )
    st.session_state["patching_included"] = included

    if included == "No":
        callout("Patching excluded. Patching effort = 0 hours.", "info")
        return True

    from config.settings import PATCHING_EFFORT_DEFAULTS

    c1, c2 = st.columns(2)
    with c1:
        servers = st.number_input(
            "**Number of Servers to be Patched**",
            min_value=1, step=1,
            value=max(1, int(st.session_state.get("num_servers", 20))),
            key="num_servers_w",
            help="Total server count in patching scope. Default: 20.",
        )
        st.session_state["num_servers"] = servers
    with c2:
        method = st.radio(
            "**Patching Method**",
            options=["Manual", "Tool-Based"],
            index=0 if st.session_state.get("patching_method") == "Manual" else 1,
            key="patching_method_w",
            horizontal=True,
            help="Manual default: 45 min/server. Automated (Tool-Based) default: 30 min/server.",
        )
        st.session_state["patching_method"] = method

    if method == "Manual":
        section_hdr("Manual Patching Configuration")
        effort = st.number_input(
            "**Effort Per Server (Minutes)**",
            min_value=0.0, step=5.0, format="%.0f",
            value=float(st.session_state.get("manual_effort_per_server", PATCHING_EFFORT_DEFAULTS["Manual"])),
            key="manual_effort_per_server_w",
            help="Average minutes to manually patch one server end-to-end. Default: 45.",
        )
        st.session_state["manual_effort_per_server"] = effort
        result = calc_patching_effort(True, servers, "Manual", manual_effort_per_server=effort)
    else:
        section_hdr("Automated (Tool-Based) Patching Configuration")
        tc1, tc2 = st.columns(2)
        error_rate = tc1.number_input(
            "**Error / Failure Rate (%)**",
            min_value=0.0, max_value=100.0, step=1.0, format="%.0f",
            value=float(st.session_state.get("patch_error_rate", 10.0)),
            key="patch_error_rate_w",
            help="% of servers where the tool fails and manual effort is needed. "
                 "e.g. 100 servers × 15% = 15 servers needing manual effort.",
        )
        st.session_state["patch_error_rate"] = error_rate
        effort = tc2.number_input(
            "**Effort Per Failed Server (Minutes)**",
            min_value=0.0, step=5.0, format="%.0f",
            value=float(st.session_state.get("auto_effort_per_server", PATCHING_EFFORT_DEFAULTS["Tool-Based"])),
            key="auto_effort_per_server_w",
            help="Manual effort for each failed (error-rate) server. Default: 30. "
                 "Servers patched successfully by the tool need no manual effort.",
        )
        st.session_state["auto_effort_per_server"] = effort
        result = calc_patching_effort(True, servers, "Tool-Based",
                                      auto_effort_per_server=effort, error_rate_pct=error_rate)

    callout(
        f"📊 <strong>Patching Effort:</strong> {result['detail']} = "
        f"<strong>{result['hours']:.1f} hours/month</strong>",
        "success",
    )

    # Patching effort assignment (relocated here from Step 2)
    st.divider()
    from modules.inputs.steps_1_2 import render_patching_role
    render_patching_role()
    return True


# ── Step 4: Additional Activities ─────────────────────────────────────────────

def render_step4() -> bool:
    page_header(4, "Additional Operational Activities",
                "Add recurring operational tasks not covered by ticket volumes or patching.")

    callout(
        "Define effort for recurring tasks and support operations in the grid below. "
        "Tick <strong>Auto</strong> on a standard activity to derive its hours from your "
        "servers/volumes, or untick it to enter your own. Set each row's role % split — "
        "for any activity with hours > 0 the role percentages must sum to exactly 100%. "
        "Use the grid's <strong>+</strong> to add a row and the row selector to delete one.",
        "info",
    )

    from config.settings import ALL_ROLES, ACTIVITY_FORMULAS
    from modules.calculations.engine import derive_activity_hours
    from modules.state.session_manager import workload_volumes

    servers = int(st.session_state.get("num_servers", 0) or 0)
    volumes = workload_volumes()

    activities = st.session_state.additional_activities

    # Names that count as "standard" (not custom) — drives the custom flag.
    STD_NAMES = {
        "Scheduled Maintenance", "Root Cause Analysis (RCA)", "Problem Management",
        "Documentation & Knowledge Base", "Service Review Preparation", "Other",
    }
    ROLE_COLS = [("L1", "L1 %"), ("L2", "L2 %"), ("L3", "L3 %"),
                 ("Architect", "Arch %"), ("SDM", "SDM %"), ("SSDM", "SSDM %")]

    def _num(v):
        try:
            f = float(v)
            return 0.0 if pd.isna(f) else f
        except (TypeError, ValueError):
            return 0.0

    # Clickable formula reference
    with st.expander("ℹ️ How are the recommended default efforts calculated?"):
        st.markdown(
            "For activities marked **Auto**, the monthly effort is derived from your "
            "server count and ticket volumes as a recommendation. Untick **Auto** on any row "
            "to enter your own value. Formula: *(sum of the terms below) ÷ 60 = hours/month.*"
        )
        for nm, cfg in ACTIVITY_FORMULAS.items():
            h = derive_activity_hours(nm, servers, volumes)
            st.markdown(f"- **{nm}** = ({cfg['text']}) ÷ 60 → current default **{h:.1f} hrs/month**")
        st.caption(f"Using servers = {servers}, alerts = {volumes['alerts']}, "
                   f"incidents = {volumes['incidents']}, service requests = {volumes['service_requests']}, "
                   f"changes = {volumes['changes']}.")

    # ── Editable grid ─────────────────────────────────────────
    in_rows = []
    for act in activities:
        name = act.get("name", "")
        is_derived = name in ACTIVITY_FORMULAS
        auto = bool(act.get("auto", False)) and is_derived
        hrs = (round(derive_activity_hours(name, servers, volumes), 1)
               if auto else _num(act.get("hours", 0)))
        d = act.get("dist", {})
        row = {"Activity": name, "Auto": auto, "Monthly Hrs": hrs}
        for rk, col in ROLE_COLS:
            row[col] = _num(d.get(rk, 0))
        in_rows.append(row)

    pct_cfg = dict(min_value=0.0, max_value=100.0, step=5.0, format="%d%%")
    edited = st.data_editor(
        pd.DataFrame(in_rows), key="act_editor", hide_index=True,
        use_container_width=True, num_rows="dynamic",
        column_config={
            "Activity": st.column_config.TextColumn(
                "Activity", width="medium",
                help="The four standard names (Scheduled Maintenance, RCA, Problem "
                     "Management, Documentation & Knowledge Base) drive the Auto formulas."),
            "Auto": st.column_config.CheckboxColumn(
                "Auto", default=False,
                help="On: hours auto-derived from servers/volumes (standard activities "
                     "only). Off: type your own Monthly Hrs."),
            "Monthly Hrs": st.column_config.NumberColumn(
                "Monthly Hrs", min_value=0.0, step=0.5, format="%.1f",
                help="Auto rows are formula-driven (edits revert); untick Auto to set your own."),
            "L1 %":   st.column_config.NumberColumn("L1 %", **pct_cfg),
            "L2 %":   st.column_config.NumberColumn("L2 %", **pct_cfg),
            "L3 %":   st.column_config.NumberColumn("L3 %", **pct_cfg),
            "Arch %": st.column_config.NumberColumn("Arch %", **pct_cfg),
            "SDM %":  st.column_config.NumberColumn("SDM %", **pct_cfg),
            "SSDM %": st.column_config.NumberColumn("SSDM %", **pct_cfg),
        },
    )

    # ── Persist back to the session contract (name/auto/custom/hours/dist) ──
    new_acts = []
    for _, r in edited.iterrows():
        nm = r["Activity"]
        name = ("" if pd.isna(nm) else str(nm).strip()) or "Custom Activity"
        is_derived = name in ACTIVITY_FORMULAS
        auto = (bool(r["Auto"]) if not pd.isna(r["Auto"]) else False) and is_derived
        hours = (round(derive_activity_hours(name, servers, volumes), 1)
                 if auto else _num(r["Monthly Hrs"]))
        dist = {rk: _num(r[col]) for rk, col in ROLE_COLS}
        new_acts.append({"name": name, "hours": hours, "custom": name not in STD_NAMES,
                         "auto": auto, "dist": dist})
    st.session_state["additional_activities"] = new_acts

    # ── Read-only validation / results table ──────────────────
    all_valid = True
    total = 0.0
    detail = ""
    for a in new_acts:
        s = sum(a["dist"].values()); total += a["hours"]
        ok = (a["hours"] == 0) or (abs(s - 100.0) < 0.1)
        if not ok:
            all_valid = False
        pill = ('<span class="pill-ok">✓ 100%</span>' if ok
                else f'<span class="pill-err">{s:.0f}%</span>')
        auto_txt = "Auto" if a["auto"] else "Manual"
        detail += (f"<tr><td>{a['name']}</td><td>{auto_txt}</td>"
                   f"<td class='r'>{a['hours']:.1f}</td><td class='r'>{s:.0f}%</td>"
                   f"<td style='text-align:center'>{pill}</td></tr>")
    st.markdown(f"""
    <table class="styled-table"><thead><tr>
      <th>Activity</th><th>Source</th><th class="r">Monthly Hrs</th>
      <th class="r">Role % Sum</th><th style="text-align:center">Valid</th>
    </tr></thead><tbody>{detail}</tbody></table>""", unsafe_allow_html=True)

    st.info(f"**Total Additional Activity Hours: {total:.1f} hrs/month**")

    if not all_valid:
        st.error("❌ For every activity with Monthly Hours > 0, the role percentages "
                 "must sum to exactly 100%. Fix the rows flagged above.")
        return False
    return True


# ── Step 5: Effort Summary & Contingency ──────────────────────────────────────

def _compute_all_effort():
    """Compute every effort component from session state. Returns full breakdown dict."""
    from modules.state.session_manager import refresh_auto_activity_hours
    refresh_auto_activity_hours()
    _, alert_h  = calc_category_hours(st.session_state.alerts)
    _, sr_h     = calc_category_hours(st.session_state.service_requests)
    _, inc_h    = calc_category_hours(st.session_state.incidents)
    _, chg_h    = calc_category_hours(st.session_state.changes)

    patch = calc_patching_effort(
        st.session_state.get("patching_included") == "Yes",
        st.session_state.get("num_servers", 0),
        st.session_state.get("patching_method") or "Manual",
        st.session_state.get("manual_effort_per_server", 45),
        st.session_state.get("auto_effort_per_server", 30),
        error_rate_pct=st.session_state.get("patch_error_rate", 0),
    )
    add_h = sum(r["hours"] for r in st.session_state.additional_activities)

    breakdown = calc_base_effort(alert_h, sr_h, inc_h, chg_h, patch["hours"], add_h)
    return breakdown


def render_step5() -> bool:
    page_header(5, "Effort Summary & Contingency",
                "Review base effort breakdown, apply contingency, and confirm role hours.")

    breakdown = _compute_all_effort()
    base_effort = breakdown["Base Effort"]

    # ── Effort breakdown table ────────────────────────────────
    section_hdr("📊 Base Operational Effort Breakdown")
    rows_html = ""
    for k, v in breakdown.items():
        if k == "Base Effort":
            rows_html += (
                f"<tr class='total-row'><td>Base Monthly Operational Effort</td>"
                f"<td class='r'><strong>{v:.1f}</strong></td>"
                f"<td class='r'><strong>100.0%</strong></td></tr>"
            )
        else:
            pct = (v / base_effort * 100) if base_effort > 0 else 0
            rows_html += f"<tr><td>{k}</td><td class='r'>{v:.1f}</td><td class='r'>{pct:.1f}%</td></tr>"

    st.markdown(f"""
    <table class="styled-table">
      <thead><tr>
        <th>Source</th>
        <th class="r">Hours / Month</th>
        <th class="r">% of Base</th>
      </tr></thead>
      <tbody>{rows_html}</tbody>
    </table>""", unsafe_allow_html=True)

    # ── Contingency ───────────────────────────────────────────
    st.divider()
    section_hdr("🔄 Contingency Buffer")
    contingency_pct = st.number_input(
        "**Contingency Percentage (%)**",
        min_value=0.0, max_value=50.0, step=1.0,
        value=float(st.session_state.get("contingency_pct", 10.0)),
        key="contingency_pct_w",
        help="Buffer for unplanned work. Typical range: 10–20%.",
    )
    st.session_state["contingency_pct"] = contingency_pct
    if contingency_pct > 30:
        callout("⚠️ Contingency above 30% is unusually high. Please confirm.", "warning")

    cont = calc_contingency(base_effort, contingency_pct)
    total_effort = cont["total_effort"]
    st.session_state["_total_effort"] = total_effort

    m1, m2, m3 = st.columns(3)
    m1.metric("Base Effort",        f"{base_effort:.1f} hrs")
    m2.metric("Contingency Hours",  f"{cont['contingency_hours']:.1f} hrs")
    m3.metric("Total Operational Effort", f"{total_effort:.1f} hrs")

    # Overhead role effort (relocated here from Step 2)
    st.divider()
    from modules.inputs.steps_1_2 import render_overhead_inputs
    render_overhead_inputs()

    # ── Role hours preview (from resolution split) ─────────────
    st.divider()
    section_hdr("👥 Indicative Role Hours (from Resolution Split)")

    ticket_role_hours = calc_all_ticket_role_hours(
        st.session_state.alerts,
        st.session_state.service_requests,
        st.session_state.incidents,
        st.session_state.changes,
    )

    overhead_role_hours = calc_overhead_hours(total_effort, st.session_state.overhead_pcts)

    patch_hours = breakdown.get("Patching", 0.0)
    patching_role = st.session_state.get("patching_role", "L2")
    
    add_h = sum(r["hours"] for r in st.session_state.additional_activities)

    full_role_hours = assemble_role_hours(
        ticket_role_hours, 
        overhead_role_hours, 
        patch_hours, 
        patching_role,
        additional_activities=st.session_state.additional_activities,
        contingency_pct=contingency_pct
    )
    st.session_state["_role_hours"] = full_role_hours

    from config.settings import ALL_ROLES
    rows_html2 = ""
    total_assigned = sum(full_role_hours.values())
    for role in ALL_ROLES:
        h = full_role_hours[role]
        pct = (h / total_effort * 100) if total_effort > 0 else 0
        badge = ""
        if role in ["L1", "L2", "L3"]:
            badge = f" <span style='color:#2A8A8A;font-size:0.75rem'>(resolution split)</span>"
        elif role == patching_role:
            badge = f" <span style='color:#2A8A8A;font-size:0.75rem'>(incl. patching)</span>"
        else:
            badge = f" <span style='color:#2A8A8A;font-size:0.75rem'>(overhead %)</span>"
        rows_html2 += f"<tr><td>{role}{badge}</td><td class='r'>{h:.1f}</td><td class='r'>{pct:.1f}%</td></tr>"
    rows_html2 += (
        f"<tr class='total-row'><td><strong>Total Assigned</strong></td>"
        f"<td class='r'><strong>{total_assigned:.1f}</strong></td><td class='r'>—</td></tr>"
    )

    callout(
        "ℹ️ Note: Overhead roles (Architect/SDM/SSDM) are additive. "
        "Total assigned hours may exceed operational effort because overhead is calculated "
        "separately on top of ticket resolution hours.",
        "info",
    )

    st.markdown(f"""
    <table class="styled-table">
      <thead><tr>
        <th>Role</th>
        <th class="r">Hours / Month</th>
        <th class="r">% of Total Effort</th>
      </tr></thead>
      <tbody>{rows_html2}</tbody>
    </table>""", unsafe_allow_html=True)

    return True
