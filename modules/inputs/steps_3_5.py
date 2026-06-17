"""
Step 3 — Patching Effort
Step 4 — Additional Operational Activities
Step 5 — Effort Summary & Contingency
"""
import streamlit as st
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
        "Define effort for recurring tasks and support operations. "
        "Assign the percentage distribution of hours for each role. "
        "For any activity with hours > 0, the sum of role percentages must be exactly 100%.",
        "info",
    )

    activities = st.session_state.additional_activities
    to_remove = []

    from config.settings import ALL_ROLES, ACTIVITY_FORMULAS
    from modules.calculations.engine import derive_activity_hours
    from modules.state.session_manager import workload_volumes

    servers = int(st.session_state.get("num_servers", 0) or 0)
    volumes = workload_volumes()

    # Clickable formula reference
    with st.expander("ℹ️ How are the recommended default efforts calculated?"):
        st.markdown(
            "For activities below marked **Auto**, the monthly effort is derived from your "
            "server count and ticket volumes as a recommendation. Untick **Auto** on any row "
            "to enter your own value. Formula: *(sum of the terms below) ÷ 60 = hours/month.*"
        )
        for nm, cfg in ACTIVITY_FORMULAS.items():
            h = derive_activity_hours(nm, servers, volumes)
            st.markdown(f"- **{nm}** = ({cfg['text']}) ÷ 60 → current default **{h:.1f} hrs/month**")
        st.caption(f"Using servers = {servers}, alerts = {volumes['alerts']}, "
                   f"incidents = {volumes['incidents']}, service requests = {volumes['service_requests']}, "
                   f"changes = {volumes['changes']}.")

    # 1. Header row
    h0, h1, hauto, hl1, hl2, hl3, harch, hsdm, hssdm, h_del = st.columns(
        [2.6, 1.0, 0.8, 0.85, 0.85, 0.85, 0.85, 0.85, 0.85, 0.9])
    h0.markdown("**Activity Name**")
    h1.markdown("**Monthly Hrs**")
    hauto.markdown("**Auto**")
    hl1.markdown("**L1 %**")
    hl2.markdown("**L2 %**")
    hl3.markdown("**L3 %**")
    harch.markdown("**Arch %**")
    hsdm.markdown("**SDM %**")
    hssdm.markdown("**SSDM %**")
    h_del.markdown("**Status**")

    all_valid = True

    for i, row in enumerate(activities):
        c0, c1, c_auto, cl1, cl2, cl3, carch, csdm, cssdm, c_del = st.columns(
            [2.6, 1.0, 0.8, 0.85, 0.85, 0.85, 0.85, 0.85, 0.85, 0.9])

        name = row["name"]
        formula = ACTIVITY_FORMULAS.get(name)
        is_derived = formula is not None
        formula_help = (f"Default = ({formula['text']}) ÷ 60" if is_derived else None)

        # Editable name for custom rows
        if row.get("custom"):
            name = c0.text_input("Name", value=row["name"],
                                 key=f"act_name_{i}", label_visibility="collapsed")
            activities[i]["name"] = name
        else:
            c0.markdown(f"*{row['name']}*")

        # Auto toggle (only for activities that have a derivation formula)
        if is_derived:
            auto = c_auto.checkbox("Auto", value=row.get("auto", True),
                                   key=f"act_auto_{i}", label_visibility="collapsed",
                                   help="On: effort auto-derived from volumes. Off: enter your own.")
            activities[i]["auto"] = auto
        else:
            auto = False
            c_auto.markdown("<div style='color:#888;text-align:center'>—</div>", unsafe_allow_html=True)

        # Monthly hours — disabled & formula-driven when Auto is on
        if is_derived and auto:
            derived_h = round(derive_activity_hours(name, servers, volumes), 1)
            activities[i]["hours"] = derived_h
            hours = derived_h
            c1.number_input("hrs", value=derived_h, disabled=True,
                            key=f"act_hrs_auto_{i}", label_visibility="collapsed",
                            help=formula_help)
        else:
            hours = c1.number_input(
                "hrs", min_value=0.0, step=0.5, format="%.1f",
                value=float(row["hours"]),
                key=f"act_hrs_{i}",
                label_visibility="collapsed",
                help=formula_help,
            )
            activities[i]["hours"] = hours

        # Role percentages
        dist = row.setdefault("dist", {r: 0.0 for r in ALL_ROLES})
        
        # We render inputs for each role
        dist["L1"] = cl1.number_input("L1%", min_value=0.0, max_value=100.0, step=5.0, format="%.0f", value=float(dist.get("L1", 0.0)), key=f"act_l1_{i}", label_visibility="collapsed")
        dist["L2"] = cl2.number_input("L2%", min_value=0.0, max_value=100.0, step=5.0, format="%.0f", value=float(dist.get("L2", 0.0)), key=f"act_l2_{i}", label_visibility="collapsed")
        dist["L3"] = cl3.number_input("L3%", min_value=0.0, max_value=100.0, step=5.0, format="%.0f", value=float(dist.get("L3", 0.0)), key=f"act_l3_{i}", label_visibility="collapsed")
        dist["Architect"] = carch.number_input("Arch%", min_value=0.0, max_value=100.0, step=5.0, format="%.0f", value=float(dist.get("Architect", 0.0)), key=f"act_arch_{i}", label_visibility="collapsed")
        dist["SDM"] = csdm.number_input("SDM%", min_value=0.0, max_value=100.0, step=5.0, format="%.0f", value=float(dist.get("SDM", 0.0)), key=f"act_sdm_{i}", label_visibility="collapsed")
        dist["SSDM"] = cssdm.number_input("SSDM%", min_value=0.0, max_value=100.0, step=5.0, format="%.0f", value=float(dist.get("SSDM", 0.0)), key=f"act_ssdm_{i}", label_visibility="collapsed")

        # Validation status & action button
        total_pct = sum(dist.get(r, 0.0) for r in ALL_ROLES)
        is_valid = (hours == 0) or (abs(total_pct - 100.0) < 0.1)
        
        if not is_valid:
            all_valid = False
            
        # Display validation indicator / delete button
        if row.get("custom"):
            with c_del:
                sub_c1, sub_c2 = st.columns([0.6, 0.4])
                if not is_valid:
                    sub_c1.markdown(f'<span class="pill-err" style="padding: 2px 4px; font-size: 0.75rem;" title="Must sum to 100% (currently {total_pct:.0f}%)">⚠️{total_pct:.0f}%</span>', unsafe_allow_html=True)
                elif hours > 0:
                    sub_c1.markdown('<span class="pill-ok" style="padding: 2px 4px; font-size: 0.75rem;">✓</span>', unsafe_allow_html=True)
                else:
                    sub_c1.markdown('<span style="color:#888;">—</span>', unsafe_allow_html=True)
                
                if sub_c2.button("🗑️", key=f"del_act_{i}", help="Remove activity"):
                    to_remove.append(i)
        else:
            if not is_valid:
                c_del.markdown(f'<span class="pill-err" style="padding: 2px 6px; font-size: 0.8rem;" title="Must sum to 100% (currently {total_pct:.0f}%)">⚠️ {total_pct:.0f}%</span>', unsafe_allow_html=True)
            elif hours > 0:
                c_del.markdown('<span class="pill-ok" style="padding: 2px 6px; font-size: 0.8rem;">✓ 100%</span>', unsafe_allow_html=True)
            else:
                c_del.markdown('<span style="color:#888; font-size: 0.8rem;">—</span>', unsafe_allow_html=True)

    for idx in reversed(to_remove):
        activities.pop(idx)
        st.rerun()

    if st.button("➕ Add Activity", type="secondary"):
        activities.append({
            "name": "Custom Activity", 
            "hours": 0.0, 
            "custom": True, 
            "dist": {r: (100.0 if r == "L2" else 0.0) for r in ALL_ROLES}
        })
        st.rerun()

    total = sum(r["hours"] for r in activities)
    st.info(f"**Total Additional Activity Hours: {total:.1f} hrs/month**")
    
    if not all_valid:
        st.error("❌ The sum of role percentages for all active activities (where Monthly Hours > 0) must be exactly 100%. Please check the highlighted errors above.")
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
