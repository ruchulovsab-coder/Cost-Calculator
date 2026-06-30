"""
Multi-skill estimation UI (Phase 2). A self-contained flow shown when
st.session_state["estimation_mode"] == "multi" — it does NOT touch the single-tower
stepper, so single mode is unaffected.

Sections (tabs): 1·Skills setup → 2·Per-skill Workload → 3·Effort & FTE dashboard.
Inputs are single-entry widgets (distinct keys + write-back), like the rest of the app.
Cost/price (InfraOps/CloudOps rate families) lands in Phase 3 — this slice shows effort
and FTE per skill. Engine: engine.compute_multi_skill_model. See docs/multi-skill-strategy.md.
"""
import uuid

import streamlit as st

from config.settings import COVERAGE_MODELS, DEFAULT_ROLE_BUFFER_PCT
from modules.inputs.steps_1_2 import section_hdr, callout, page_header
from modules.calculations.engine import compute_multi_skill_model
from utils.formatters import fmt_hours

CATEGORIES = [("alerts", "Monitoring Alerts"), ("service_requests", "Service Requests"),
              ("incidents", "Incidents"), ("changes", "Change Requests")]
LEVELS = ["L1", "L2", "L3"]
GENUS = ["InfraOps", "CloudOps"]
COV_MODELS = [m for m in COVERAGE_MODELS if m != "Custom"]


def _new_id() -> str:
    return uuid.uuid4().hex[:8]


# ──────────────────────────────────────────────────────────────────────────────
# Mode chooser (shown once on Manual → Start afresh)
# ──────────────────────────────────────────────────────────────────────────────
def render_mode_chooser():
    """Single vs Multi-skill. Sets estimation_mode + marks it resolved."""
    st.markdown("<div style='max-width:760px;margin:6vh auto 0'>", unsafe_allow_html=True)
    page_header(0, "How do you want to build this estimate?",
                "Pick the estimation mode. You can change skills later; single is the classic flow.")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("#### 🧱 Single skill (default)")
        st.caption("One support tower split by L1/L2/L3 — the classic flow, unchanged.")
        if st.button("Use Single-skill", key="ms_pick_single", type="primary", use_container_width=True):
            st.session_state["estimation_mode"] = "single"
            st.session_state["_ms_mode_resolved"] = True
            st.rerun()
    with c2:
        st.markdown("#### 🧩 Multi-skill")
        st.caption("Several skills (Security, Cloud, DevOps…), each with its own volumes, "
                   "levels, coverage and architect; priced by InfraOps/CloudOps bands.")
        if st.button("Use Multi-skill", key="ms_pick_multi", type="primary", use_container_width=True):
            st.session_state["estimation_mode"] = "multi"
            st.session_state["_ms_mode_resolved"] = True
            _seed_first_skill()
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)


def _seed_first_skill():
    if not st.session_state.get("skills"):
        st.session_state["skills"] = [_blank_skill("Skill 1")]


def _blank_skill(name="New Skill"):
    return {"id": _new_id(), "name": name, "genus_category": "InfraOps",
            "active_levels": ["L1", "L2", "L3"], "has_architect": False, "architect_pct": 5.0,
            "coverage_model": "8×5", "visible": True, "level_visible": {},
            "workload": {}, "patching": None, "activities": []}


# ──────────────────────────────────────────────────────────────────────────────
# Tab 1 — Skills setup
# ──────────────────────────────────────────────────────────────────────────────
def _render_skill_setup():
    section_hdr("🧩 Skills")
    callout("Define each skill: tag its rate family (InfraOps / CloudOps), the levels it uses, "
            "its coverage model, and whether it has an Architect. Add or remove skills anytime.", "info")
    skills = st.session_state.setdefault("skills", [])
    to_remove = []
    for i, sk in enumerate(skills):
        sid = sk["id"]
        with st.container(border=True):
            c1, c2, c3 = st.columns([3, 2, 0.6])
            sk["name"] = c1.text_input("Skill name", value=sk.get("name", ""),
                                       key=f"ms_name_{sid}")
            sk["genus_category"] = c2.selectbox(
                "Rate family", GENUS,
                index=GENUS.index(sk.get("genus_category", "InfraOps")) if sk.get("genus_category") in GENUS else 0,
                key=f"ms_genus_{sid}")
            if c3.button("🗑️", key=f"ms_del_{sid}", help="Remove skill"):
                to_remove.append(sid)
            c4, c5, c6, c7 = st.columns([2.4, 1.6, 1, 1])
            sk["active_levels"] = c4.multiselect(
                "Active levels", LEVELS, default=sk.get("active_levels", LEVELS),
                key=f"ms_levels_{sid}")
            sk["coverage_model"] = c5.selectbox(
                "Coverage", COV_MODELS,
                index=COV_MODELS.index(sk.get("coverage_model", "8×5")) if sk.get("coverage_model") in COV_MODELS else 0,
                key=f"ms_cov_{sid}")
            sk["has_architect"] = c6.checkbox("Architect", value=bool(sk.get("has_architect")),
                                              key=f"ms_arch_{sid}")
            sk["architect_pct"] = c7.number_input(
                "Arch %", min_value=0.0, max_value=50.0, step=0.5,
                value=float(sk.get("architect_pct", 5.0) or 0.0), key=f"ms_archpct_{sid}",
                disabled=not sk.get("has_architect"))
    if to_remove:
        st.session_state["skills"] = [s for s in skills if s["id"] not in to_remove]
        st.rerun()
    if st.button("➕ Add skill", key="ms_add_skill", type="secondary"):
        skills.append(_blank_skill(f"Skill {len(skills) + 1}"))
        st.rerun()


# ──────────────────────────────────────────────────────────────────────────────
# Tab 2 — Per-skill workload (direct entry; one aggregate row per category)
# ──────────────────────────────────────────────────────────────────────────────
def _render_workload():
    section_hdr("📊 Per-skill Workload")
    skills = st.session_state.get("skills", [])
    if not skills:
        callout("Add a skill on the Skills tab first.", "info")
        return
    names = {s["id"]: s.get("name") or s["id"] for s in skills}
    sid = st.selectbox("Skill", list(names), format_func=lambda x: names[x], key="ms_wl_skill")
    sk = next(s for s in skills if s["id"] == sid)
    st.caption("Enter monthly volume, average minutes/ticket, and the L1/L2/L3 split per category "
               "for this skill. (Per-severity detail, patching and activities come in later phases.)")
    wl = sk.setdefault("workload", {})

    # Per-level effort buffer (was a hidden 20% default — now an explicit input per skill,
    # applied to every category below; drives the role hours on the Effort & FTE tab).
    rb = sk.setdefault("role_buffers", {lvl: DEFAULT_ROLE_BUFFER_PCT for lvl in LEVELS})
    st.markdown("<div style='font-size:0.82rem;color:#1A5F6A;font-weight:600;margin:.4rem 0 .1rem'>"
                "Per-level effort buffer %</div>", unsafe_allow_html=True)
    st.caption("Extra time added per level for wait/handover/non-productive overhead. Applied to "
               "this skill's role hours across all categories (set to 0 to price raw effort only).")
    bc = st.columns(3)
    for col, lvl in zip(bc, LEVELS):
        rb[lvl] = col.number_input(f"{lvl} buffer %", min_value=0.0, max_value=100.0, step=1.0,
                                   value=float(rb.get(lvl, DEFAULT_ROLE_BUFFER_PCT) or 0.0),
                                   key=f"ms_buf_{sid}_{lvl}")
    st.markdown("<div style='height:.4rem'></div>", unsafe_allow_html=True)

    hdr = st.columns([2, 1, 1, 1, 1, 1])
    for col, t in zip(hdr, ["Category", "Count", "Min/Ticket", "L1 %", "L2 %", "L3 %"]):
        col.markdown(f"<div style='font-size:0.76rem;color:#1A5F6A;font-weight:600'>{t}</div>",
                     unsafe_allow_html=True)
    for cat_key, cat_label in CATEGORIES:
        row = (wl.get(cat_key, {}) or {}).get("All", {})
        rc = st.columns([2, 1, 1, 1, 1, 1])
        rc[0].markdown(f"<div style='padding-top:6px;font-size:0.85rem'>{cat_label}</div>",
                       unsafe_allow_html=True)
        cnt = rc[1].number_input(f"{cat_key} count", min_value=0, step=10,
                                 value=int(row.get("count", 0) or 0),
                                 key=f"ms_{sid}_{cat_key}_count", label_visibility="collapsed")
        mins = rc[2].number_input(f"{cat_key} min", min_value=0.0, step=1.0,
                                  value=float(row.get("minutes", 0) or 0),
                                  key=f"ms_{sid}_{cat_key}_min", label_visibility="collapsed")
        l1 = rc[3].number_input(f"{cat_key} l1", min_value=0.0, max_value=100.0, step=1.0,
                                value=float(row.get("L1_pct", 0) or 0),
                                key=f"ms_{sid}_{cat_key}_l1", label_visibility="collapsed")
        l2 = rc[4].number_input(f"{cat_key} l2", min_value=0.0, max_value=100.0, step=1.0,
                                value=float(row.get("L2_pct", 0) or 0),
                                key=f"ms_{sid}_{cat_key}_l2", label_visibility="collapsed")
        l3 = rc[5].number_input(f"{cat_key} l3", min_value=0.0, max_value=100.0, step=1.0,
                                value=float(row.get("L3_pct", 0) or 0),
                                key=f"ms_{sid}_{cat_key}_l3", label_visibility="collapsed")
        wl[cat_key] = {"All": {"count": cnt, "minutes": mins, "L1_pct": l1, "L2_pct": l2, "L3_pct": l3,
                               "L1_buffer": rb["L1"], "L2_buffer": rb["L2"], "L3_buffer": rb["L3"]}}
        if abs(l1 + l2 + l3 - 100.0) > 0.5 and (l1 + l2 + l3) > 0:
            rc[0].markdown("<span style='color:#E74C3C;font-size:0.72rem'>L1+L2+L3 ≠ 100%</span>",
                           unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────────────────────
# Tab 3 — Engagement inputs + Effort/FTE dashboard
# ──────────────────────────────────────────────────────────────────────────────
def _build_multi_state() -> dict:
    ss = st.session_state
    return {
        "skills": ss.get("skills", []),
        "resource_sharing": ss.get("resource_sharing", []),
        "rates_by_category": {},                 # Phase 3 (InfraOps/CloudOps band rates)
        "sdm_overhead_pct": float(ss.get("sdm_overhead_pct", 5.0) or 0.0),
        "sdm_rate_inr": 0.0,
        "contingency_pct": float(ss.get("contingency_pct", 10.0) or 0.0),
        "monthly_working_hours": float(ss.get("monthly_working_hours", 160.0) or 160.0),
        "productive_utilisation": float(ss.get("productive_utilisation", 75.0) or 75.0),
        "fte_basis": ss.get("fte_basis", "rounded"),
        "custom_hours_per_day": ss.get("custom_hours_per_day", 8),
        "custom_days_per_week": ss.get("custom_days_per_week", 5),
        "additional_costs": [], "sla_provision_included": "No", "sla_provision_pct": 0.0,
        "target_margin_pct": float(ss.get("target_margin_pct", 20.0) or 0.0),
    }


def _render_dashboard():
    section_hdr("📈 Effort & FTE by Skill")
    if not st.session_state.get("skills"):
        callout("Add a skill and its workload first.", "info")
        return
    e1, e2, e3 = st.columns(3)
    st.session_state["monthly_working_hours"] = e1.number_input(
        "Monthly working hrs / FTE", min_value=1.0, step=1.0,
        value=float(st.session_state.get("monthly_working_hours", 160.0) or 160.0), key="ms_monthly")
    st.session_state["productive_utilisation"] = e2.number_input(
        "Productive utilisation %", min_value=1.0, max_value=100.0, step=1.0,
        value=float(st.session_state.get("productive_utilisation", 75.0) or 75.0), key="ms_util")
    st.session_state["contingency_pct"] = e3.number_input(
        "Contingency %", min_value=0.0, max_value=50.0, step=1.0,
        value=float(st.session_state.get("contingency_pct", 10.0) or 0.0), key="ms_cont")
    st.session_state["sdm_overhead_pct"] = st.number_input(
        "SDM overhead % (one engagement SDM)", min_value=0.0, max_value=50.0, step=0.5,
        value=float(st.session_state.get("sdm_overhead_pct", 5.0) or 0.0), key="ms_sdm")

    model = compute_multi_skill_model(_build_multi_state())
    names = {s["id"]: (s.get("name") or s["id"]) for s in st.session_state.get("skills", [])}
    rows = ""
    staffed_total = 0.0
    for sid, ps in model["per_skill"].items():
        rh = ps["role_hours"]
        staffed = rh["L1"] + rh["L2"] + rh["L3"] + rh["Architect"]   # row adds up across columns
        staffed_total += staffed
        rows += (f"<tr><td>{names.get(sid, sid)}</td><td>{ps['genus_category']}</td>"
                 f"<td class='r'>{rh['L1']:.1f}</td><td class='r'>{rh['L2']:.1f}</td>"
                 f"<td class='r'>{rh['L3']:.1f}</td><td class='r'>{rh['Architect']:.1f}</td>"
                 f"<td class='r'>{staffed:.1f}</td><td class='r' style='color:#7A8A99'>{ps['total_effort']:.1f}</td></tr>")
    rows += (f"<tr class='total-row'><td><strong>Engagement</strong></td><td></td><td></td><td></td>"
             f"<td></td><td></td><td class='r'><strong>{staffed_total:.1f}</strong></td>"
             f"<td class='r' style='color:#7A8A99'><strong>{model['engagement_total_effort']:.1f}</strong></td></tr>")
    st.markdown(
        f"""<table class="styled-table"><thead><tr>
        <th>Skill</th><th>Family</th><th class="r">L1 hrs</th><th class="r">L2 hrs</th>
        <th class="r">L3 hrs</th><th class="r">Arch hrs</th><th class="r">Staffed hrs</th>
        <th class="r">Effort (pre-buffer)</th>
        </tr></thead><tbody>{rows}</tbody></table>""", unsafe_allow_html=True)
    st.caption("**Staffed hrs** = L1+L2+L3+Arch role hours (includes the per-level buffer set on the "
               "Workload tab) — this is what FTE is built from. **Effort (pre-buffer)** = raw ticket "
               "effort + contingency, before any per-level buffer.")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Staffed effort", fmt_hours(staffed_total), help="Role hours incl. per-level buffer")
    m2.metric("Effort (pre-buffer)", fmt_hours(model["engagement_total_effort"]),
              help="Raw ticket effort + contingency, before per-level buffer")
    m3.metric("Total FTE", f"{model['total_fte']:.2f}")
    m4.metric("SDM hours", fmt_hours(model["sdm_hours"]))
    callout("💡 Cost & price (InfraOps/CloudOps rate families) arrive in <strong>Phase 3</strong>. "
            "This view shows effort and FTE per skill.", "info")


# ──────────────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────────────
def render_multi_skill_app():
    page_header(0, "Multi-skill Estimate",
                "Define skills, enter per-skill workload, and review effort & FTE per skill.")
    if st.button("← Switch to Single-skill mode", key="ms_to_single", type="secondary"):
        st.session_state["estimation_mode"] = "single"
        st.rerun()
    t1, t2, t3 = st.tabs(["1 · Skills", "2 · Workload", "3 · Effort & FTE"])
    with t1:
        _render_skill_setup()
    with t2:
        _render_workload()
    with t3:
        _render_dashboard()
