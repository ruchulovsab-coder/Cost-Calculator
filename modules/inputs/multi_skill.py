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

from config.settings import (COVERAGE_MODELS, DEFAULT_ROLE_BUFFER_PCT, GRADE_ELIGIBILITY,
                             PATCHING_EFFORT_DEFAULTS, DEFAULT_NUM_SERVERS, ACTIVITY_FORMULAS)
from modules.inputs.steps_1_2 import section_hdr, callout, page_header
from modules.calculations.engine import (compute_multi_skill_model, resolve_role_rates,
                                         calc_patching_effort, derive_activity_hours)
from modules.state.multi_state import (build_multi_model_state as _build_multi_state,
                                       refresh_auto_activities as _refresh_auto_activities,
                                       skill_volumes as _skill_volumes)
from utils.formatters import fmt_hours

CATEGORIES = [("alerts", "Monitoring Alerts"), ("service_requests", "Service Requests"),
              ("incidents", "Incidents"), ("changes", "Change Requests")]
LEVELS = ["L1", "L2", "L3"]
BD_LEVELS = ["L1", "L2", "L3", "Architect"]   # buffered/breakdown levels, matches engine _MS_LEVELS
GENUS = ["InfraOps", "CloudOps"]
COV_MODELS = [m for m in COVERAGE_MODELS if m != "Custom"]


def _new_id() -> str:
    return uuid.uuid4().hex[:8]


def _locked() -> bool:
    """Estimate-level read-only lock. When True, value inputs are disabled (via CSS in
    render_multi_skill_app) and structural buttons (add/remove/apply) pass disabled=_locked()."""
    return bool(st.session_state.get("ms_locked", False))


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
            "role_buffers": {"L1": DEFAULT_ROLE_BUFFER_PCT, "L2": DEFAULT_ROLE_BUFFER_PCT,
                             "L3": DEFAULT_ROLE_BUFFER_PCT, "Architect": 0.0},
            "workload": {}, "patching": None, "activities": []}


def _skill_buffers(sk) -> dict:
    """Per-skill role buffers with safe defaults (migrates older drafts/skills that
    predate the Architect buffer or have no buffers at all)."""
    rb = sk.setdefault("role_buffers", {})
    for lvl in LEVELS:
        rb.setdefault(lvl, DEFAULT_ROLE_BUFFER_PCT)
    rb.setdefault("Architect", 0.0)
    return rb


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
            if c3.button("🗑️", key=f"ms_del_{sid}", help="Remove skill", disabled=_locked()):
                to_remove.append(sid)
            c4, c5, c6, c7 = st.columns([2.4, 1.6, 1, 1])
            sk["active_levels"] = c4.multiselect(
                "Active levels", LEVELS, default=sk.get("active_levels", LEVELS),
                key=f"ms_levels_{sid}")
            sk["coverage_model"] = c5.selectbox(
                "Coverage", COV_MODELS,
                index=COV_MODELS.index(sk.get("coverage_model", "8×5")) if sk.get("coverage_model") in COV_MODELS else 0,
                key=f"ms_cov_{sid}")
            # Architect is a senior/design role that sits above L3, so it is only offered
            # once L3 is an active level. When first enabled it auto-fills the recommended %
            # (deterministic, archetype-based); the user can override. No L3 → no Architect.
            from modules.recommend import recommend_architect
            arch_key, cb_key, prev_key = f"ms_archpct_{sid}", f"ms_arch_{sid}", f"_arch_prev_{sid}"
            if "L3" in (sk.get("active_levels") or []):
                _apct, _awhy = recommend_architect(sk)
                if prev_key not in st.session_state:
                    st.session_state[prev_key] = bool(sk.get("has_architect"))
                if arch_key not in st.session_state:
                    st.session_state[arch_key] = float(sk.get("architect_pct", _apct) or _apct)
                prev = st.session_state[prev_key]
                sk["has_architect"] = c6.checkbox("Architect", value=bool(sk.get("has_architect")),
                                                  key=cb_key)
                if sk["has_architect"] and not prev:          # just enabled → auto-fill recommended
                    st.session_state[arch_key] = float(_apct)
                st.session_state[prev_key] = sk["has_architect"]
                sk["architect_pct"] = float(c7.number_input(
                    "Arch %", min_value=0.0, max_value=50.0, step=0.5, key=arch_key,
                    disabled=not sk["has_architect"]))
                st.caption(f"💡 Recommended Architect ≈ **{_apct}%** ({_awhy}) — auto-filled on enable; "
                           "override above if needed.")
            else:
                sk["has_architect"] = False   # no L3 → no architect effort
                for k in (arch_key, cb_key, prev_key):
                    st.session_state.pop(k, None)
                c6.markdown("<div style='padding-top:6px;color:#B0B0B0;font-size:0.78rem'>Architect</div>",
                            unsafe_allow_html=True)
                c7.markdown("<div style='padding-top:6px;color:#B0B0B0;font-size:0.74rem'>after L3</div>",
                            unsafe_allow_html=True)
    if to_remove:
        st.session_state["skills"] = [s for s in skills if s["id"] not in to_remove]
        st.rerun()
    if st.button("➕ Add skill", key="ms_add_skill", type="secondary", disabled=_locked()):
        new = _blank_skill(f"Skill {len(skills) + 1}")
        # TEMPORARY (DEMO_SEED_DATA): pre-fill new skills with representative workload so
        # testers skip manual entry per skill. No-op when the flag is off. Revert with it.
        from modules.demo_seed import demo_fill_skill
        demo_fill_skill(new)
        skills.append(new)
        st.rerun()


# ──────────────────────────────────────────────────────────────────────────────
# Tab 2 — Per-skill workload (direct entry; one aggregate row per category)
# ──────────────────────────────────────────────────────────────────────────────
def _skill_dist_roles(sk) -> list:
    """Roles that patching / additional activities can be assigned to — the skill's ACTIVE
    levels plus Architect when it has one (Architect requires L3). Non-ticket work is
    distributed only across the levels this skill actually staffs; the engine renormalises
    each activity's split onto these roles to match."""
    roles = [l for l in LEVELS if l in (sk.get("active_levels") or [])]
    if sk.get("has_architect"):
        roles.append("Architect")
    return roles or ["L1"]


def _render_skill_tickets(sk, sid):
    """Classification-driven workload: enter a monthly total per category, then review the
    classification mix (share %), handling time (AHT), and the recommended L1/L2/L3 routing —
    all pre-filled from industry defaults and editable. Per-class count = total × share%."""
    from config.settings import MS_CLASSIFICATIONS, MS_DEFAULT_DIST, MS_DEFAULT_AHT
    from modules.state.multi_state import ensure_ms_workload
    from modules.recommend import recommend_routing
    ensure_ms_workload(sk)
    active = [l for l in LEVELS if l in (sk.get("active_levels") or [])]   # LEVELS = L1/L2/L3
    # When the skill's active levels change (e.g. L2 activated on a previously L1-only skill),
    # re-apply the recommended L1/L2/L3 routing to every workload row so the split adapts to
    # the new levels — otherwise a stale split (e.g. alerts 100% L1 from an L1-only seed) sticks.
    _pk = f"_ms_active_{sid}"
    _cur_active = tuple(sk.get("active_levels") or [])
    if st.session_state.get(_pk) is not None and st.session_state[_pk] != _cur_active:
        for _ck in MS_CLASSIFICATIONS:
            for _cls, _row in (sk.get("workload", {}).get(_ck, {}) or {}).items():
                _row["L1_pct"], _row["L2_pct"], _row["L3_pct"] = \
                    recommend_routing(_ck, _cls, sk.get("active_levels"))[:3]
                for _l in ("l1", "l2", "l3"):
                    st.session_state.pop(f"ms_{sid}_{_ck}_{_cls}_{_l}", None)
    st.session_state[_pk] = _cur_active
    st.caption("Enter the monthly **total** per category; the classification mix, handling time "
               "and the **recommended L1/L2/L3 routing** are pre-filled — higher priority escalates "
               "to L2/L3, routine work stays on L1, folded onto this skill's active levels. Everything "
               "is editable. Inactive levels show “—”; Informational alerts default to 0 effort.")
    wl = sk.setdefault("workload", {})
    for cat_key, cat_label in CATEGORIES:
        classes = MS_CLASSIFICATIONS[cat_key]
        rows = wl.setdefault(cat_key, {})
        cur_total = int(sum((rows.get(c, {}) or {}).get("count", 0) or 0 for c in classes))
        with st.expander(f"{cat_label} — {cur_total}/mo", expanded=False):
            total = st.number_input(f"Total {cat_label} / month", min_value=0, step=10,
                                    value=cur_total, key=f"ms_{sid}_{cat_key}_total")
            hdr = st.columns([1.8, 1.1, 1.1, 1, 1, 1])
            for col, t in zip(hdr, ["Classification", "Share %", "AHT (min)", "L1 %", "L2 %", "L3 %"]):
                col.markdown(f"<div style='font-size:0.72rem;color:#1A5F6A;font-weight:600'>{t}</div>",
                             unsafe_allow_html=True)
            new_rows, shares = {}, {}
            for c in classes:
                cur = rows.get(c, {}) or {}
                cur_share = (cur.get("count", 0) or 0) / cur_total * 100.0 if cur_total > 0 \
                    else MS_DEFAULT_DIST[cat_key].get(c, 0)
                rl1, rl2, rl3, _why = recommend_routing(cat_key, c, sk.get("active_levels"))
                dr = (rl1, rl2, rl3)   # recommended split, folded onto active levels
                rc = st.columns([1.8, 1.1, 1.1, 1, 1, 1])
                rc[0].markdown(f"<div style='padding-top:6px;font-size:0.82rem'>{c}</div>",
                               unsafe_allow_html=True)
                sh = rc[1].number_input(f"{c} share", min_value=0.0, max_value=100.0, step=1.0,
                                        value=float(round(cur_share, 1)),
                                        key=f"ms_{sid}_{cat_key}_{c}_sh", label_visibility="collapsed")
                aht = rc[2].number_input(f"{c} aht", min_value=0.0, step=1.0,
                                         value=float(cur.get("minutes", MS_DEFAULT_AHT[cat_key].get(c, 0)) or 0),
                                         key=f"ms_{sid}_{cat_key}_{c}_aht", label_visibility="collapsed")
                split = {}
                for i, lvl in enumerate(("L1", "L2", "L3"), start=3):
                    if lvl in active:
                        split[lvl] = rc[i].number_input(
                            f"{c} {lvl}", min_value=0.0, max_value=100.0, step=1.0,
                            value=float(cur.get(f"{lvl}_pct", dr[i - 3]) or 0),
                            key=f"ms_{sid}_{cat_key}_{c}_{lvl.lower()}", label_visibility="collapsed")
                    else:
                        rc[i].markdown("<div style='padding-top:6px;color:#B0B0B0;text-align:center'>—</div>",
                                       unsafe_allow_html=True)
                        split[lvl] = 0.0
                shares[c] = sh
                new_rows[c] = {"count": round(total * sh / 100.0), "minutes": aht,
                               "L1_pct": split["L1"], "L2_pct": split["L2"], "L3_pct": split["L3"]}
            wl[cat_key] = new_rows
            ssum = sum(shares.values())
            if abs(ssum - 100.0) > 0.5 and ssum > 0:
                st.markdown(f"<span style='color:#E74C3C;font-size:0.74rem'>Classification shares "
                            f"sum to {ssum:.0f}% — should be 100%.</span>", unsafe_allow_html=True)


def _render_skill_patching(sk, sid):
    st.caption("Server patching effort for this skill. Assigned to one role; excluded by default.")
    p = sk.get("patching") or {}
    roles = _skill_dist_roles(sk)
    included = st.checkbox("Patching in scope for this skill", value=bool(p.get("included")),
                           key=f"ms_{sid}_patch_on")
    if not included:
        sk["patching"] = None
        st.caption("Excluded — patching effort = 0.")
        return
    c1, c2, c3 = st.columns(3)
    servers = c1.number_input("Servers", min_value=0, step=1,
                              value=int(p.get("num_servers", DEFAULT_NUM_SERVERS) or 0),
                              key=f"ms_{sid}_patch_srv")
    method = c2.selectbox("Method", ["Manual", "Tool-Based"],
                          index=0 if (p.get("method") or "Manual") == "Manual" else 1,
                          key=f"ms_{sid}_patch_method")
    default_role = p.get("patching_role") if p.get("patching_role") in roles else (
        "L2" if "L2" in roles else roles[0])
    role = c3.selectbox("Handled by", roles, index=roles.index(default_role),
                        key=f"ms_{sid}_patch_role")
    man = float(p.get("manual_effort_per_server", PATCHING_EFFORT_DEFAULTS["Manual"]) or 45)
    auto = float(p.get("auto_effort_per_server", PATCHING_EFFORT_DEFAULTS["Tool-Based"]) or 30)
    err = float(p.get("error_rate_pct", 10.0) or 0)
    d1, d2 = st.columns(2)
    if method == "Manual":
        man = d1.number_input("Min/server", min_value=0.0, step=5.0, value=man, key=f"ms_{sid}_patch_man")
    else:
        auto = d1.number_input("Min/failed server", min_value=0.0, step=5.0, value=auto, key=f"ms_{sid}_patch_auto")
        err = d2.number_input("Error rate %", min_value=0.0, max_value=100.0, step=1.0, value=err,
                              key=f"ms_{sid}_patch_err")
    sk["patching"] = {"included": True, "num_servers": servers, "method": method,
                      "manual_effort_per_server": man, "auto_effort_per_server": auto,
                      "error_rate_pct": err, "patching_role": role}
    res = calc_patching_effort(True, servers, method, man, auto, error_rate_pct=err)
    callout(f"📊 {res['detail']} = <strong>{res['hours']:.1f} hrs/month</strong> → {role}", "success")


def _render_skill_activities(sk, sid):
    st.caption("Recurring operational tasks beyond tickets/patching. Tick **Auto** to derive hours "
               "from this skill's volumes/servers, or enter your own. Role % must sum to 100% for "
               "any activity with hours > 0.")
    roles = _skill_dist_roles(sk)
    acts = sk.setdefault("activities", [])
    servers = int((sk.get("patching") or {}).get("num_servers", 0) or 0)
    volumes = _skill_volumes(sk)

    widths = [2.3, 0.7, 1.0] + [0.9] * len(roles) + [0.5]
    heads = ["Activity", "Auto", "Monthly Hrs"] + [f"{r} %" for r in roles] + [""]
    hc = st.columns(widths)
    for col, t in zip(hc, heads):
        col.markdown(f"<div style='font-size:0.74rem;color:#1A5F6A;font-weight:600'>{t}</div>",
                     unsafe_allow_html=True)
    to_remove = []
    for i, act in enumerate(acts):
        rc = st.columns(widths)
        nm = rc[0].text_input(f"a name {sid}{i}", value=str(act.get("name", "")),
                              key=f"ms_{sid}_act_nm_{i}", label_visibility="collapsed")
        derivable = nm.strip() in ACTIVITY_FORMULAS
        auto = rc[1].checkbox(f"a auto {sid}{i}", value=bool(act.get("auto")) and derivable,
                              key=f"ms_{sid}_act_auto_{i}", label_visibility="collapsed",
                              disabled=not derivable)
        if auto:
            hrs = derive_activity_hours(nm.strip(), servers, volumes)
            rc[2].markdown(f"<div style='padding-top:6px;font-size:0.85rem'>{hrs:.1f}</div>",
                           unsafe_allow_html=True)
        else:
            hrs = rc[2].number_input(f"a hrs {sid}{i}", min_value=0.0, step=1.0,
                                     value=float(act.get("hours", 0) or 0),
                                     key=f"ms_{sid}_act_hrs_{i}", label_visibility="collapsed")
        d = act.get("dist", {}) or {}
        # Fold the stored split onto this skill's staffed roles so the shown values sum to
        # 100 across the active levels (+Architect) — matches how the engine distributes it.
        _dsum = sum(float(d.get(r, 0) or 0) for r in roles)
        d_disp = ({r: float(d.get(r, 0) or 0) / _dsum * 100.0 for r in roles} if _dsum > 0
                  else {roles[0]: 100.0})
        new_dist = {}
        for j, r in enumerate(roles):
            new_dist[r] = rc[3 + j].number_input(
                f"a {r} {sid}{i}", min_value=0.0, max_value=100.0, step=5.0,
                value=float(round(d_disp.get(r, 0.0), 1)), key=f"ms_{sid}_act_{r}_{i}",
                label_visibility="collapsed")
        if rc[-1].button("🗑️", key=f"ms_{sid}_act_del_{i}", help="Remove", disabled=_locked()):
            to_remove.append(i)
        act.update({"name": nm.strip() or "Custom Activity", "hours": float(hrs or 0),
                    "auto": bool(auto), "dist": new_dist})
        if hrs > 0 and abs(sum(new_dist.values()) - 100.0) > 0.5:
            rc[0].markdown("<span style='color:#E74C3C;font-size:0.72rem'>roles ≠ 100%</span>",
                           unsafe_allow_html=True)
    for idx in reversed(to_remove):
        acts.pop(idx)
    if to_remove:
        st.rerun()
    a1, a2 = st.columns([1.4, 3])
    if a1.button("➕ Add activity", key=f"ms_{sid}_act_add", type="secondary", disabled=_locked()):
        acts.append({"name": "Custom Activity", "hours": 0.0, "auto": False,
                     "dist": {r: 0.0 for r in roles}})
        st.rerun()
    std = [n for n in ACTIVITY_FORMULAS if n not in {a.get("name") for a in acts}]
    if std:
        pick = a2.selectbox("Add standard activity", ["—"] + std, key=f"ms_{sid}_act_std")
        if pick != "—":
            acts.append({"name": pick, "hours": 0.0, "auto": True,
                         "dist": {r: 0.0 for r in roles}})
            st.rerun()
    total = sum(a.get("hours", 0.0) for a in acts)
    st.info(f"**Total additional activity effort: {total:.1f} hrs/month**")


def _render_pyramid_hint(sk):
    """Per-skill 'Recommended support pyramid' summary — effort-weighted L1/L2/L3 (+Architect)
    from this skill's classification mix, folded onto its active levels. Advisory, no gating."""
    from modules.recommend import recommend_skill_pyramid, recommend_architect
    pyr, data_driven = recommend_skill_pyramid(sk)
    if not pyr:
        return
    active = sk.get("active_levels") or []
    parts = "  ·  ".join(f"<strong>{l} {pyr[l]}%</strong>" for l in ("L1", "L2", "L3") if l in active)
    arch = f"  (+ Architect ~{recommend_architect(sk)[0]}%)" if "L3" in active else ""
    basis = "from this skill's workload mix" if data_driven \
        else "archetype indication — enter volumes below to refine"
    st.markdown(
        f"<div style='background:#EAF4F4;border-left:3px solid #1A5F6A;padding:6px 11px;"
        f"border-radius:4px;font-size:0.85rem;margin:2px 0 10px'>💡 <strong>Recommended support "
        f"pyramid</strong> <span style='color:#5A6B6B'>({basis})</span>: {parts}{arch}</div>",
        unsafe_allow_html=True)


def _render_workload():
    section_hdr("📊 Per-skill Workload")
    skills = st.session_state.get("skills", [])
    if not skills:
        callout("Add a skill on the Skills tab first.", "info")
        return
    names = {s["id"]: s.get("name") or s["id"] for s in skills}
    sid = st.selectbox("Skill", list(names), format_func=lambda x: names[x], key="ms_wl_skill")
    sk = next(s for s in skills if s["id"] == sid)
    from modules.state.multi_state import ensure_ms_workload
    ensure_ms_workload(sk)
    _render_pyramid_hint(sk)
    with st.expander("🎫 Tickets", expanded=True):
        _render_skill_tickets(sk, sid)
    with st.expander("🖥️ Patching", expanded=False):
        _render_skill_patching(sk, sid)
    with st.expander("🧰 Additional Activities", expanded=False):
        _render_skill_activities(sk, sid)


# ──────────────────────────────────────────────────────────────────────────────
# Tab 3 — Engagement inputs + Effort/FTE dashboard
# (state builder + auto-activity refresh live in modules/state/multi_state.py so
#  non-UI code — run_model, approval email, Excel — can compute the multi model)
# ──────────────────────────────────────────────────────────────────────────────
def _render_buffer_config(skills):
    """Per-skill × per-level buffer matrix (L1/L2/L3/Architect). Writes sk['role_buffers']."""
    section_hdr("🎛️ Per-level effort buffer")
    callout("Buffer % added per level for wait / handover / non-productive overhead — set it "
            "independently for each skill and support level (Architect included). Use 0 to price "
            "raw effort. The build-up below shows exactly how each buffer and the contingency "
            "shape the final staffing.", "info")
    hc = st.columns([2.6, 1, 1, 1, 1.3])
    for col, t in zip(hc, ["Skill", "L1 %", "L2 %", "L3 %", "Architect %"]):
        col.markdown(f"<div style='font-size:0.76rem;color:#1A5F6A;font-weight:600'>{t}</div>",
                     unsafe_allow_html=True)
    for sk in skills:
        sid = sk["id"]
        rb = _skill_buffers(sk)
        active = set(sk.get("active_levels", []) or [])
        rc = st.columns([2.6, 1, 1, 1, 1.3])
        rc[0].markdown(f"<div style='padding-top:6px;font-size:0.85rem'>{sk.get('name') or sid}</div>",
                       unsafe_allow_html=True)
        for i, lvl in enumerate(LEVELS, start=1):
            if lvl in active:
                rb[lvl] = rc[i].number_input(
                    f"{sid} {lvl} buffer", min_value=0.0, max_value=100.0, step=1.0,
                    value=float(rb.get(lvl, DEFAULT_ROLE_BUFFER_PCT) or 0.0),
                    key=f"ms_buf_{sid}_{lvl}", label_visibility="collapsed")
            else:
                rc[i].markdown("<div style='padding-top:6px;color:#B0B0B0'>—</div>", unsafe_allow_html=True)
        if sk.get("has_architect"):
            rb["Architect"] = rc[4].number_input(
                f"{sid} Architect buffer", min_value=0.0, max_value=100.0, step=1.0,
                value=float(rb.get("Architect", 0.0) or 0.0),
                key=f"ms_buf_{sid}_Architect", label_visibility="collapsed")
        else:
            rc[4].markdown("<div style='padding-top:6px;color:#B0B0B0'>—</div>", unsafe_allow_html=True)


def _render_skill_buildup(name: str, ps: dict, cont_pct: float):
    """Raw → Buffered → Final build-up (hours + FTE) with variance, for one skill."""
    bd = ps["breakdown"]
    order = [lvl for lvl in ("L1", "L2", "L3", "Architect")
             if bd.get(lvl, {}).get("raw", 0) > 1e-9 or bd.get(lvl, {}).get("final", 0) > 1e-9]
    if not order:
        st.caption("No workload entered for this skill yet.")
        return
    raw_t = buf_t = fin_t = 0.0
    fr_t = fb_t = ff_t = fs_t = 0.0
    e_rows = ""
    f_rows = ""
    for lvl in order:
        d = bd[lvl]
        raw_t += d["raw"]; buf_t += d["buffered"]; fin_t += d["final"]
        fr_t += d["fte_raw"]; fb_t += d["fte_buffered"]; ff_t += d["fte_final"]; fs_t += d["fte_staffed"]
        e_rows += (f"<tr><td>{lvl}</td><td class='r'>{d['raw']:.1f}</td>"
                   f"<td class='r'>{d['buffer_pct']:.0f}%</td><td class='r'>{d['buffered']:.1f}</td>"
                   f"<td class='r'>{cont_pct:.0f}%</td><td class='r'>{d['final']:.1f}</td>"
                   f"<td class='r' style='color:#1A7F37'>+{d['final'] - d['raw']:.1f}</td></tr>")
        f_rows += (f"<tr><td>{lvl}</td><td class='r'>{d['fte_raw']:.2f}</td>"
                   f"<td class='r'>{d['fte_buffered']:.2f}</td><td class='r'>{d['fte_final']:.2f}</td>"
                   f"<td class='r'><strong>{d['fte_staffed']:.1f}</strong></td></tr>")
    e_rows += (f"<tr class='total-row'><td><strong>Total</strong></td>"
               f"<td class='r'><strong>{raw_t:.1f}</strong></td><td></td>"
               f"<td class='r'><strong>{buf_t:.1f}</strong></td><td></td>"
               f"<td class='r'><strong>{fin_t:.1f}</strong></td>"
               f"<td class='r' style='color:#1A7F37'><strong>+{fin_t - raw_t:.1f}</strong></td></tr>")
    f_rows += (f"<tr class='total-row'><td><strong>Total</strong></td>"
               f"<td class='r'><strong>{fr_t:.2f}</strong></td><td class='r'><strong>{fb_t:.2f}</strong></td>"
               f"<td class='r'><strong>{ff_t:.2f}</strong></td><td class='r'><strong>{fs_t:.1f}</strong></td></tr>")

    st.markdown("<div style='font-size:0.82rem;color:#1A5F6A;font-weight:600;margin:.2rem 0'>Effort (hours)</div>",
                unsafe_allow_html=True)
    st.markdown(
        f"""<table class="styled-table"><thead><tr>
        <th>Level</th><th class="r">Raw</th><th class="r">Buffer</th><th class="r">Buffered</th>
        <th class="r">Contingency</th><th class="r">Final</th><th class="r">Δ Raw→Final</th>
        </tr></thead><tbody>{e_rows}</tbody></table>""", unsafe_allow_html=True)

    st.markdown("<div style='font-size:0.82rem;color:#1A5F6A;font-weight:600;margin:.6rem 0 .2rem'>FTE</div>",
                unsafe_allow_html=True)
    st.markdown(
        f"""<table class="styled-table"><thead><tr>
        <th>Level</th><th class="r">Raw FTE</th><th class="r">Buffered FTE</th>
        <th class="r">Final FTE</th><th class="r">Staffed FTE</th>
        </tr></thead><tbody>{f_rows}</tbody></table>""", unsafe_allow_html=True)
    st.caption("Raw/Buffered/Final FTE are exact (hours ÷ productive hours × coverage). **Staffed FTE** "
               "rounds each level up to the nearest 0.5 (min 0.5) — the actual headcount. This build-up "
               "is standalone per skill; resource-sharing pools are applied at the engagement roll-up.")

    def _pct(num, den):
        return f"{num / den * 100:+.0f}%" if den > 1e-9 else None

    v1, v2, v3 = st.columns(3)
    v1.metric("Buffer impact", fmt_hours(buf_t - raw_t), delta=_pct(buf_t - raw_t, raw_t),
              delta_color="off", help="Δ Raw → Buffered (effect of the per-level buffers)")
    v2.metric("Contingency impact", fmt_hours(fin_t - buf_t), delta=_pct(fin_t - buf_t, buf_t),
              delta_color="off", help="Δ Buffered → Final (effect of the contingency %)")
    v3.metric("Combined (Raw→Final)", fmt_hours(fin_t - raw_t), delta=_pct(fin_t - raw_t, raw_t),
              delta_color="off", help="Total uplift from raw effort to final staffed hours")


def _render_summary(model, names):
    """Per-skill final role hours by level + Raw and Final totals (§4)."""
    section_hdr("📋 Summary")
    rows = ""
    tot = {lvl: 0.0 for lvl in BD_LEVELS}
    raw_tot = fin_tot = 0.0
    for sid, ps in model["per_skill"].items():
        rh, bd = ps["role_hours"], ps["breakdown"]
        raw = sum(bd[lvl]["raw"] for lvl in BD_LEVELS)
        fin = sum(rh[lvl] for lvl in BD_LEVELS)   # = L1+L2+L3+Arch final hours
        raw_tot += raw; fin_tot += fin
        for lvl in BD_LEVELS:
            tot[lvl] += rh[lvl]
        rows += (f"<tr><td>{names.get(sid, sid)}</td><td>{ps['genus_category']}</td>"
                 f"<td class='r'>{rh['L1']:.1f}</td><td class='r'>{rh['L2']:.1f}</td>"
                 f"<td class='r'>{rh['L3']:.1f}</td><td class='r'>{rh['Architect']:.1f}</td>"
                 f"<td class='r' style='color:#7A8A99'>{raw:.1f}</td><td class='r'><strong>{fin:.1f}</strong></td></tr>")
    rows += (f"<tr class='total-row'><td><strong>Engagement</strong></td><td></td>"
             f"<td class='r'><strong>{tot['L1']:.1f}</strong></td><td class='r'><strong>{tot['L2']:.1f}</strong></td>"
             f"<td class='r'><strong>{tot['L3']:.1f}</strong></td><td class='r'><strong>{tot['Architect']:.1f}</strong></td>"
             f"<td class='r' style='color:#7A8A99'><strong>{raw_tot:.1f}</strong></td>"
             f"<td class='r'><strong>{fin_tot:.1f}</strong></td></tr>")
    st.markdown(
        f"""<table class="styled-table"><thead><tr>
        <th>Skill</th><th>Family</th><th class="r">L1 Hours</th><th class="r">L2 Hours</th>
        <th class="r">L3 Hours</th><th class="r">Architect Hours</th>
        <th class="r">Raw Hours</th><th class="r">Final Hours</th>
        </tr></thead><tbody>{rows}</tbody></table>""", unsafe_allow_html=True)
    st.caption("**L1–Architect Hours** are Final (buffer + contingency) and sum to **Final Hours**. "
               "**Raw Hours** = effort before any buffer or contingency.")


def _render_overall_comparison(model):
    """Engagement Raw → Buffered → Final totals with absolute & % variance (§5)."""
    section_hdr("📊 Overall Comparison")
    raw = buf = fin = 0.0
    for ps in model["per_skill"].values():
        for lvl in BD_LEVELS:
            d = ps["breakdown"][lvl]
            raw += d["raw"]; buf += d["buffered"]; fin += d["final"]
    pct = lambda n, d: f"+{n / d * 100:.1f}%" if d > 1e-9 else "—"
    body = (
        f"<tr><td>Raw (before any adjustment)</td><td class='r'>{raw:.1f}</td><td class='r'>—</td>"
        f"<td class='r'>—</td></tr>"
        f"<tr><td>After Buffer</td><td class='r'>{buf:.1f}</td>"
        f"<td class='r' style='color:#1A7F37'>+{buf - raw:.1f}</td><td class='r' style='color:#1A7F37'>{pct(buf - raw, raw)}</td></tr>"
        f"<tr><td>Final (Buffer + Contingency)</td><td class='r'><strong>{fin:.1f}</strong></td>"
        f"<td class='r' style='color:#1A7F37'>+{fin - buf:.1f}</td><td class='r' style='color:#1A7F37'>{pct(fin - buf, buf)}</td></tr>"
    )
    st.markdown(
        f"""<table class="styled-table"><thead><tr>
        <th>Stage</th><th class="r">Total Hours</th><th class="r">Δ from previous</th>
        <th class="r">Δ % from previous</th></tr></thead><tbody>{body}</tbody></table>""",
        unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    c1.metric("Buffer impact", fmt_hours(buf - raw), delta=pct(buf - raw, raw), delta_color="off",
              help="Raw → After Buffer")
    c2.metric("Contingency impact", fmt_hours(fin - buf), delta=pct(fin - buf, buf), delta_color="off",
              help="After Buffer → Final")
    c3.metric("Combined (Raw → Final)", fmt_hours(fin - raw), delta=pct(fin - raw, raw), delta_color="off",
              help="Total uplift from raw effort to final")


def _fte_matrix(model, names, kind):
    """One FTE matrix (rows = skills, cols = L1/L2/L3/Architect + Total). `kind`:
      'raw'   → exact pre-pool requirement (breakdown fte_raw);
      'final' → delivered team, pooled-aware (per_skill fte_by_level, hours-share of pools).
    Returns (rows_html, col_totals, grand)."""
    rows = ""
    col_tot = {lvl: 0.0 for lvl in BD_LEVELS}
    grand = 0.0
    for sid, ps in model["per_skill"].items():
        cells = ""
        row_tot = 0.0
        for lvl in BD_LEVELS:
            v = ps["breakdown"][lvl]["fte_raw"] if kind == "raw" else ps["fte_by_level"][lvl]
            col_tot[lvl] += v
            row_tot += v
            cells += f"<td class='r'>{v:.2f}</td>"
        grand += row_tot
        rows += f"<tr><td>{names.get(sid, sid)}</td>{cells}<td class='r'><strong>{row_tot:.2f}</strong></td></tr>"
    return rows, col_tot, grand


def _render_team_summary(model, names):
    """Raw vs Final FTE by skill × level, with SDM and grand totals (§6)."""
    section_hdr("👥 Overall Team Summary")
    st.caption("Team composition before vs after adjustments. **Raw FTE** = exact pre-pooling "
               "requirement (hours ÷ productive × coverage). **Final FTE** = the delivered team "
               "(buffered + contingency, and **pooled** where resource sharing is applied), "
               "attributed to each skill by its hours-share — cells are fractional; the **grand "
               "total is the real headcount and equals the engagement Total FTE**. SDM is one "
               "engagement resource.")

    sdm = next((r for r in model["resources"] if r["level"] == "SDM"), None)
    sdm_raw = float(sdm["raw_fte"]) if sdm else 0.0
    sdm_final = float(sdm["fte"]) if sdm else 0.0

    def _table(title, kind, sdm_val, subtitle=""):
        rows, col_tot, grand = _fte_matrix(model, names, kind)
        gtot = grand + sdm_val
        if sdm and sdm_val > 0:
            rows += (f"<tr><td>SDM <span style='color:#7A8A99'>(engagement)</span></td>"
                     f"<td class='r'>—</td><td class='r'>—</td><td class='r'>—</td><td class='r'>—</td>"
                     f"<td class='r'><strong>{sdm_val:.2f}</strong></td></tr>")
        tcells = "".join(f"<td class='r'><strong>{col_tot[lvl]:.2f}</strong></td>" for lvl in BD_LEVELS)
        rows += (f"<tr class='total-row'><td><strong>Grand total</strong></td>{tcells}"
                 f"<td class='r'><strong>{gtot:.2f}</strong></td></tr>")
        st.markdown(f"<div style='font-size:0.82rem;color:#1A5F6A;font-weight:600;margin:.4rem 0 .1rem'>{title}</div>",
                    unsafe_allow_html=True)
        if subtitle:
            st.markdown(f"<div style='font-size:0.72rem;color:#7A8A99;line-height:1.35;margin:0 0 .35rem'>{subtitle}</div>",
                        unsafe_allow_html=True)
        st.markdown(
            f"""<table class="styled-table"><thead><tr>
            <th>Skill</th><th class="r">L1</th><th class="r">L2</th><th class="r">L3</th>
            <th class="r">Architect</th><th class="r">Total</th></tr></thead><tbody>{rows}</tbody></table>""",
            unsafe_allow_html=True)
        return gtot

    raw_grand = _table(
        "Raw FTE (exact, pre-pooling)", "raw", sdm_raw,
        "Exact fractional requirement per skill × level = monthly hours ÷ productive hours × coverage "
        "multiplier. The mathematical demand — not directly staffable as whole people.")
    fin_grand = _table(
        "Final FTE (delivered team, pooled-aware)", "final", sdm_final,
        "The team you actually staff: every skill × level is rounded <strong>up to the nearest 0.5</strong>, "
        "with a <strong>0.5-person minimum</strong> (you can't deploy less than half a person on a line). "
        "Shared/pooled roles are rounded <strong>once</strong>, not per skill.")

    g1, g2 = st.columns(2)
    g1.metric("Total Raw FTE", f"{raw_grand:.2f}")
    g2.metric("Total Final FTE (headcount)", f"{fin_grand:.1f}",
              help="Delivered team. Equals the engagement Total FTE (pooling applied where configured).")

    gap = fin_grand - raw_grand
    if raw_grand > 0 and gap > 0.05:
        pct = gap / raw_grand * 100.0
        callout(f"↕️ <strong>Rounding &amp; minimum-staffing overhead: +{gap:.1f} FTE ({pct:.0f}% over Raw).</strong> "
                "Each skill × level is rounded up to a 0.5-person minimum, so many small fractions across "
                "skills/levels round up independently and add up. To shrink this, <strong>pool L2/L3/Architect "
                "across similar skills on the <em>Optimize (AI)</em> tab</strong> — pooled roles round once "
                "instead of once per skill.", "info")


def _render_dashboard():
    section_hdr("📈 Effort & FTE by Skill")
    skills = st.session_state.get("skills", [])
    if not skills:
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
        "SDM allocation (% of one SDM FTE)", min_value=0.0, max_value=100.0, step=5.0,
        value=float(st.session_state.get("sdm_overhead_pct", 5.0) or 0.0), key="ms_sdm",
        help="Fraction of ONE Service Delivery Manager assigned to this engagement — 25 = 0.25 SDM FTE "
             "(fixed, independent of engagement size). Not a % of delivery effort.")

    # New multi estimates default to Raw (the chosen basis); loaded estimates keep their saved
    # basis. Leadership can switch here; both bases are compared on the Approve & Export tab.
    if not st.session_state.get("_ms_basis_init"):
        if not st.session_state.get("_current_estimate_ref"):
            st.session_state["fte_basis"] = "raw"
        st.session_state["_ms_basis_init"] = True
    _basis = st.radio(
        "Estimation basis (drives cost, price, approval & export)",
        ["Raw (theoretical minimum)", "Rounded (delivered team)"],
        index=1 if st.session_state.get("fte_basis") == "rounded" else 0, horizontal=True,
        key="ms_fte_basis_radio",
        help="Raw = exact fractional demand (assumes perfect sharing/pooling) — the default. "
             "Rounded = each skill × level rounded up to 0.5 (min 0.5), the team you actually staff. "
             "Both are compared on the Approve & Export tab.")
    st.session_state["fte_basis"] = "rounded" if _basis.startswith("Rounded") else "raw"

    # §2 Per-level effort buffer
    _render_buffer_config(skills)

    cont_pct = float(st.session_state.get("contingency_pct", 10.0) or 0.0)
    model = compute_multi_skill_model(_build_multi_state())
    names = {s["id"]: (s.get("name") or s["id"]) for s in skills}

    # §3 Step-by-step build-up (per skill)
    st.divider()
    section_hdr("🔍 Step-by-step build-up (Raw → Buffered → Final)")
    st.caption("For each skill: Raw effort/FTE (no adjustments) → after the configured Buffer → "
               "Final after Contingency, with the variance each step contributes.")
    for sid, ps in model["per_skill"].items():
        with st.expander(f"{names.get(sid, sid)} · {ps['genus_category']}", expanded=len(skills) == 1):
            _render_skill_buildup(names.get(sid, sid), ps, cont_pct)

    # §4 Summary
    st.divider()
    _render_summary(model, names)

    # §5 Overall Comparison
    st.divider()
    _render_overall_comparison(model)

    # §6 Overall Team Summary
    st.divider()
    _render_team_summary(model, names)

    callout("💡 See the <strong>Rates &amp; Cost</strong> tab for cost &amp; price "
            "(InfraOps/CloudOps rate families).", "info")


# ──────────────────────────────────────────────────────────────────────────────
# Tab 4 — Rates & Cost (InfraOps/CloudOps rate families → cost/price)
# ──────────────────────────────────────────────────────────────────────────────
def _inr(v) -> str:
    return f"₹{float(v or 0):,.0f}"


def _default_grade(band, available, family="InfraOps"):
    """First eligible genus grade for a band + rate family that exists in the rate card
    (InfraOps → *-INFRAOPS, CloudOps → *-CLOUD-INFRASTRUCTURE), else first available."""
    from config.settings import grade_eligibility
    for g in grade_eligibility(band, family):
        if g in available:
            return g
    if family == "CloudOps":
        # Tolerant fallback: any card grade sharing this band's number AND a cloud family,
        # so naming variations (2.1-CLOUD-INFRASTRUCTURE / 2.1 CLOUD-INFRA / etc.) resolve.
        prefixes = tuple(g.split("-", 1)[0] for g in grade_eligibility(band, "InfraOps"))
        for g in available:
            gs = str(g).upper()
            if "CLOUD" in gs and gs.startswith(prefixes):
                return g
    return available[0] if available else None


def _ensure_fx(filtered):
    """Collect INR exchange rates for any non-INR rate-card currencies in scope."""
    fx = dict(st.session_state.get("exchange_rates", {}) or {})
    fx.setdefault("INR", 1.0)
    curs = sorted({str(c).upper().strip() for c in filtered["rate currency"].dropna().unique()} - {"INR"})
    if curs:
        st.caption("Enter exchange rates for the rate-card currencies (1 unit = ? INR):")
        cols = st.columns(len(curs))
        for col, cur in zip(cols, curs):
            fx[cur] = col.number_input(f"1 {cur} = ? INR", min_value=0.0, step=1.0,
                                       value=float(fx.get(cur, 0.0) or 0.0), key=f"ms_fx_{cur}")
    st.session_state["exchange_rates"] = fx
    return fx


def _render_rate_matrix(filtered):
    """Family × band genus-grade dropdowns (+ SDM). Returns (family_grades, sdm_grade)."""
    available = filtered["genus"].dropna().astype(str).unique().tolist()
    if not available:
        callout("No grades in the rate card for the selected location.", "warning")
        return {}, None
    fam_grades = st.session_state.setdefault("ms_family_grades", {})
    for fam in GENUS:
        fg = fam_grades.setdefault(fam, {})
        for band in BD_LEVELS:
            cur = fg.get(band)
            # (Re)default when the cell is unset/invalid, OR when a CloudOps cell still points
            # at an INFRAOPS grade (a stale fallback from before cloud grades were mapped).
            stale_cloud = fam == "CloudOps" and cur and "INFRAOPS" in str(cur).upper()
            if cur not in available or stale_cloud:
                fg[band] = _default_grade(band, available, fam)
    if st.session_state.get("ms_sdm_grade") not in available:
        st.session_state["ms_sdm_grade"] = _default_grade("SDM", available)

    section_hdr("🎓 Rate family → grade mapping")
    callout("Map each rate family and band to a genus grade from the rate card; the hourly rate "
            "(converted to INR) is read from the card. A skill prices off its family's bands: "
            "<strong>InfraOps → *-INFRAOPS</strong>, <strong>CloudOps → *-CLOUD-INFRASTRUCTURE</strong> "
            "(defaulted automatically; override any cell). If the card lacks CLOUD-INFRASTRUCTURE rows, "
            "CloudOps falls back to the first available grade.", "info")
    hc = st.columns([1.5, 2, 2, 2, 2])
    for col, t in zip(hc, ["Family", "L1", "L2", "L3", "Architect"]):
        col.markdown(f"<div style='font-size:0.76rem;color:#1A5F6A;font-weight:600'>{t}</div>",
                     unsafe_allow_html=True)
    for fam in GENUS:
        rc = st.columns([1.5, 2, 2, 2, 2])
        rc[0].markdown(f"<div style='padding-top:6px;font-size:0.85rem'><strong>{fam}</strong></div>",
                       unsafe_allow_html=True)
        for i, band in enumerate(BD_LEVELS, start=1):
            cur = fam_grades[fam].get(band)
            idx = available.index(cur) if cur in available else 0
            fam_grades[fam][band] = rc[i].selectbox(
                f"{fam} {band} grade", available, index=idx,
                key=f"ms_rg_{fam}_{band}", label_visibility="collapsed")
    sc1, sc2 = st.columns([1.5, 2])
    sc1.markdown("<div style='padding-top:6px;font-size:0.85rem'><strong>SDM</strong> (engagement)</div>",
                 unsafe_allow_html=True)
    sdm_cur = st.session_state.get("ms_sdm_grade")
    sdm_idx = available.index(sdm_cur) if sdm_cur in available else 0
    st.session_state["ms_sdm_grade"] = sc2.selectbox(
        "SDM grade", available, index=sdm_idx, key="ms_rg_SDM", label_visibility="collapsed")
    return fam_grades, st.session_state["ms_sdm_grade"]


def _render_rates_cost():
    section_hdr("💰 Rates & Cost")
    skills = st.session_state.get("skills", [])
    if not skills:
        callout("Add a skill and its workload first (tabs 1–2).", "info")
        return

    from modules.inputs.steps_6_7 import render_rate_card_source, render_delivery_location
    render_rate_card_source()
    df = st.session_state.get("rate_card_df")
    if df is None:
        callout("Load a rate card above to resolve InfraOps/CloudOps band rates and price the estimate.",
                "warning")
        return
    render_delivery_location()
    filtered = st.session_state.get("_filtered_rate_card")
    if filtered is None or len(filtered) == 0:
        callout("No rate-card grades for the selected delivery location.", "warning")
        return

    fx = _ensure_fx(filtered)
    country = st.session_state.get("delivery_country")
    location = st.session_state.get("delivery_location")

    fam_grades, sdm_grade = _render_rate_matrix(filtered)
    rbc = {fam: resolve_role_rates(df, fam_grades.get(fam, {}), country, location, fx) for fam in GENUS}
    sdm_rate = resolve_role_rates(df, {"SDM": sdm_grade}, country, location, fx).get("SDM", 0.0)
    st.session_state["ms_rates_by_category"] = rbc
    st.session_state["ms_sdm_rate_inr"] = sdm_rate

    # Resolved hourly rates (INR) read-back
    rate_rows = ""
    for fam in GENUS:
        cells = "".join(f"<td class='r'>{_inr(rbc[fam].get(b, 0))}</td>" for b in BD_LEVELS)
        rate_rows += f"<tr><td><strong>{fam}</strong></td>{cells}</tr>"
    rate_rows += (f"<tr><td><strong>SDM</strong></td><td class='r' colspan='4'>{_inr(sdm_rate)} "
                  f"<span style='color:#7A8A99'>(engagement)</span></td></tr>")
    st.markdown(
        f"""<table class="styled-table"><thead><tr><th>Family</th>
        <th class="r">L1 /hr</th><th class="r">L2 /hr</th><th class="r">L3 /hr</th>
        <th class="r">Architect /hr</th></tr></thead><tbody>{rate_rows}</tbody></table>""",
        unsafe_allow_html=True)

    st.session_state["target_margin_pct"] = st.number_input(
        "Target margin %", min_value=0.0, max_value=99.0, step=1.0,
        value=float(st.session_state.get("target_margin_pct", 20.0) or 0.0), key="ms_margin")

    model = compute_multi_skill_model(_build_multi_state())

    # Engagement cost → price (per-skill "Cost by Skill" table now lives on Approve & Export)
    st.divider()
    cr, pr = model["cost_result"], model["price_result"]
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Resource cost / mo", _inr(cr["resource_cost"]))
    m2.metric("Delivery cost / mo", _inr(cr["total_delivery_cost"]))
    m3.metric(f"Selling price / mo ({pr['margin_pct']:.0f}% margin)", _inr(pr["selling_price"]))
    m4.metric("Gross profit / mo", _inr(pr["gross_profit"]))
    st.caption("Cost = FTE × monthly hours × band rate (per skill's family), pooled where resource "
               "sharing applies; SDM priced once. Selling price = delivery cost ÷ (1 − margin).")


# ──────────────────────────────────────────────────────────────────────────────
# Tab 5 — AI Team Optimizer (cross-skill resource sharing)
# ──────────────────────────────────────────────────────────────────────────────
def _render_optimize():
    section_hdr("🤖 AI Team Optimizer")
    skills = st.session_state.get("skills", [])
    if not skills:
        callout("Add a skill and its workload first (tabs 1–2).", "info")
        return
    st.caption("Share senior people across similar skills to cut team size — without losing coverage. "
               "The engine does the maths; you approve each move.")

    from modules.optimize.team_optimizer import (optimize_team, apply_optimization,
                                                 ai_available, ai_narrative)

    # All knobs live behind one Settings expander — sensible defaults just work.
    OBJECTIVES = {"Balanced": 85.0, "Lean — save the most": 95.0, "Safe — lowest risk": 70.0}
    with st.expander("⚙️ Settings (optional)", expanded=False):
        obj = st.selectbox("How aggressive?", list(OBJECTIVES),
                           index=(list(OBJECTIVES).index(st.session_state["ms_opt_objective"])
                                  if st.session_state.get("ms_opt_objective") in OBJECTIVES else 0),
                           key="ms_opt_objective")
        levels = st.multiselect("Levels to share", ["Architect", "L3", "L2"],
                                default=st.session_state.get("ms_opt_levels", ["Architect", "L3"]),
                                key="ms_opt_levels", help="L1 is never shared (front-line, per-skill).")
        cross_family = st.checkbox("Allow sharing across InfraOps ↔ CloudOps (senior roles)",
                                   value=bool(st.session_state.get("ms_opt_crossfam", False)),
                                   key="ms_opt_crossfam")
        s1, s2 = st.columns(2)
        st.session_state["ms_context_switch_pct"] = s1.number_input(
            "Context-switch penalty %", min_value=0.0, max_value=50.0, step=5.0,
            value=float(st.session_state.get("ms_context_switch_pct", 10.0) or 0.0), key="ms_csw",
            help="Extra effort when one person spans several skills — keeps savings honest.")
        st.session_state["ms_enforce_min_shift"] = s2.toggle(
            "Enforce 24×7 shift minimums",
            value=bool(st.session_state.get("ms_enforce_min_shift", False)), key="ms_minshift",
            help="Require enough bodies for round-the-clock presence (applies to the whole estimate).")
        context = st.text_input("Notes for the AI (optional)",
                                value=st.session_state.get("ms_opt_context", ""), key="ms_opt_context",
                                placeholder="e.g. keep Security dedicated; minimise key-person risk")
    ceiling = OBJECTIVES[obj]
    sel_levels = tuple(levels) or ("Architect", "L3")

    state = _build_multi_state()
    with st.spinner("Finding sharing opportunities…"):
        res = optimize_team(state, ceiling_pct=ceiling, share_levels=sel_levels, cross_family=cross_family)
    baseline, suggestions, notes = res["baseline"], res["suggestions"], res["level_notes"]

    if not suggestions:
        callout("No safe team savings for the current setup — the skills aren't similar enough, or "
                "there's no spare capacity to share. Try **Settings → How aggressive → Lean**, or "
                "add **L2**.", "warning")
        st.metric("Current team", f"{baseline['total_fte']:.1f} FTE")
        return

    # Default: accept every suggestion (tick boxes persist in session by suggestion id).
    for s in suggestions:
        st.session_state.setdefault(f"ms_optchk_{s['id']}", True)
    accepted = [s for s in suggestions if st.session_state.get(f"ms_optchk_{s['id']}", True)]
    accepted_groups = [s["group"] for s in accepted]
    optimized = apply_optimization(state, accepted_groups)

    fte_b, fte_a = baseline["total_fte"], optimized["total_fte"]
    cost_b, cost_a = baseline["total_resource_cost"], optimized["total_resource_cost"]
    price_b = baseline["price_result"]["selling_price"]
    price_a = optimized["price_result"]["selling_price"]
    saved_pct = ((fte_b - fte_a) / fte_b * 100.0) if fte_b > 1e-9 else 0.0

    # ── Headline: the answer, first ──
    h1, h2, h3 = st.columns(3)
    h1.metric("Optimised team", f"{fte_a:.1f} FTE", f"-{fte_b - fte_a:.1f} FTE", delta_color="inverse")
    if cost_b > 0:
        h2.metric("Monthly cost", _inr(cost_a), f"-{_inr(cost_b - cost_a)}", delta_color="inverse")
        h3.metric("Monthly price", _inr(price_a), f"-{_inr(price_b - price_a)}", delta_color="inverse")
    else:
        h2.metric("Team saved", f"{fte_b - fte_a:.1f} FTE")
        h3.caption("Load a rate card (tab 4) to see cost & price savings.")
    st.caption(f"From **{fte_b:.1f}** to **{fte_a:.1f} FTE** by applying **{len(accepted)} of "
               f"{len(suggestions)}** suggested moves"
               + (f" — a **{saved_pct:.0f}%** smaller team." if saved_pct > 0 else "."))

    # ── Recommended moves: one line each ──
    st.markdown("**Recommended moves** — tick the ones to apply")
    for s in suggestions:
        c_chk, c_txt = st.columns([0.6, 9])
        c_chk.checkbox("apply", key=f"ms_optchk_{s['id']}", label_visibility="collapsed")
        chips = ""
        if s.get("cross_family"):
            chips += (" &nbsp;<span style='background:#E8F0F2;color:#1A5F6A;padding:1px 6px;"
                      "border-radius:8px;font-size:0.72rem'>cross-family</span>")
        if s["key_person_risk"]:
            chips += (" &nbsp;<span style='background:#FBEED9;color:#B8860B;padding:1px 6px;"
                      "border-radius:8px;font-size:0.72rem'>⚠ key person</span>")
        cost_txt = f" &nbsp;·&nbsp; ~{_inr(s['cost_saved'])}/mo" if s["cost_saved"] > 0 else ""
        c_txt.markdown(
            f"Share **1 {s['level']}** across **{' + '.join(s['skill_names'])}** — "
            f"saves **{s['fte_saved']:.1f} FTE**{cost_txt}{chips}", unsafe_allow_html=True)

    a1, a2, a3 = st.columns([1.5, 1, 2])
    if a1.button("✅ Apply to estimate", key="ms_opt_apply", type="primary",
                 disabled=_locked() or not accepted_groups):
        st.session_state["resource_sharing"] = accepted_groups
        st.success(f"Applied {len(accepted_groups)} move(s) — Effort & Cost now reflect the leaner team.")
    if a2.button("↩ Reset", key="ms_opt_clear",
                 disabled=_locked() or not st.session_state.get("resource_sharing")):
        st.session_state["resource_sharing"] = []
        st.info("Reset — back to the current team.")
    if ai_available() and a3.button("✨ Explain with AI", key="ms_opt_ai"):
        with st.spinner("Asking the AI advisor…"):
            out = ai_narrative([s.get("name") or s["id"] for s in skills], accepted or suggestions,
                               {"fte_before": fte_b, "fte_after": fte_a}, context=context)
        st.session_state["ms_opt_ai_text"] = out.get("summary") or out.get("error", "")
    if st.session_state.get("ms_opt_ai_text"):
        callout(st.session_state["ms_opt_ai_text"], "info")

    # ── Details (collapsed): full numbers + what was analysed + how it works ──
    with st.expander("📊 Details — before vs after, and what was analysed", expanded=False):
        rows = (
            f"<tr><td>Total FTE</td><td class='r'>{fte_b:.1f}</td><td class='r'><strong>{fte_a:.1f}</strong></td>"
            f"<td class='r' style='color:#1A7F37'>−{fte_b - fte_a:.1f} ({saved_pct:.0f}%)</td></tr>"
            f"<tr><td>Resource cost / mo</td><td class='r'>{_inr(cost_b)}</td><td class='r'><strong>{_inr(cost_a)}</strong></td>"
            f"<td class='r' style='color:#1A7F37'>−{_inr(cost_b - cost_a)}</td></tr>"
            f"<tr><td>Selling price / mo</td><td class='r'>{_inr(price_b)}</td><td class='r'><strong>{_inr(price_a)}</strong></td>"
            f"<td class='r' style='color:#1A7F37'>−{_inr(price_b - price_a)}</td></tr>")
        st.markdown(
            f"""<table class="styled-table"><thead><tr><th>Metric</th><th class="r">Current</th>
            <th class="r">Optimised</th><th class="r">Saving</th></tr></thead><tbody>{rows}</tbody></table>""",
            unsafe_allow_html=True)
        parts = []
        for lvl in sel_levels:
            n = notes.get(lvl, {})
            if not n or n.get("clusters", 0) == 0:
                parts.append(f"**{lvl}** — no similar skills at this level")
            elif n.get("suggested", 0) > 0:
                parts.append(f"**{lvl}** — {n['suggested']} move(s)")
            else:
                why = " (needs shift coverage)" if lvl == "L2" else ""
                parts.append(f"**{lvl}** — similar skills found, but sharing didn't cut FTE at the "
                             f"current setting{why}")
        st.caption("What was analysed: " + "  ·  ".join(parts))
        st.caption("How it works: adjacent skills share Architect/L3 (and L2 within one coverage "
                   "window); a shared pool always covers the widest window, so coverage never drops. "
                   "Only moves that cut FTE and keep utilisation under the ceiling are shown.")


# ──────────────────────────────────────────────────────────────────────────────
# Tab 6 — Approve & Export (end-of-journey lifecycle; parity with single Step 10)
# ──────────────────────────────────────────────────────────────────────────────
def _render_multi_summary_metrics(model):
    """Headline metrics row shared by the preparer tab and the reviewer view."""
    cr, pr = model["cost_result"], model["price_result"]
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total FTE", f"{model.get('total_fte', 0):.1f}")
    m2.metric("Resource cost / mo", _inr(model.get("total_resource_cost", 0)))
    m3.metric("Delivery cost / mo", _inr(cr.get("total_delivery_cost", 0)))
    m4.metric(f"Selling price / mo ({pr.get('margin_pct', 0):.0f}%)", _inr(pr.get("selling_price", 0)))


def _render_skill_table(skills):
    """Skills basis for the approver: family, active levels, coverage, architect per skill."""
    section_hdr("🧩 Skills")
    rows = ""
    for sk in skills:
        lvls = ", ".join([l for l in LEVELS if l in (sk.get("active_levels") or [])]) or "—"
        arch = f"{float(sk.get('architect_pct', 0) or 0):.0f}%" if sk.get("has_architect") else "—"
        rows += (f"<tr><td>{sk.get('name') or sk['id']}</td><td>{sk.get('genus_category', '')}</td>"
                 f"<td>{lvls}</td><td>{sk.get('coverage_model', '')}</td><td class='r'>{arch}</td></tr>")
    st.markdown(
        f"""<table class="styled-table"><thead><tr><th>Skill</th><th>Family</th>
        <th>Active Levels</th><th>Coverage</th><th class="r">Architect</th></tr></thead>
        <tbody>{rows}</tbody></table>""", unsafe_allow_html=True)


def _render_workload_summary(skills):
    """Monthly workload volumes per skill (the demand behind the commercials)."""
    from modules.state.multi_state import skill_volumes
    section_hdr("📊 Workload Summary (monthly)")
    cats = ["alerts", "service_requests", "incidents", "changes"]
    tot = {c: 0 for c in cats}
    tot_srv = 0
    rows = ""
    for sk in skills:
        v = skill_volumes(sk)
        p = sk.get("patching") or {}
        srv = int(p.get("num_servers", 0) or 0) if p.get("included") else 0
        nact = len(sk.get("activities") or [])
        cells = ""
        for c in cats:
            cnt = int(v.get(c, 0) or 0)
            tot[c] += cnt
            cells += f"<td class='r'>{cnt or '—'}</td>"
        tot_srv += srv
        rows += (f"<tr><td>{sk.get('name') or sk['id']}</td>{cells}"
                 f"<td class='r'>{srv or '—'}</td><td class='r'>{nact or '—'}</td></tr>")
    tcells = "".join(f"<td class='r'><strong>{tot[c]}</strong></td>" for c in cats)
    rows += (f"<tr class='total-row'><td><strong>Total</strong></td>{tcells}"
             f"<td class='r'><strong>{tot_srv or '—'}</strong></td><td></td></tr>")
    st.markdown(
        f"""<table class="styled-table"><thead><tr><th>Skill</th>
        <th class="r">Alerts</th><th class="r">Service Requests</th><th class="r">Incidents</th>
        <th class="r">Changes</th><th class="r">Patch Servers</th><th class="r">Activities</th>
        </tr></thead><tbody>{rows}</tbody></table>""", unsafe_allow_html=True)


def _render_cost_by_skill(model, names):
    """Per-skill monthly resource cost table (moved here from Rates & Cost)."""
    section_hdr("📦 Cost by Skill (monthly)")
    crows = ""
    for sid, ps in model["per_skill"].items():
        crows += (f"<tr><td>{names.get(sid, sid)}</td><td>{ps['genus_category']}</td>"
                  f"<td class='r'>{_inr(ps.get('cost', 0))}</td></tr>")
    crows += (f"<tr class='total-row'><td><strong>Resource cost</strong></td><td></td>"
              f"<td class='r'><strong>{_inr(model['total_resource_cost'])}</strong></td></tr>")
    st.markdown(
        f"""<table class="styled-table"><thead><tr><th>Skill</th><th>Family</th>
        <th class="r">Monthly Cost (INR)</th></tr></thead><tbody>{crows}</tbody></table>""",
        unsafe_allow_html=True)


def _render_management_summary(state):
    """Per-skill FTE build-up for management visibility, so the Raw→Rounded variance is
    self-explanatory: L1/L2/L3/Architect effort (hrs) + three FTE stages per skill —
    **Raw** (workload only, breakdown.fte_raw) → **+ Buffer & Contingency** (un-rounded
    requirement, breakdown.fte_final) → **Rounded** (delivered, breakdown.fte_staffed, each
    skill × level to a 0.5-person minimum). SDM + grand totals; a note when pooling applies."""
    section_hdr("📋 Management Summary")
    st.caption("The FTE build-up per skill: **Raw** (workload only) → **+ Buffer & Contingency** "
               "(the un-rounded requirement) → **Rounded** (delivered team; each skill × level rounded "
               "up to a 0.5-person minimum). L1–Architect are monthly effort hours. SDM is one "
               "engagement resource.")
    model = compute_multi_skill_model({**state, "fte_basis": "rounded"})
    names = {s["id"]: (s.get("name") or s["id"]) for s in st.session_state.get("skills", [])}

    tot_hrs = {lvl: 0.0 for lvl in BD_LEVELS}
    t_raw = t_fin = t_rnd = 0.0
    body = ""
    for sid, ps in model["per_skill"].items():
        rh, bd = ps["role_hours"], ps["breakdown"]
        raw = sum(bd[l]["fte_raw"] for l in BD_LEVELS)
        fin = sum(bd[l]["fte_final"] for l in BD_LEVELS)
        rnd = sum(bd[l]["fte_staffed"] for l in BD_LEVELS)
        hcells = "".join(f"<td class='r'>{rh.get(l, 0.0):.0f}</td>" for l in BD_LEVELS)
        for l in BD_LEVELS:
            tot_hrs[l] += rh.get(l, 0.0)
        t_raw += raw; t_fin += fin; t_rnd += rnd
        body += (f"<tr><td>{names.get(sid, sid)}</td><td>{ps['genus_category']}</td>"
                 f"<td>{ps['coverage_model']}</td>{hcells}"
                 f"<td class='r'>{raw:.2f}</td><td class='r'>{fin:.2f}</td>"
                 f"<td class='r'><strong>{rnd:.1f}</strong></td></tr>")
    sdm = next((r for r in model["resources"] if r["level"] == "SDM"), None)
    if sdm and (float(sdm.get("fte", 0) or 0) or float(sdm.get("raw_fte", 0) or 0)):
        sr, sf, sh = float(sdm["raw_fte"]), float(sdm["fte"]), float(model.get("sdm_hours", 0) or 0)
        body += (f"<tr><td>SDM <span style='color:#7A8A99'>(engagement)</span></td><td>—</td><td>—</td>"
                 f"<td class='r' colspan='4'>{sh:.0f}h</td>"
                 f"<td class='r'>{sr:.2f}</td><td class='r'>{sr:.2f}</td>"
                 f"<td class='r'><strong>{sf:.1f}</strong></td></tr>")
        t_raw += sr; t_fin += sr; t_rnd += sf
    tcells = "".join(f"<td class='r'><strong>{tot_hrs[l]:.0f}</strong></td>" for l in BD_LEVELS)
    body += (f"<tr class='total-row'><td><strong>Total</strong></td><td></td><td></td>{tcells}"
             f"<td class='r'><strong>{t_raw:.2f}</strong></td><td class='r'><strong>{t_fin:.2f}</strong></td>"
             f"<td class='r'><strong>{t_rnd:.1f}</strong></td></tr>")
    st.markdown(
        f"""<table class="styled-table"><thead><tr>
        <th>Skill</th><th>Family</th><th>Coverage</th>
        <th class="r">L1 h</th><th class="r">L2 h</th><th class="r">L3 h</th><th class="r">Arch h</th>
        <th class="r">Raw FTE</th><th class="r">+ Buffer&amp;Cont</th><th class="r">Rounded FTE</th>
        </tr></thead><tbody>{body}</tbody></table>""", unsafe_allow_html=True)
    st.caption(f"Reconciliation: **Raw {t_raw:.2f}** → **+ Buffer & Contingency {t_fin:.2f}** → "
               f"**Rounded {t_rnd:.1f}** (delivered). The +{t_rnd - t_raw:.1f} FTE is buffer/contingency "
               "plus the 0.5-per-cell minimum-staffing round-up.")
    if state.get("resource_sharing"):
        st.caption(f"ℹ️ Resource sharing is applied: pooling combines fractional roles, so the delivered "
                   f"team is **{model['total_fte']:.1f} FTE** (below the per-skill Rounded total above). "
                   "See the Optimize tab.")


def _render_excel_export():
    st.caption("Download the full working model as an Excel workbook — the numbers equal the engine.")
    if st.button("📊 Prepare Excel export", key="ms_ax_xlsx_prep", type="secondary"):
        from modules.outputs.multi_excel_export import generate_multi_excel_report
        with st.spinner("Building workbook…"):
            st.session_state["_ms_xlsx"] = generate_multi_excel_report()
    if st.session_state.get("_ms_xlsx"):
        from datetime import date
        st.download_button("⬇️ Download .xlsx", data=st.session_state["_ms_xlsx"],
                           file_name=f"multi_skill_estimate_{date.today():%Y%m%d}.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           key="ms_ax_xlsx_dl")


def _render_approve_export():
    section_hdr("✅ Approve & Export")
    skills = st.session_state.get("skills", [])
    if not skills:
        callout("Add a skill and its workload first (tabs 1–2).", "info")
        return
    # RFP / Customer name at the top so the approver has the estimate's identity.
    proj = (st.session_state.get("project_name") or "").strip()
    ref = st.session_state.get("_current_estimate_ref")
    if proj:
        vtxt = f" — v{ref['version']}" if ref and ref.get("version") else ""
        st.markdown(f"<div style='font-size:1.15rem;font-weight:700;color:#0D1B2A;margin:-.2rem 0 .4rem'>"
                    f"📄 {proj}{vtxt}</div>", unsafe_allow_html=True)
    else:
        callout("Name this estimate (Customer / RFP) at the top of the page before saving a "
                "version or requesting approval.", "warning")
    state = _build_multi_state()
    basis = "Raw (theoretical minimum)" if state.get("fte_basis") == "raw" else "Rounded (delivered team)"
    st.caption(f"Reported on the **{basis}** basis — change it on the Effort & FTE tab.")
    model = compute_multi_skill_model(state)
    _render_multi_summary_metrics(model)
    st.divider()

    # Basis of the commercials: skills (structure) + workload (demand).
    _render_skill_table(skills)
    st.divider()
    _render_workload_summary(skills)
    st.divider()

    # Cost by Skill (monthly) — moved here from Rates & Cost.
    _render_cost_by_skill(model, {s["id"]: (s.get("name") or s["id"]) for s in skills})
    st.divider()

    # Management summary — per-skill effort/FTE by level, coverage, Raw & Rounded FTE.
    _render_management_summary(state)
    st.divider()

    # Raw vs Rounded comparison (folded in here from the former standalone tab).
    _render_raw_vs_rounded()
    st.divider()

    from modules.outputs.approval import render_approval_panel, change_state
    # Post-approval divergence banner + lock (parity with single-mode Step 10).
    cs = change_state()
    if cs["diverged"]:
        callout("🔴 This approved estimate has changed. Save it as a <strong>new version</strong> "
                "below before exporting or re-requesting approval.", "error")
    render_approval_panel(locked=cs["diverged"], rec=cs["rec"])

    st.divider()
    section_hdr("📤 Export")
    _render_excel_export()


def render_multi_approve_export(review: bool = False):
    """Full-page multi-skill Approve & Export view for a reviewer opening the tokened
    link (no tabs/sidebar): a read-only summary + the approval panel. The single-mode
    Step 10 dashboard can't render multi inputs, so multi reviewers land here."""
    page_header(0, "Multi-skill Estimate — Approve & Export",
                "Review the estimate summary, then approve or reject it.")
    ref = st.session_state.get("_current_estimate_ref")
    if ref:
        st.caption(f"Estimate: **{ref.get('project', '')} — v{ref.get('version', '')}**")
    skills = st.session_state.get("skills", [])
    if skills:
        state = _build_multi_state()
        model = compute_multi_skill_model(state)
        _render_multi_summary_metrics(model)
        st.divider()
        _render_skill_table(skills)
        st.divider()
        _render_workload_summary(skills)
        st.divider()
        _render_cost_by_skill(model, {s["id"]: (s.get("name") or s["id"]) for s in skills})
        st.divider()
        _render_management_summary(state)
        st.divider()
        _render_raw_vs_rounded()
        st.divider()
    from modules.outputs.approval import render_approval_panel
    render_approval_panel()


# ──────────────────────────────────────────────────────────────────────────────
# Tab 7 — Versions & Compare (parity with single-mode Saved Calculations + Compare)
# ──────────────────────────────────────────────────────────────────────────────
def _fmt_version(it) -> str:
    ts = (it.get("saved_at") or "")
    if "T" in ts:
        d, _, t = ts.partition("T")
        ts = f"{d} {t.replace('-', ':')[:5]} UTC"
    return f"v{it['version']} · {ts}"


def _render_versions_compare():
    section_hdr("🗂️ Versions & Compare")
    from modules.state.estimate_store import store_configured
    if not store_configured():
        callout("Cloud storage isn't configured in this environment, so saved versions aren't "
                "available here. On the deployed app this lists your saved estimates.", "info")
        return
    from modules.state.estimate_store import list_estimates, load_estimate
    from modules.state.session_manager import load_scenario, mark_saved_baseline, model_from_inputs

    try:
        items = list_estimates()
    except Exception as e:
        callout(f"Couldn't list saved versions: {type(e).__name__}: {e}", "warning")
        return
    if not items:
        callout("No saved versions yet. Save one from the **Approve & Export** tab, then reopen "
                "or compare versions here.", "info")
        return

    # ── Open a saved version ─────────────────────────────────────
    st.markdown("**📂 Open a saved version** — loads it back into this estimate")
    projects = sorted({(it["project"] or it["slug"]) for it in items})
    o1, o2, o3 = st.columns([2, 2, 1.1])
    sel_proj = o1.selectbox("Project", projects, key="ms_ver_proj")
    versions = sorted([it for it in items if (it["project"] or it["slug"]) == sel_proj],
                      key=lambda x: x["version"], reverse=True)
    sel = o2.selectbox("Version (newest first)", versions, format_func=_fmt_version, key="ms_ver_ver")
    o3.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
    if o3.button("📥 Load", key="ms_ver_load", use_container_width=True, type="primary"):
        try:
            data = load_estimate(sel["blob"])
            load_scenario({"inputs": data.get("inputs", {})})
            st.session_state["_current_estimate_ref"] = {
                "slug": sel["slug"], "version": sel["version"],
                "project": (data.get("meta", {}) or {}).get("project", sel["project"]),
                "blob": sel["blob"]}
            mark_saved_baseline()
            st.success(f"Loaded {sel_proj} v{sel['version']}.")
            st.rerun()
        except Exception as e:
            st.error(f"Load failed: {e}")

    st.divider()
    # ── Compare versions ─────────────────────────────────────────
    st.markdown("**📊 Compare versions** — pick 2 or more to see them side by side")
    labels = {f"{(it['project'] or it['slug'])} · v{it['version']}": it for it in items}
    chosen = st.multiselect("Versions to compare", list(labels), key="ms_cmp_pick",
                            help="Each is recomputed from its stored inputs, so numbers match the engine.")
    if len(chosen) < 2:
        st.caption("Select at least 2 saved versions to compare.")
        return
    models = {}
    with st.spinner("Recomputing selected versions…"):
        for lbl in chosen:
            try:
                data = load_estimate(labels[lbl]["blob"])
                models[lbl] = model_from_inputs(data.get("inputs", {}))
            except Exception:
                pass
    if len(models) < 2:
        callout("Couldn't recompute enough of the selected versions to compare.", "warning")
        return
    _render_multi_comparison(models)


def _render_multi_comparison(models: dict):
    """Side-by-side headline metrics for the selected versions. Uses only keys common to
    both single and multi models, so a mixed selection still compares cleanly."""
    lbls = list(models.keys())

    def _skills(m):
        ps = m.get("per_skill")
        return str(len(ps)) if isinstance(ps, dict) and ps else "—"

    rows = [
        ("Skills",              _skills),
        ("Total FTE",           lambda m: f"{float(m.get('total_fte', 0) or 0):.1f}"),
        ("Resource cost / mo",  lambda m: _inr((m.get("cost_result") or {}).get("resource_cost", 0))),
        ("Delivery cost / mo",  lambda m: _inr((m.get("cost_result") or {}).get("total_delivery_cost", 0))),
        ("Margin",              lambda m: f"{float((m.get('price_result') or {}).get('margin_pct', 0) or 0):.0f}%"),
        ("Selling price / mo",  lambda m: _inr((m.get("price_result") or {}).get("selling_price", 0))),
    ]
    head = "".join(f"<th class='r'>{l}</th>" for l in lbls)
    body = ""
    for name, fn in rows:
        cells = "".join(f"<td class='r'>{fn(models[l])}</td>" for l in lbls)
        body += f"<tr><td>{name}</td>{cells}</tr>"
    st.markdown(
        f"""<table class="styled-table"><thead><tr><th>Metric</th>{head}</tr></thead>
        <tbody>{body}</tbody></table>""", unsafe_allow_html=True)
    st.caption("Each version is recomputed from its stored inputs (engine-recalculated), so the "
               "comparison stays consistent with the live model.")


# ──────────────────────────────────────────────────────────────────────────────
# Raw vs Rounded — two estimate versions, shown as a section inside Approve & Export
# ──────────────────────────────────────────────────────────────────────────────
def _render_raw_vs_rounded():
    section_hdr("⚖️ Raw vs Rounded")
    skills = st.session_state.get("skills", [])
    if not skills:
        callout("Add a skill and its workload first (tabs 1–2).", "info")
        return
    state = _build_multi_state()
    raw = compute_multi_skill_model({**state, "fte_basis": "raw"})
    rnd = compute_multi_skill_model({**state, "fte_basis": "rounded"})
    chosen = "Raw + Buffer & Contingency (un-rounded)" if state.get("fte_basis") == "raw" \
        else "Rounded (delivered)"
    callout(f"The two priced views of the same estimate. <strong>Raw + Buffer & Contingency</strong> = "
            f"the un-rounded requirement (workload + buffer + contingency, before whole/half-person "
            f"rounding). <strong>Rounded</strong> = the delivered team (each skill × level rounded up to "
            f"0.5, min 0.5). Pricing, approval &amp; export currently use <strong>{chosen}</strong> — "
            f"switch it on the Effort &amp; FTE tab. (The pre-overhead workload demand is the “Raw FTE” "
            f"column in the Management Summary above.)", "info")

    def _r(lbl, rv, fv, fmt):
        d = fv - rv
        return (f"<tr><td>{lbl}</td><td class='r'>{fmt(rv)}</td><td class='r'>{fmt(fv)}</td>"
                f"<td class='r' style='color:#7A8A99'>{'+' if d >= 0 else ''}{fmt(d)}</td></tr>")
    fte = lambda v: f"{v:.2f}"
    cr_r, cr_f, pr_r, pr_f = raw["cost_result"], rnd["cost_result"], raw["price_result"], rnd["price_result"]
    body = (
        _r("Total FTE", raw["total_fte"], rnd["total_fte"], fte)
        + _r("Resource cost / mo", raw["total_resource_cost"], rnd["total_resource_cost"], _inr)
        + _r("Delivery cost / mo", cr_r["total_delivery_cost"], cr_f["total_delivery_cost"], _inr)
        + _r("Selling price / mo", pr_r["selling_price"], pr_f["selling_price"], _inr)
        + _r("Gross profit / mo", pr_r["gross_profit"], pr_f["gross_profit"], _inr))
    st.markdown(
        f"""<table class="styled-table"><thead><tr><th>Metric</th>
        <th class="r">Raw + Buffer&amp;Cont (un-rounded)</th><th class="r">Rounded (delivered)</th>
        <th class="r">Δ (Rounded − Raw)</th></tr></thead><tbody>{body}</tbody></table>""",
        unsafe_allow_html=True)
    gap = rnd["total_fte"] - raw["total_fte"]
    if raw["total_fte"] > 0 and gap > 0.05:
        st.caption(f"Rounding adds **{gap:.1f} FTE ({gap / raw['total_fte'] * 100:.0f}%)** and "
                   f"**{_inr(rnd['total_resource_cost'] - raw['total_resource_cost'])}/mo** resource cost — "
                   "the price of indivisible people. Pool L2/L3/Architect on the Optimize tab to reduce it.")


def _roster_config() -> dict:
    """RosterConfig from session_state (self-healing defaults). Read by the deterministic
    scheduler; the roster never writes back to the estimate."""
    return {
        "strategy": st.session_state.get("roster_strategy", "Balanced"),
        "customer_tz": st.session_state.get("roster_customer_tz", "EST"),
        "delivery_tz": st.session_state.get("roster_delivery_tz", "IST"),
        "business_start": st.session_state.get("roster_bh_start", "09:00"),
        "business_end": st.session_state.get("roster_bh_end", "17:00"),
        "shift_length_h": st.session_state.get("roster_shift_len", 8),
        "coverage_prefs": st.session_state.get("roster_prefs", {}) or {},
    }


def _idx(choices, val, default=0):
    return choices.index(val) if val in choices else default


def _render_roster():
    from modules.roster.scheduler import (build_roster, CUSTOMER_TZ_CHOICES,
                                          DELIVERY_TZ_CHOICES, COVERAGE_PREF_MODES)
    section_hdr("🗓️ Shift Plan")
    skills = st.session_state.get("skills", [])
    if not skills:
        callout("Add a skill and its workload first (tabs 1–2).", "info")
        return
    callout("A proposal-ready coverage &amp; shift plan <strong>derived from the final estimate</strong> — "
            "it regenerates when the estimate changes and never affects effort, FTE or commercials. "
            "Whole-person <strong>seats = ⌈delivered FTE⌉</strong> (the coverage relief factor is already "
            "baked into the FTE, so there's no double-count).", "info")

    # ── Config strip ──
    c1, c2, c3, c4 = st.columns(4)
    st.session_state["roster_customer_tz"] = c1.selectbox(
        "Customer time zone", CUSTOMER_TZ_CHOICES,
        index=_idx(CUSTOMER_TZ_CHOICES, st.session_state.get("roster_customer_tz", "EST")),
        key="roster_customer_tz_w")
    st.session_state["roster_delivery_tz"] = c2.selectbox(
        "Delivery time zone", DELIVERY_TZ_CHOICES,
        index=_idx(DELIVERY_TZ_CHOICES, st.session_state.get("roster_delivery_tz", "IST")),
        key="roster_delivery_tz_w")
    st.session_state["roster_bh_start"] = c3.text_input(
        "Business hours from", value=st.session_state.get("roster_bh_start", "09:00"),
        key="roster_bh_start_w", help="Customer local time, HH:MM.")
    st.session_state["roster_bh_end"] = c4.text_input(
        "Business hours to", value=st.session_state.get("roster_bh_end", "17:00"),
        key="roster_bh_end_w", help="Customer local time, HH:MM.")

    s1, s2 = st.columns(2)
    st.session_state["roster_shift_len"] = s1.selectbox(
        "Shift length (hours)", [8, 12],
        index=_idx([8, 12], int(st.session_state.get("roster_shift_len", 8) or 8)),
        key="roster_shift_len_w")
    st.session_state["roster_strategy"] = s2.selectbox(
        "Roster strategy", ["Balanced"], index=0, key="roster_strategy_w",
        help="Cost-Optimized, Max-Coverage and Follow-the-Sun strategies arrive in a later phase.")

    # ── Per-skill coverage window preference (only for non-24×7 skills) ──
    non247 = [s for s in skills if (s.get("coverage_model") or "8×5") != "24×7"]
    prefs = dict(st.session_state.get("roster_prefs", {}) or {})
    if non247:
        with st.expander("Coverage window preference (per non-24×7 skill)", expanded=False):
            st.caption("Where each skill's coverage window sits in the customer's day. 24×7 skills "
                       "run the full day and aren't listed here.")
            for s in non247:
                sid = s["id"]; nm = s.get("name") or sid
                p = dict(prefs.get(sid, {}) or {})
                row = st.columns([2.4, 2, 1.3, 1.3])
                row[0].markdown(f"**{nm}** · {s.get('coverage_model')}")
                p["mode"] = row[1].selectbox(
                    "Window", COVERAGE_PREF_MODES, index=_idx(COVERAGE_PREF_MODES, p.get("mode", "Business Hours")),
                    key=f"roster_mode_{sid}", label_visibility="collapsed")
                if p["mode"] == "Custom Window":
                    p["start"] = row[2].text_input("From", value=p.get("start", "09:00"),
                                                   key=f"roster_cs_{sid}", label_visibility="collapsed")
                    p["end"] = row[3].text_input("To", value=p.get("end", "17:00"),
                                                 key=f"roster_ce_{sid}", label_visibility="collapsed")
                prefs[sid] = p
    st.session_state["roster_prefs"] = prefs

    # ── Build the roster (deterministic; rounded/delivered team) ──
    state = _build_multi_state()
    model = compute_multi_skill_model({**state, "fte_basis": "rounded"})
    plan = build_roster(model, _roster_config())

    tot = plan["totals"]
    m1, m2, m3 = st.columns(3)
    m1.metric("Delivered FTE", f"{tot['delivered_fte']:.2f}")
    m2.metric("Deployable seats", f"{tot['deployable_seats']}")
    m3.metric("Δ (seats − FTE)", f"+{tot['delta']:.2f}")
    st.caption(f"Shifts shown in **{plan['customer_tz']} (customer)** and **{plan['delivery_tz']} "
               f"(delivery)** time · business hours {plan['business_hours']}.")
    st.divider()

    # Reconciliation: billed FTE → whole heads
    section_hdr("🔗 FTE → Deployable Seats")
    rrows = ""
    for r0 in plan["reconciliation"]:
        rrows += (f"<tr><td>{r0['skill']}</td><td>{r0['level']}</td><td>{r0['coverage']}</td>"
                  f"<td class='r'>{r0['fte']:.2f}</td><td class='r'>{r0['seats']}</td>"
                  f"<td class='r' style='color:#7A8A99'>+{r0['delta']:.2f}</td></tr>")
    rrows += (f"<tr class='total-row'><td><strong>Total</strong></td><td></td><td></td>"
              f"<td class='r'><strong>{tot['delivered_fte']:.2f}</strong></td>"
              f"<td class='r'><strong>{tot['deployable_seats']}</strong></td>"
              f"<td class='r'><strong>+{tot['delta']:.2f}</strong></td></tr>")
    st.markdown(
        f"""<table class="styled-table"><thead><tr><th>Skill</th><th>Level</th><th>Coverage</th>
        <th class="r">Billed FTE</th><th class="r">Seats</th><th class="r">Δ</th></tr></thead>
        <tbody>{rrows}</tbody></table>""", unsafe_allow_html=True)
    st.caption("Seats are whole people (⌈FTE⌉) for a realistic shift plan. The **billed FTE is "
               "unchanged** — the delta is the rounding to indivisible heads, not a commercial change.")
    st.divider()

    # Shift-timing legend: map each cell label to a real clock window (customer + delivery).
    section_hdr("🕒 Shift Timings")
    trows = "".join(
        f"<tr><td>{t['label']}</td><td class='r'>{t['customer']}</td><td class='r'>{t['delivery']}</td></tr>"
        for t in plan["shift_timings"])
    st.markdown(
        f"""<table class="styled-table"><thead><tr><th>Shift</th>
        <th class="r">Customer ({plan['customer_tz']})</th>
        <th class="r">Delivery ({plan['delivery_tz']})</th></tr></thead><tbody>{trows}</tbody></table>""",
        unsafe_allow_html=True)
    st.divider()

    # Weekly roster (person × weekday) — the proposal roster in the requested format.
    section_hdr("🗓️ Weekly Roster")
    cell_bg = {"Morning": "#D6F0ED", "Evening": "#A8DDD8", "Night": "#1A5F6A",
               "Day": "#EAF3F4", "On-Call": "#FBEED9"}
    cell_fg = {"Night": "#FFFFFF"}
    dcols = "".join(f"<th class='r'>{d}</th>" for d in plan["days"])
    prows = ""
    for p0 in plan["people"]:
        cells = ""
        for v in p0["cells"]:
            bg = cell_bg.get(v, "")
            fg = cell_fg.get(v, "#1B2A3A")
            style = f"background:{bg};color:{fg};" if bg else "color:#B8C2CC;"
            cells += f"<td class='r' style='{style}font-size:.82rem'>{v or '—'}</td>"
        prows += (f"<tr><td style='white-space:nowrap'>{p0['employee']}</td>"
                  f"<td style='white-space:nowrap'>{p0['role']}</td>{cells}</tr>")
    st.markdown(
        f"""<table class="styled-table"><thead><tr><th>Employee</th><th>Role</th>{dcols}</tr></thead>
        <tbody>{prows}</tbody></table>""", unsafe_allow_html=True)
    for n in plan["roster_notes"]:
        st.caption("• " + n)
    st.divider()

    # Advisories (informational — never affect commercials)
    if plan["advisories"]:
        section_hdr("⚠️ Coverage Advisories")
        st.caption("Feasibility notes only — these do **not** change effort, FTE or price.")
        for a in plan["advisories"]:
            callout(a, "warning")
    else:
        st.success("Coverage looks feasible for the proposed team.")
    st.divider()

    # Export
    section_hdr("📤 Export")
    st.caption("Download the shift plan as a presentation-ready Excel appendix.")
    if st.button("🗓️ Prepare Shift Plan Excel", key="roster_xlsx_prep", type="secondary",
                 disabled=_locked()):
        from modules.outputs.roster_excel import build_roster_workbook
        with st.spinner("Building shift plan…"):
            st.session_state["_roster_xlsx"] = build_roster_workbook(
                plan, (st.session_state.get("project_name") or "").strip())
    if st.session_state.get("_roster_xlsx"):
        from datetime import date
        st.download_button(
            "⬇️ Download shift plan (.xlsx)", data=st.session_state["_roster_xlsx"],
            file_name=f"shift_plan_{date.today():%Y%m%d}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="roster_xlsx_dl")


def _transition_config() -> dict:
    """TransitionConfig from session_state (self-healing). Read by the deterministic builder;
    the transition plan never writes back to the estimate."""
    from modules.transition.builder import default_phase_config
    return {
        "start_date": st.session_state.get("transition_start"),
        "duration_weeks": st.session_state.get("transition_duration_weeks", 20),
        "go_live_date": st.session_state.get("transition_go_live"),
        "customer_tz": st.session_state.get("transition_customer_tz", "EST"),
        "sequencing": st.session_state.get("transition_sequencing", "Sequential"),
        "incumbent_present": st.session_state.get("transition_incumbent", True),
        "phases": st.session_state.get("transition_phase_cfg") or default_phase_config(),
    }


_BAND_COLOR = {"Service Strategy": "#1A5F6A", "Service Design": "#2E7D8A",
               "Service Transition": "#3E9AA6", "Service Operations": "#7FC4C4"}


def _render_transition():
    from datetime import date, timedelta
    from modules.transition.builder import build_transition_plan, default_phase_config
    from modules.roster.scheduler import CUSTOMER_TZ_CHOICES
    section_hdr("🚀 Transition Strategy")
    skills = st.session_state.get("skills", [])
    if not skills:
        callout("Add a skill and its workload first (tabs 1–2).", "info")
        return
    callout("A proposal-ready, ITIL-aligned <strong>Transition Strategy</strong> derived from the "
            "estimate and your dates — timeline (Gantt), phase activities, skill-wise plan, RACI and "
            "deliverables. Read-only: it never affects effort, FTE or commercials.", "info")

    # ── Config strip ──
    c1, c2, c3 = st.columns(3)
    st.session_state["transition_start"] = c1.date_input(
        "Transition start", value=st.session_state.get("transition_start") or (date.today() + timedelta(days=30)),
        key="transition_start_w")
    st.session_state["transition_go_live"] = c2.date_input(
        "Customer Go-Live", value=st.session_state.get("transition_go_live") or (date.today() + timedelta(days=140)),
        key="transition_gl_w")
    # Overall duration is derived from the two dates (window to Go-Live) — not an editable input.
    _tstart = st.session_state.get("transition_start")
    _tgl = st.session_state.get("transition_go_live")
    _dur_weeks = round((_tgl - _tstart).days / 7.0, 1) if (_tstart and _tgl and _tgl > _tstart) else 0.0
    st.session_state["transition_duration_weeks"] = _dur_weeks
    c3.metric("Duration → Go-Live", f"{_dur_weeks:g} weeks")

    c4, c5, c6 = st.columns(3)
    st.session_state["transition_customer_tz"] = c4.selectbox(
        "Customer time zone", CUSTOMER_TZ_CHOICES,
        index=_idx(CUSTOMER_TZ_CHOICES, st.session_state.get("transition_customer_tz", "EST")),
        key="transition_tz_w")
    st.session_state["transition_sequencing"] = c5.selectbox(
        "Phase sequencing", ["Sequential", "Overlap"],
        index=_idx(["Sequential", "Overlap"], st.session_state.get("transition_sequencing", "Sequential")),
        key="transition_seq_w")
    st.session_state["transition_incumbent"] = c6.checkbox(
        "Incumbent / outgoing vendor present", value=st.session_state.get("transition_incumbent", True),
        key="transition_inc_w", help="Shadow & Reverse-Shadow assume live operations to shadow.")

    # ── Per-phase duration / include / overlap editor ──
    seq = st.session_state.get("transition_sequencing")
    overlap = seq == "Overlap"
    phases = st.session_state.get("transition_phase_cfg") or default_phase_config()
    # Overlap only changes the timeline via each phase's lead (weeks). Those default to 0, and
    # overlap-with-0-lead == sequential — so on the first switch to Overlap, seed a visible default
    # (1 wk) on non-first phases so the Gantt actually moves. (Only when all leads are still 0, so
    # we never clobber the user's own leads.)
    if overlap and st.session_state.get("_transition_seq_prev") != "Overlap" \
            and all(int(p.get("overlap_lead_weeks", 0) or 0) == 0 for p in phases[1:]):
        for p in phases[1:]:
            p["overlap_lead_weeks"] = 1
            st.session_state.pop(f"tr_lead_{p['key']}", None)   # let the widget pick up the seed
    st.session_state["_transition_seq_prev"] = seq

    with st.expander("Phase durations & sequencing", expanded=overlap):
        st.markdown(
            "**What this is** — the length of each transition phase (in weeks) and how phases are "
            "scheduled relative to each other. This shapes the Gantt and where Go-Live lands.\n\n"
            "**How to use**\n"
            "- **Weeks** — set each phase's duration. Leave a phase at its default if unsure.\n"
            "- **Incl.** — uncheck to *exclude* a phase (e.g. skip **Reverse Shadow** for a small, "
            "low-risk scope, or **Shadow** for a greenfield build with no incumbent to observe).\n"
            "- **Lead** (Overlap mode only) — how many weeks a phase starts *before* the previous one "
            "ends. `0` = no overlap for that phase.\n\n"
            "**Sequential vs Overlap**\n"
            "- **Sequential** — each phase starts when the previous finishes. Lowest risk, cleanest "
            "sign-offs. Use as the default and for regulated / complex / high-risk transitions.\n"
            "- **Overlap** — phases run partly in parallel to *compress the timeline* and hit an "
            "earlier Go-Live. Use when the customer's Go-Live is tight and you have the bench to run "
            "activities concurrently. Trade-off: more coordination, tighter dependencies.\n\n"
            "**Example** — Knowledge Transition 4 wks → Shadow 4 wks. Sequential: Shadow starts week 5. "
            "Set Shadow's **lead = 2** in Overlap: Shadow starts in week 3 (KT still finishing), pulling "
            "Go-Live ~2 weeks earlier. Do the same across phases and the whole plan compresses.")
        st.caption("Tip: watch the **Duration → Go-Live** metric and the Gantt above update as you edit; "
                   "the advisories below flag if your phases overshoot or undershoot the Go-Live date.")
        st.markdown("---")
        hdr = st.columns([3, 1.3, 1.2, 1.6])
        hdr[0].caption("**Phase**")
        hdr[1].caption("**Weeks**")
        hdr[2].caption("**Incl.**")
        hdr[3].caption("**Lead**" if overlap else "")
        for ph in phases:
            cols = st.columns([3, 1.3, 1.2, 1.6])
            cols[0].markdown(f"**{ph['name']}**  \n<span style='color:#7A8A99;font-size:.78rem'>{ph['band']}</span>",
                             unsafe_allow_html=True)
            ph["duration_weeks"] = cols[1].number_input(
                "wks", min_value=0, max_value=52, value=int(ph.get("duration_weeks", 2) or 0), step=1,
                key=f"tr_dur_{ph['key']}", label_visibility="collapsed")
            ph["included"] = cols[2].checkbox("incl.", value=ph.get("included", True),
                                              key=f"tr_inc_{ph['key']}")
            if overlap and ph["key"] != phases[0]["key"]:
                ph["overlap_lead_weeks"] = cols[3].number_input(
                    "lead", min_value=0, max_value=12, value=int(ph.get("overlap_lead_weeks", 0) or 0),
                    step=1, key=f"tr_lead_{ph['key']}", label_visibility="collapsed")
    st.session_state["transition_phase_cfg"] = phases

    # ── Build the plan (deterministic; rounded/delivered team) ──
    state = _build_multi_state()
    model = compute_multi_skill_model({**state, "fte_basis": "rounded"})
    plan = build_transition_plan(model, _transition_config())
    st.divider()

    # ── Summary KPIs (at-a-glance) ──
    _k = st.columns(5)
    _k[0].metric("Span", f"{plan['span_weeks']:g} wks")
    _k[1].metric("Phases", f"{len(plan['timeline'])}")
    _k[2].metric("Milestones", f"{len(plan['milestones'])}")
    _k[3].metric("Skills", f"{len(plan['skill_plans'])}")
    _k[4].metric("RAID items", f"{len(plan['raid_register'])}")
    st.caption("The timeline is always visible below; the detailed sections are collapsed — "
               "expand what you need.")
    st.divider()

    # ── Gantt ──
    section_hdr("📅 Transition Timeline")
    rows = plan["timeline"]
    if rows:
        start = plan["start"]; end = rows[-1]["end"]
        span = max((end - start).days, 1)
        # Month-boundary ticks (as % across the timeline) for the top date axis + gridlines.
        ticks = []
        d = date(start.year + 1, 1, 1) if start.month == 12 else date(start.year, start.month + 1, 1)
        while d < end:
            ticks.append(((d - start).days / span * 100, d))
            d = date(d.year + 1, 1, 1) if d.month == 12 else date(d.year, d.month + 1, 1)
        grid = "".join(f"<div style='position:absolute;left:{p:.1f}%;top:0;bottom:0;width:1px;"
                       f"background:#E6ECEF'></div>" for p, _ in ticks)
        LABELW = "200px"
        # Top date axis: start & end anchored to the edges, month ticks in between.
        axis = (f"<div style='position:absolute;left:0;top:0;font-size:.68rem;color:#7A8A99'>{start:%d-%b}</div>"
                f"<div style='position:absolute;right:0;top:0;font-size:.68rem;color:#7A8A99'>{end:%d-%b}</div>"
                + "".join(f"<div style='position:absolute;left:{p:.1f}%;top:0;transform:translateX(-50%);"
                          f"font-size:.68rem;color:#7A8A99;white-space:nowrap'>{dt:%d-%b}</div>"
                          for p, dt in ticks))
        html = (f"<div style='font-size:.8rem'>"
                f"<div style='display:flex;align-items:flex-end;margin-bottom:3px'>"
                f"<div style='width:{LABELW};flex:none'></div>"
                f"<div style='flex:1;position:relative;height:15px'>{axis}</div></div>")
        for row in rows:
            l = (row["start"] - start).days / span * 100
            w = max((row["end"] - row["start"]).days / span * 100, 1.5)
            col = _BAND_COLOR.get(row["band"], "#3E9AA6")
            ms = f" <strong>◆ {row['milestone']}</strong>" if row["milestone"] else ""
            dur = f"{round(row['duration_weeks'], 1):g}w"
            title = f"{row['start']:%d-%b-%Y} → {row['end']:%d-%b-%Y} · {dur}"
            bar = (f"<div style='position:relative;height:22px'>{grid}"
                   f"<div title='{title}' style='position:absolute;left:{l:.1f}%;width:{w:.1f}%;height:22px;"
                   f"background:{col};border-radius:3px;color:#fff;font-size:.68rem;line-height:22px;"
                   f"text-align:center;overflow:hidden'>{dur}</div></div>")
            html += (f"<div style='display:flex;align-items:center;margin:2px 0'>"
                     f"<div style='width:{LABELW};flex:none;white-space:nowrap;overflow:hidden;"
                     f"text-overflow:ellipsis;padding-right:8px'>{row['name']}{ms}</div>"
                     f"<div style='flex:1'>{bar}</div></div>")
        html += "</div>"
        st.markdown(html, unsafe_allow_html=True)
        _gl = st.session_state.get("transition_go_live")
        _fit = (" · phases scaled to fit **start → Go-Live**, so Reverse-Shadow ends on your Go-Live "
                "date (set the split under *Phase durations & sequencing*)") if _gl else ""
        st.caption(f"Start **{start:%d-%b-%Y}** · span **{plan['span_weeks']:g} weeks** · foundation "
                   f"throughout: *{plan['foundation']}*{_fit}.")
        # Milestone chips
        chips = " ".join(
            f"<span style='background:#FBEED9;border-radius:10px;padding:2px 10px;margin-right:6px;"
            f"font-size:.78rem'>◆ <strong>{m['id']}</strong> {m['date']:%d-%b} — {m['gate']}</span>"
            for m in plan["milestones"])
        if chips:
            st.markdown("<div style='margin-top:6px'>" + chips + "</div>", unsafe_allow_html=True)
        st.caption("▸ Transition completes at **M4** (end of Stabilization). The engagement then "
                   "enters **Steady-State Service Delivery & Continuous Improvement** (BAU) — governed "
                   "by the AMS contract, not part of this transition timeline.")
    st.divider()

    # ── Phase activities ──
    section_hdr("🧭 Phase Activities")
    for p in plan["phase_activities"]:
        ms = f" · ◆ {p['milestone']}" if p.get("milestone") else ""
        with st.expander(f"{p['name']}  ({p['band']}{ms})", expanded=False):
            g1, g2 = st.columns(2)
            g1.markdown("**Objectives**\n" + "\n".join("- " + x for x in p.get("objectives", [])))
            g1.markdown("**Deliverables**\n" + "\n".join("- " + x for x in p.get("deliverables", [])))
            g1.markdown("**Entry criteria**\n" + "\n".join("- " + x for x in p.get("entry", [])))
            g1.markdown("**Exit criteria**\n" + "\n".join("- " + x for x in p.get("exit", [])))
            g2.markdown("**Risks**\n" + "\n".join("- " + x for x in p.get("risks", [])))
            g2.markdown("**Dependencies**\n" + "\n".join("- " + x for x in p.get("dependencies", [])))
            g2.markdown("**Customer responsibilities**\n" + "\n".join("- " + x for x in p.get("customer_resp", [])))
            g2.markdown("**Nagarro responsibilities**\n" + "\n".join("- " + x for x in p.get("nagarro_resp", [])))
    st.divider()

    # ── Skill-wise plan ──
    section_hdr("🧩 Skill-wise Transition Plan")
    for sp in plan["skill_plans"]:
        with st.expander(f"{sp['skill']}  ·  {sp.get('family_label', 'General')}  "
                         f"({', '.join(sp['levels']) or '—'} · {sp['coverage']})",
                         expanded=False):
            s1, s2 = st.columns(2)
            s1.markdown("**Knowledge Transition**\n" + "\n".join("- " + x for x in sp["knowledge_transition"]))
            s1.markdown("**Shadow Support**\n" + "\n".join("- " + x for x in sp["shadow"]))
            s1.markdown("**Reverse Shadow**\n" + "\n".join("- " + x for x in sp["reverse_shadow"]))
            s2.markdown("**Stabilization**\n" + "\n".join("- " + x for x in sp["stabilization"]))
            s2.markdown("**Exit criteria** (KT/Shadow gate)\n"
                        + "\n".join("- " + x for x in sp["exit_criteria"]))
            s2.markdown("**Sign-off criteria** (Go-Live gate)\n"
                        + "\n".join("- " + x for x in sp["signoff_criteria"]))

            # ── Acceptance gate: critical check + fillable register + named sign-off ──
            st.markdown(f"**✅ Critical readiness check — must pass at sign-off:** "
                        f"{sp['family_critical_check']}")
            st.markdown(
                "**📋 Open Items & Residual Risk register** "
                "<span style='color:#7A8A99;font-size:.8rem'>— complete during transition: every open "
                "item highlighted with a named owner &amp; target date and agreed by both parties; "
                "residual risk accepted by both parties before sign-off.</span>",
                unsafe_allow_html=True)
            cols = plan["open_items_columns"]
            header = "| " + " | ".join(cols) + " |"
            sep = "| " + " | ".join(["---"] * len(cols)) + " |"
            blanks = "\n".join("| " + str(i + 1) + " | " + " | ".join([""] * (len(cols) - 1)) + " |"
                               for i in range(3))
            st.markdown(header + "\n" + sep + "\n" + blanks)
            st.markdown("**✍️ Sign-off** — recorded at the gate")
            st.markdown("\n".join(
                f"- **{party} — {role}:**  Name \\_\\_\\_\\_\\_\\_\\_\\_   "
                f"Signature \\_\\_\\_\\_\\_\\_\\_\\_   Date \\_\\_\\_\\_\\_"
                for party, role in plan["signoff_signatories"]))
            st.markdown(plan["signoff_decision"])
    st.divider()

    # ── RACI ──
    with st.expander("👥 RACI Matrix", expanded=False):
        st.caption("R = Responsible · A = Accountable · C = Consulted · I = Informed")
        roles = plan["roles_customer"] + plan["roles_nagarro"]
        raci_bg = {"R": "#D6F0ED", "A": "#A8DDD8", "C": "#EAF3F4", "I": "#F4F6F7"}
        rhead = "".join(f"<th class='r' style='font-size:.68rem'>{ro}</th>" for ro in roles)
        rbody = ""
        for row in plan["raci"]:
            cells = ""
            for ro in roles:
                v = row["raci"].get(ro, "")
                bg = raci_bg.get(v, "")
                cells += (f"<td class='r' style='background:{bg};font-weight:{'700' if v=='A' else '400'};"
                          f"font-size:.72rem'>{v or ''}</td>")
            rbody += f"<tr><td style='font-size:.76rem'>{row['activity']}</td>{cells}</tr>"
        st.markdown(
            f"""<table class="styled-table"><thead><tr><th>Activity</th>{rhead}</tr></thead>
            <tbody>{rbody}</tbody></table>""", unsafe_allow_html=True)
    st.divider()

    # ── Deliverables & gates ──
    with st.expander("📦 Deliverables & Quality Gates", expanded=False):
        drows = ""
        for d in plan["deliverables"]:
            ms = f"◆ {d['milestone']}" if d.get("milestone") else "—"
            dl = "<br>".join("• " + x for x in d.get("deliverables", []))
            ex = "<br>".join("• " + x for x in d.get("exit", []))
            drows += (f"<tr><td><strong>{d['phase']}</strong></td><td style='font-size:.8rem'>{dl}</td>"
                      f"<td style='font-size:.8rem'>{ex}</td><td class='r'>{ms}</td></tr>")
        st.markdown(
            f"""<table class="styled-table"><thead><tr><th>Phase</th><th>Key Deliverables</th>
            <th>Exit / Quality Gate</th><th class="r">Milestone</th></tr></thead>
            <tbody>{drows}</tbody></table>""", unsafe_allow_html=True)
        st.markdown("**Best-practice artifacts**")
        for a in plan["best_practice_artifacts"]:
            st.caption("• " + a)
    st.divider()

    # ── RAID register ──
    with st.expander(f"🧭 RAID Register ({len(plan['raid_register'])})", expanded=False):
        st.caption("Risks · Assumptions · Issues · Dependencies — Risks/Dependencies are seeded from the "
                   "phase plan and Assumptions are listed; **Issues are logged during execution**. "
                   "Complete Owner, Likelihood/Impact, Response and Status during the transition.")
        _raid_bg = {"Risk": "#FBEED9", "Dependency": "#EAF3F4", "Assumption": "#EDF3E6", "Issue": "#FDE7E7"}
        rrows = ""
        for i, item in enumerate(plan["raid_register"], start=1):
            bg = _raid_bg.get(item["type"], "")
            rrows += (f"<tr><td class='r'>{i}</td>"
                      f"<td style='background:{bg};font-size:.76rem'>{item['type']}</td>"
                      f"<td style='font-size:.8rem'>{item['description']}</td>"
                      f"<td style='font-size:.76rem'>{item['phase']}</td>"
                      f"<td></td><td></td><td></td><td></td></tr>")
        st.markdown('<table class="styled-table"><thead><tr>'
                    + "".join(f"<th>{h}</th>" for h in plan["raid_columns"])
                    + f"</tr></thead><tbody>{rrows}</tbody></table>", unsafe_allow_html=True)
    st.divider()

    # ── Governance & communications ──
    with st.expander("🗣️ Governance & Communications", expanded=False):
        st.caption("Cadence of transition forums — attendees and purpose. Escalation & communication "
                   "protocols per skill are in the Skill-wise plan above.")
        grows = ""
        for g in plan["governance_cadence"]:
            grows += (f"<tr><td><strong>{g['forum']}</strong></td>"
                      f"<td class='r' style='font-size:.78rem'>{g['cadence']}</td>"
                      f"<td style='font-size:.78rem'>{g['participants']}</td>"
                      f"<td style='font-size:.78rem'>{g['purpose']}</td></tr>")
        st.markdown('<table class="styled-table"><thead><tr>'
                    + "".join(f"<th>{h}</th>" for h in plan["governance_columns"])
                    + f"</tr></thead><tbody>{grows}</tbody></table>", unsafe_allow_html=True)
    st.divider()

    # ── Advisories ──
    if plan["advisories"]:
        section_hdr("⚠️ Advisories")
        st.caption("Informational — these do **not** change effort, FTE or price.")
        for a in plan["advisories"]:
            callout(a, "warning")
    else:
        st.success("Timeline is consistent and the RACI is valid.")
    st.divider()

    # ── Export ──
    section_hdr("📤 Export")
    st.caption("Download the transition strategy as a presentation-ready Excel appendix.")
    if st.button("🚀 Prepare Transition Excel", key="transition_xlsx_prep", type="secondary",
                 disabled=_locked()):
        from modules.outputs.transition_excel import build_transition_workbook
        with st.spinner("Building transition strategy…"):
            st.session_state["_transition_xlsx"] = build_transition_workbook(
                plan, (st.session_state.get("project_name") or "").strip())
    if st.session_state.get("_transition_xlsx"):
        from datetime import date as _date
        st.download_button(
            "⬇️ Download transition strategy (.xlsx)", data=st.session_state["_transition_xlsx"],
            file_name=f"transition_strategy_{_date.today():%Y%m%d}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="transition_xlsx_dl")


# ──────────────────────────────────────────────────────────────────────────────
# Tab 9 — Transition Cost (leaner transition team per skill + shared SDM; separate line)
# ──────────────────────────────────────────────────────────────────────────────
def _render_transition_cost():
    section_hdr("💸 Transition Cost")
    skills = st.session_state.get("skills", [])
    if not skills:
        callout("Add a skill and its workload first (tabs 1–2).", "info")
        return
    from config.settings import (TRANSITION_DEFAULT_WEEKS, TRANSITION_DEFAULT_UTILISATION,
                                 TRANSITION_DEFAULT_SDM_FTE)
    from modules.transition.costing import (LEVELS, steady_state_seats, reconcile_team,
                                            compute_transition_cost)
    callout("A one-time <strong>transition cost</strong> from a leaner, user-configurable transition "
            "team per skill — <strong>capped by the steady-state team</strong> — plus a shared SDM for "
            "governance. This is a separate line and <strong>never changes the monthly run-rate</strong>.",
            "info")

    state = _build_multi_state()
    model = compute_multi_skill_model({**state, "fte_basis": "rounded"})
    steady = steady_state_seats(model)
    disabled = _locked()

    # ── Config strip (duration defaults to the Transition Strategy window) ──
    _ts = st.session_state.get("transition_start")
    _gl = st.session_state.get("transition_go_live")
    _span = round((_gl - _ts).days / 7) if (_ts and _gl and _gl > _ts) else TRANSITION_DEFAULT_WEEKS
    c1, c2, c3 = st.columns(3)
    weeks = c1.number_input("Transition duration (weeks)", min_value=1, max_value=104,
                            value=int(st.session_state.get("transition_cost_weeks", _span) or _span),
                            step=1, key="tc_weeks_w", disabled=disabled,
                            help="Defaults to the start→Go-Live window from the Transition Strategy tab.")
    st.session_state["transition_cost_weeks"] = weeks
    util = c2.number_input("Utilisation %", min_value=10, max_value=100, step=5,
                           value=int(st.session_state.get("transition_cost_util", TRANSITION_DEFAULT_UTILISATION)),
                           key="tc_util_w", disabled=disabled,
                           help="Share of a transition seat's time on the transition (leanness is mostly "
                                "expressed by fewer seats).")
    st.session_state["transition_cost_util"] = util
    sdm_fte = c3.number_input("SDM transition FTE", min_value=0.0, max_value=5.0, step=0.25,
                              value=float(st.session_state.get("transition_sdm_fte", TRANSITION_DEFAULT_SDM_FTE)),
                              key="tc_sdm_w", disabled=disabled,
                              help="Shared Service Delivery Manager effort for transition governance "
                                   "(planning, reporting, customer coordination, sign-offs).")
    st.session_state["transition_sdm_fte"] = sdm_fte

    # ── Per-skill transition team (capped by steady-state; active levels only) ──
    section_hdr("🧩 Transition Team per Skill")
    tcap1, tcap2 = st.columns([4, 1])
    tcap1.caption("The **steady-state team is the maximum**. Defaults follow AMS best practice "
                  "(senior-weighted); adjust each level as needed.")
    if tcap2.button("↺ AMS defaults", key="tc_reset", type="secondary", disabled=disabled):
        for sid in steady:
            for lvl in LEVELS:
                st.session_state.pop(f"tc_{sid}_{lvl}_w", None)
        st.session_state.pop("transition_team", None)
        st.rerun()

    team0 = reconcile_team(st.session_state.get("transition_team") or {}, steady)
    hdr = st.columns([2.4, 1, 1, 1, 1])
    hdr[0].markdown("**Skill**")
    for i, lvl in enumerate(LEVELS):
        hdr[i + 1].markdown(f"**{lvl}**")
    new_team = {}
    for sid, cap in steady.items():
        ps = model["per_skill"][sid]
        row = st.columns([2.4, 1, 1, 1, 1])
        steady_lbl = " · ".join(f"{lvl} {cap[lvl]}" for lvl in LEVELS if lvl in cap) or "—"
        row[0].markdown(f"**{ps['name']}**  \n<span style='color:#7A8A99;font-size:.74rem'>"
                        f"{ps.get('genus_category','')} · steady: {steady_lbl}</span>",
                        unsafe_allow_html=True)
        entry = {}
        for i, lvl in enumerate(LEVELS):
            if lvl in cap:
                v = row[i + 1].number_input(
                    f"{lvl} ≤{cap[lvl]}", min_value=0, max_value=int(cap[lvl]),
                    value=int(team0.get(sid, {}).get(lvl, cap[lvl])), step=1,
                    key=f"tc_{sid}_{lvl}_w", label_visibility="collapsed", disabled=disabled)
                entry[lvl] = int(v)
            else:
                row[i + 1].markdown("<div style='color:#B8C2CC;text-align:center;padding-top:6px'>—</div>",
                                    unsafe_allow_html=True)
        new_team[sid] = entry
    st.session_state["transition_team"] = new_team
    st.divider()

    # ── Compute + outputs ──
    res = compute_transition_cost(state, team=new_team, weeks=weeks, utilisation_pct=util,
                                  sdm_fte=sdm_fte)
    st.session_state["_transition_cost_res"] = res

    if res["total_cost"] <= 0 and res["total_hours"] > 0:
        callout("Transition <strong>hours/FTE</strong> are computed, but cost is ₹0 — resolve genus "
                "rates on the <strong>Rates &amp; Cost</strong> tab to price it.", "warning")

    k = st.columns(4)
    k[0].metric("Total transition hours", f"{res['total_hours']:,.0f}")
    k[1].metric("Total transition FTE", f"{res['total_fte']:.2f}")
    k[2].metric("Total transition cost", _inr(res["total_cost"]))
    k[3].metric("Duration", f"{int(res['weeks'])} wks")

    # By skill
    section_hdr("📊 Transition Effort & Cost by Skill")
    body = ""
    for sid, sp in res["per_skill"].items():
        team_lbl = " · ".join(f"{lvl} {sp['levels'][lvl]['seats']}" for lvl in LEVELS
                              if lvl in sp["levels"]) or "—"
        body += (f"<tr><td><strong>{sp['name']}</strong></td><td>{sp.get('genus_category','')}</td>"
                 f"<td>{team_lbl}</td><td class='r'>{sp['fte']:.2f}</td>"
                 f"<td class='r'>{sp['hours']:,.0f}</td><td class='r'>{_inr(sp['cost'])}</td></tr>")
    body += (f"<tr><td><strong>SDM</strong> <span style='color:#7A8A99'>(engagement)</span></td>"
             f"<td>—</td><td>{res['sdm']['fte']:.2f} FTE</td><td class='r'>{res['sdm']['fte']:.2f}</td>"
             f"<td class='r'>{res['sdm']['hours']:,.0f}</td><td class='r'>{_inr(res['sdm']['cost'])}</td></tr>")
    body += (f"<tr style='background:#EAF3F4;font-weight:700'><td>Total</td><td>—</td><td>—</td>"
             f"<td class='r'>{res['total_fte']:.2f}</td><td class='r'>{res['total_hours']:,.0f}</td>"
             f"<td class='r'>{_inr(res['total_cost'])}</td></tr>")
    st.markdown('<table class="styled-table"><thead><tr><th>Skill</th><th>Family</th>'
                '<th>Transition Team</th><th class="r">FTE</th><th class="r">Hours</th>'
                f'<th class="r">Cost</th></tr></thead><tbody>{body}</tbody></table>',
                unsafe_allow_html=True)

    # By level
    with st.expander("📈 Transition Effort & Cost by Level", expanded=False):
        lb = ""
        for lvl in LEVELS:
            d = res["by_level"][lvl]
            if d["seats"] <= 0:
                continue
            lb += (f"<tr><td><strong>{lvl}</strong></td><td class='r'>{d['seats']}</td>"
                   f"<td class='r'>{d['hours']:,.0f}</td><td class='r'>{_inr(d['cost'])}</td></tr>")
        lb += (f"<tr><td><strong>SDM</strong></td><td class='r'>{res['sdm']['fte']:.2f}</td>"
               f"<td class='r'>{res['sdm']['hours']:,.0f}</td><td class='r'>{_inr(res['sdm']['cost'])}</td></tr>")
        st.markdown('<table class="styled-table"><thead><tr><th>Level</th><th class="r">Seats</th>'
                    '<th class="r">Hours</th><th class="r">Cost</th></tr></thead>'
                    f'<tbody>{lb}</tbody></table>', unsafe_allow_html=True)

    # Export
    st.divider()
    if st.button("🚀 Prepare Transition Cost Excel", key="tcost_xlsx_prep", type="secondary"):
        from modules.outputs.transition_excel import build_transition_cost_workbook
        with st.spinner("Building transition cost…"):
            st.session_state["_tcost_xlsx"] = build_transition_cost_workbook(
                res, (st.session_state.get("project_name") or "").strip())
    if st.session_state.get("_tcost_xlsx"):
        from datetime import date as _date
        st.download_button(
            "⬇️ Download transition cost (.xlsx)", data=st.session_state["_tcost_xlsx"],
            file_name=f"transition_cost_{_date.today():%Y%m%d}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="tcost_xlsx_dl")


# ──────────────────────────────────────────────────────────────────────────────
# Overview KPI band — at-a-glance headline shown above the tabs (every screen)
# ──────────────────────────────────────────────────────────────────────────────
def _render_overview_strip():
    """Executive at-a-glance band above the tabs: the key commercial & delivery numbers,
    always visible so any persona can read the headline without opening a tab."""
    skills = st.session_state.get("skills", [])
    if not skills:
        return
    try:
        model = compute_multi_skill_model(_build_multi_state())
    except Exception:
        return
    pr = model.get("price_result", {}) or {}
    locked = _locked()
    approved = bool(st.session_state.get("ms_approved"))
    status = "🔒 Locked" if locked else ("✅ Approved" if approved else "✏️ Draft")
    c = st.columns(6)
    c[0].metric("Skills", f"{len(skills)}")
    c[1].metric("Total FTE", f"{float(model.get('total_fte', 0) or 0):.1f}")
    c[2].metric("Selling price / mo", _inr(pr.get("selling_price", 0)))
    c[3].metric("Gross margin", f"{float(pr.get('margin_pct', 0) or 0):.0f}%")
    _ts = st.session_state.get("transition_start")
    _gl = st.session_state.get("transition_go_live")
    if _ts and _gl and _gl > _ts:
        c[4].metric("Transition → Go-Live", f"{round((_gl - _ts).days / 7)} wks")
    else:
        c[4].metric("Gross profit / mo", _inr(pr.get("gross_profit", 0)))
    c[5].metric("Status", status)
    st.divider()


# ──────────────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────────────
def render_multi_skill_app():
    page_header(0, "Multi-skill Estimate",
                "Define skills, enter per-skill workload, review effort & FTE, price it, and optimise the team.")

    # ── Estimate identity (required to save/resume) — mirrors single-mode Step 1 ──
    proj = st.text_input(
        "Customer / RFP Name *", value=st.session_state.get("project_name", ""),
        key="ms_project_name_w", placeholder="e.g. Acme Corp — Infra RFP 2026",
        help="Every estimate is saved and resumed under this name. Your work autosaves once named.")
    st.session_state["project_name"] = proj
    if not proj.strip():
        callout("📝 <strong>Name this estimate</strong> (Customer / RFP) to autosave it and be "
                "able to resume later.", "info")
    else:
        st.caption(f"👤 Prepared by **{st.session_state.get('user_email', '')}** — autosaves as you go.")

    # ── Estimate-level Lock (read-only protection; calculations stay visible) ──
    locked = _locked()
    lk1, lk2 = st.columns([4.2, 1.3])
    if locked:
        lk1.markdown("<div style='background:#FBEED9;border-left:4px solid #B8860B;padding:8px 12px;"
                     "border-radius:4px;font-size:0.9rem'>🔒 <strong>Locked (read-only)</strong> — inputs "
                     "are protected from edits. Exports still work; <strong>Unlock</strong> to change "
                     "anything or submit for approval.</div>", unsafe_allow_html=True)
        if lk2.button("🔓 Unlock", key="ms_unlock", type="primary", use_container_width=True):
            st.session_state["ms_locked"] = False
            st.rerun()
        # Disable all value inputs (buttons, tab nav and downloads stay usable). Testids
        # verified against Streamlit 1.58 (see modules/inputs/identity_gate.py).
        st.markdown(
            "<style>"
            '[data-testid="stNumberInput"],[data-testid="stTextInput"],[data-testid="stTextArea"],'
            '[data-testid="stSelectbox"],[data-testid="stMultiSelect"],[data-testid="stCheckbox"],'
            '[data-testid="stRadio"],[data-testid="stToggle"],[data-testid="stFileUploader"],'
            '[data-testid="stSlider"],[data-testid="stDateInput"]'
            "{pointer-events:none!important;opacity:.55!important;}</style>", unsafe_allow_html=True)
    else:
        lk1.caption("Estimate is editable. Lock it to protect inputs from accidental changes "
                    "(calculations stay visible; exports still work).")
        if lk2.button("🔒 Lock estimate", key="ms_lock", type="secondary", use_container_width=True):
            st.session_state["ms_locked"] = True
            st.rerun()

    hc1, hc2, hc3 = st.columns([1.6, 1.6, 1.6])
    if hc1.button("← Switch to Single-skill mode", key="ms_to_single", type="secondary"):
        st.session_state["estimation_mode"] = "single"
        st.rerun()
    if hc3.button("🗒️ View feedback", key="ms_feedback_admin", type="secondary"):
        st.session_state["_show_feedback_admin"] = True
        st.rerun()
    # Orphan clean-up entry point — the sidebar (which hosts it in single mode) never
    # renders in multi, so surface it here when there are abandoned drafts to clean up.
    try:
        from modules.outputs.orphan_admin import orphan_count_cached
        _orphans = orphan_count_cached()
    except Exception:
        _orphans = 0
    if _orphans and hc2.button(f"🧹 Clean up drafts ({_orphans})", key="ms_orphan_admin",
                               type="secondary"):
        st.session_state["_show_orphan_admin"] = True
        st.rerun()
    _render_overview_strip()

    from modules.inputs.feedback_widget import render_feedback_widget
    _tabs_meta = [
        ("1 · Skills", _render_skill_setup), ("2 · Workload", _render_workload),
        ("3 · Effort & FTE", _render_dashboard), ("4 · Rates & Cost", _render_rates_cost),
        ("5 · Optimize (AI)", _render_optimize), ("6 · Approve & Export", _render_approve_export),
        ("7 · Versions & Compare", _render_versions_compare), ("8 · Transition", _render_transition),
        ("9 · Transition Cost", _render_transition_cost), ("10 · Shift Plan", _render_roster),
    ]
    for _i, (_tab, (_label, _fn)) in enumerate(zip(st.tabs([m[0] for m in _tabs_meta]), _tabs_meta)):
        with _tab:
            _fc = st.columns([6, 1])
            with _fc[1]:
                render_feedback_widget(f"Multi · {_label}", key=f"fb_ms_{_i}")
            _fn()
