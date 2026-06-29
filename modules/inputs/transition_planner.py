"""
Transition & Onboarding Planner — a dynamic phase/week resource grid rendered as a
section inside Step 8 (Costing Inputs).

Flow:  enable → total duration → configurable phases (must sum to duration) →
resource roster (role × count) → per-phase weekly utilisation grids → live cost →
commercial treatment (recurring / one-time / absorb).

Nothing is hardcoded: weeks, phases, phase names and roster rows are all dynamic.
Cost reuses the same Genus INR rates as the monthly model (no separate costing).
State lives in st.session_state["transition_planner"]; the engine reads it via
compute_full_model → calc_transition_cost.
"""
import uuid

import streamlit as st

from config.settings import (
    TRANSITION_DURATION_PRESETS, DEFAULT_TRANSITION_PHASES, TRANSITION_DEFAULT_ROLES,
    TRANSITION_UTIL_OPTIONS, TRANSITION_WEEKLY_HOURS, ALL_ROLES,
)
from modules.calculations.engine import (
    calc_transition_cost, transition_week_phase_map, resolve_role_rates,
)
from modules.inputs.steps_1_2 import section_hdr, callout
from utils.formatters import fmt_currency

# Utilisation picker: store floats, show friendly % labels in the grid.
_UTIL_LABELS = {0.0: "0%", 0.25: "25%", 0.5: "50%", 1.0: "100%"}
_LABEL_UTIL = {v: k for k, v in _UTIL_LABELS.items()}


def _new_id() -> str:
    return uuid.uuid4().hex[:8]


def _seed_defaults(tp: dict):
    """Populate sensible default phases + roster the first time the planner is
    enabled with nothing configured yet. Phase weeks are spread to sum to the
    current total duration so validation passes out of the box."""
    total = int(tp.get("total_weeks", 8) or 8)
    if not tp.get("phases"):
        n = len(DEFAULT_TRANSITION_PHASES)
        base, extra = divmod(total, n)
        tp["phases"] = [
            {"id": _new_id(), "name": name, "weeks": base + (1 if i < extra else 0)}
            for i, name in enumerate(DEFAULT_TRANSITION_PHASES)
        ]
    if not tp.get("resources"):
        tp["resources"] = [
            {"id": _new_id(), "role": role, "count": 1} for role in TRANSITION_DEFAULT_ROLES
        ]
    tp.setdefault("allocation", {})


def _resolve_rates() -> dict:
    """Current per-role INR rates from the uploaded rate card scoped to the selected
    delivery location — the same resolution build_model_state uses."""
    return resolve_role_rates(
        st.session_state.get("rate_card_df"),
        st.session_state.get("role_genus", {}) or {},
        st.session_state.get("delivery_country"),
        st.session_state.get("delivery_location"),
        st.session_state.get("exchange_rates", {}) or {},
    )


def _sync_phases(tp: dict):
    """Phases as individual single-entry inputs (distinct id-keyed widgets + write-back),
    with per-row delete and an add button."""
    hc = st.columns([3, 1, 0.5])
    hc[0].markdown("<div style='font-size:0.76rem;color:#1A5F6A;font-weight:600'>Phase</div>",
                   unsafe_allow_html=True)
    hc[1].markdown("<div style='font-size:0.76rem;color:#1A5F6A;font-weight:600'>Weeks</div>",
                   unsafe_allow_html=True)
    to_remove = []
    for i, ph in enumerate(tp.get("phases", [])):
        pid = ph["id"]
        c = st.columns([3, 1, 0.5])
        name = c[0].text_input(f"Phase name {i}", value=str(ph.get("name", "")),
                               key=f"tp_ph_name_{pid}", label_visibility="collapsed")
        weeks = c[1].number_input(f"Phase weeks {i}", min_value=0, step=1,
                                  value=int(ph.get("weeks", 0) or 0),
                                  key=f"tp_ph_wk_{pid}", label_visibility="collapsed")
        if c[2].button("🗑️", key=f"tp_ph_del_{pid}", help="Remove this phase"):
            to_remove.append(pid)
        ph["name"] = name.strip() or "Phase"
        ph["weeks"] = int(max(0, weeks))
    if to_remove:
        tp["phases"] = [p for p in tp["phases"] if p["id"] not in to_remove]
        st.rerun()
    if st.button("➕ Add phase", key="tp_ph_add", type="secondary"):
        tp["phases"].append({"id": _new_id(), "name": "New Phase", "weeks": 0})
        st.rerun()


def _sync_roster(tp: dict):
    """Roster as individual single-entry inputs (distinct id-keyed widgets + write-back),
    with per-row delete and an add button."""
    hc = st.columns([3, 1, 0.5])
    hc[0].markdown("<div style='font-size:0.76rem;color:#1A5F6A;font-weight:600'>Role</div>",
                   unsafe_allow_html=True)
    hc[1].markdown("<div style='font-size:0.76rem;color:#1A5F6A;font-weight:600'>Count</div>",
                   unsafe_allow_html=True)
    to_remove = []
    for i, r in enumerate(tp.get("resources", [])):
        rid = r["id"]
        c = st.columns([3, 1, 0.5])
        role = c[0].selectbox(f"Role {i}", ALL_ROLES,
                              index=ALL_ROLES.index(r["role"]) if r.get("role") in ALL_ROLES else 0,
                              key=f"tp_res_role_{rid}", label_visibility="collapsed")
        count = c[1].number_input(f"Count {i}", min_value=0, step=1,
                                  value=int(r.get("count", 0) or 0),
                                  key=f"tp_res_cnt_{rid}", label_visibility="collapsed")
        if c[2].button("🗑️", key=f"tp_res_del_{rid}", help="Remove this resource"):
            to_remove.append(rid)
        r["role"] = role
        r["count"] = int(max(0, count))
    if to_remove:
        tp["resources"] = [x for x in tp["resources"] if x["id"] not in to_remove]
        for rid in to_remove:
            tp.get("allocation", {}).pop(rid, None)
        st.rerun()
    if st.button("➕ Add resource", key="tp_res_add", type="secondary"):
        tp["resources"].append({"id": _new_id(), "role": ALL_ROLES[0], "count": 1})
        st.rerun()


def _render_weekly_grids(tp: dict, total_weeks: int):
    """One mini-grid per phase, stacked, with that phase's week columns. Rows are the
    roster resources; each cell is the weekly utilisation (constrained picker)."""
    resources = tp.get("resources", [])
    if not resources:
        callout("Add at least one resource to the roster above to plan weekly utilisation.", "info")
        return
    week_phase = transition_week_phase_map(tp.get("phases", []), total_weeks)
    # group week numbers under each phase, in order
    phase_weeks = {}
    for wk in range(1, total_weeks + 1):
        ph = week_phase.get(wk)
        if ph:
            phase_weeks.setdefault(ph, []).append(wk)

    alloc = tp.setdefault("allocation", {})
    util_opts = list(_UTIL_LABELS.values())          # ["0%", "25%", "50%", "100%"]
    seen = {}
    res_labels = {}
    for r in resources:
        seen[r["role"]] = seen.get(r["role"], 0) + 1
        res_labels[r["id"]] = f"{r['role']} #{seen[r['role']]}"

    for phase_name, weeks in phase_weeks.items():
        span = f"W{weeks[0]}" if len(weeks) == 1 else f"W{weeks[0]}–W{weeks[-1]}"
        st.markdown(
            f"<div class='tp-phase-band' style='background:#1A5F6A;color:#fff;"
            f"padding:4px 10px;border-radius:6px 6px 0 0;font-weight:600;font-size:0.9rem'>"
            f"{phase_name} · {span}</div>", unsafe_allow_html=True)
        widths = [1.5] + [1] * len(weeks)
        hc = st.columns(widths)
        hc[0].markdown("<div style='font-size:0.74rem;color:#1A5F6A;font-weight:600'>Resource</div>",
                       unsafe_allow_html=True)
        for j, wk in enumerate(weeks):
            hc[j + 1].markdown(f"<div style='font-size:0.74rem;color:#1A5F6A;font-weight:600'>W{wk}</div>",
                               unsafe_allow_html=True)
        for r in resources:
            rid = r["id"]
            r_alloc = alloc.setdefault(rid, {})
            rc = st.columns(widths)
            rc[0].markdown(f"<div style='padding-top:6px;font-size:0.85rem'>{res_labels[rid]}</div>",
                           unsafe_allow_html=True)
            for j, wk in enumerate(weeks):
                cur = float(r_alloc.get(str(wk), r_alloc.get(wk, 0.0)) or 0.0)
                cur_lbl = _UTIL_LABELS.get(cur, "0%")
                sel = rc[j + 1].selectbox(
                    f"util {rid} {wk}", util_opts, index=util_opts.index(cur_lbl),
                    key=f"tp_u_{rid}_{wk}", label_visibility="collapsed")
                r_alloc[str(wk)] = _LABEL_UTIL.get(sel, 0.0)


def render_transition_planner():
    """Render the whole Transition & Onboarding Planner section (Step 8)."""
    section_hdr("🚀 Transition & Onboarding Planner")
    tp = st.session_state.setdefault("transition_planner", {})

    enabled = st.radio(
        "Include Transition & Onboarding?", ["Yes", "No"],
        index=0 if tp.get("enabled") else 1, key="tp_enabled", horizontal=True)
    tp["enabled"] = (enabled == "Yes")
    if not tp["enabled"]:
        st.caption("Plan transition phases and staff each week to auto-calculate the "
                   "onboarding cost, then choose how to recover it commercially.")
        st.session_state["transition_planner"] = tp
        return

    _seed_defaults(tp)

    # ── Duration ──────────────────────────────────────────────
    dur_options = sorted(set(TRANSITION_DURATION_PRESETS) | {int(tp.get("total_weeks", 8))})
    d1, d2 = st.columns([1, 2])
    with d1:
        total_weeks = st.selectbox(
            "Total Transition Duration (weeks)", dur_options,
            index=dur_options.index(int(tp.get("total_weeks", 8))), key="tp_total_weeks")
    prev_weeks = int(tp.get("total_weeks", 8) or 8)
    if total_weeks < prev_weeks:
        # warn before dropping weeks that hold utilisation data
        dropped = range(total_weeks + 1, prev_weeks + 1)
        has_data = any(
            float(a.get(str(w), a.get(w, 0)) or 0) > 0
            for a in tp.get("allocation", {}).values() for w in dropped)
        if has_data:
            callout(f"⚠️ Reducing to {total_weeks} weeks removes utilisation entered in "
                    f"weeks {total_weeks + 1}–{prev_weeks}.", "warning")
    tp["total_weeks"] = int(total_weeks)

    # ── Phases ────────────────────────────────────────────────
    st.markdown("**Phases** — rename, add, delete or reorder; set each phase's weeks.")
    _sync_phases(tp)
    allocated = sum(int(p.get("weeks", 0) or 0) for p in tp.get("phases", []))
    remaining = tp["total_weeks"] - allocated
    if remaining == 0:
        callout(f"✅ Allocated {allocated} / {tp['total_weeks']} weeks.", "success")
        phases_ok = True
    elif remaining > 0:
        callout(f"Allocated {allocated} / {tp['total_weeks']} — Remaining {remaining} week(s). "
                "Allocate every week before the cost is final.", "warning")
        phases_ok = False
    else:
        callout(f"Allocated {allocated} / {tp['total_weeks']} — Exceeded by {-remaining} week(s). "
                "Reduce phase durations to match the total.", "warning")
        phases_ok = False

    # ── Roster ────────────────────────────────────────────────
    st.markdown("**Resource Roster** — the people on the transition team.")
    _sync_roster(tp)

    # ── Weekly allocation grids ───────────────────────────────
    st.markdown("**Weekly Allocation** — utilisation per resource per week, grouped by phase.")
    if phases_ok:
        _render_weekly_grids(tp, tp["total_weeks"])
    else:
        callout("Match the phase durations to the total duration to plan weekly utilisation.", "info")

    # ── Live cost + commercial treatment ──────────────────────
    rates = _resolve_rates()
    trans = calc_transition_cost(tp, rates)
    _render_cost_and_treatment(tp, trans)

    st.session_state["transition_planner"] = tp


def _render_cost_and_treatment(tp: dict, trans: dict):
    """Per-resource cost table + commercial-treatment chooser, themed to match."""
    st.markdown("**Transition Cost** "
                f"<span style='color:#6B7B7B;font-size:0.8rem'>(full-capacity week = "
                f"{TRANSITION_WEEKLY_HOURS:.0f} hrs)</span>", unsafe_allow_html=True)
    rows = ""
    for pr in trans.get("per_resource", []):
        rate_note = "" if pr["rate_inr"] > 0 else " ⚠️ no rate"
        rows += (f"<tr><td>{pr['role']}{rate_note}</td><td class='r'>{pr['count']:.0f}</td>"
                 f"<td class='r'>{pr['hours']:.0f}</td>"
                 f"<td class='r'>{fmt_currency(pr['rate_inr'])}</td>"
                 f"<td class='r'>{fmt_currency(pr['cost'])}</td></tr>")
    rows += (f"<tr class='total-row'><td><strong>TOTAL TRANSITION COST</strong></td>"
             f"<td></td><td></td><td></td>"
             f"<td class='r'><strong>{fmt_currency(trans.get('total', 0))}</strong></td></tr>")
    st.markdown(
        f"""<table class="styled-table"><thead><tr>
        <th>Role</th><th class="r">Count</th><th class="r">Hours</th>
        <th class="r">Rate (INR/hr)</th><th class="r">Cost (INR)</th></tr></thead>
        <tbody>{rows}</tbody></table>""", unsafe_allow_html=True)
    if any(pr["rate_inr"] <= 0 for pr in trans.get("per_resource", [])):
        callout("Some roles have no resolved rate — set their Genus in Step 7 (Grade Mapping) "
                "so the transition cost is complete.", "warning")

    st.markdown("**Commercial Treatment**")
    treat_labels = {
        "recurring": "Recover via Monthly Recurring Charges",
        "one_time":  "Recover as a One-Time Fee",
        "absorb":    "Absorb Internally (discount)",
    }
    keys = list(treat_labels.keys())
    cur = tp.get("treatment", "recurring")
    choice = st.radio(
        "How should the transition cost be recovered?",
        keys, index=keys.index(cur) if cur in keys else 0,
        format_func=lambda k: treat_labels[k], key="tp_treatment")
    tp["treatment"] = choice

    total = trans.get("total", 0.0)
    if choice == "recurring":
        months = st.number_input(
            "Amortisation period (months)", min_value=1, max_value=120,
            value=int(tp.get("amortisation_months", 12) or 12), step=1, key="tp_months",
            help="Monthly transition charge = Total Transition Cost ÷ this period, added "
                 "to the monthly selling price (post-margin).")
        tp["amortisation_months"] = int(months)
        callout(f"Adds <strong>{fmt_currency(total / max(int(months), 1))}/month</strong> "
                f"to the monthly selling price (₹{total:,.0f} ÷ {int(months)} months).", "success")
    elif choice == "one_time":
        callout(f"Shown as a separate one-time line: "
                f"<strong>{fmt_currency(total)}</strong> (not in the monthly price).", "success")
    else:  # absorb
        callout(f"Transition <strong>{fmt_currency(total)}</strong> · "
                f"Absorbed <strong>−{fmt_currency(total)}</strong> · "
                f"Net charged <strong>{fmt_currency(0)}</strong>.", "success")
