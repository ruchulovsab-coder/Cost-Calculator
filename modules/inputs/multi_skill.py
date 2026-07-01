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

from config.settings import COVERAGE_MODELS, DEFAULT_ROLE_BUFFER_PCT, GRADE_ELIGIBILITY
from modules.inputs.steps_1_2 import section_hdr, callout, page_header
from modules.calculations.engine import compute_multi_skill_model, resolve_role_rates
from utils.formatters import fmt_hours

CATEGORIES = [("alerts", "Monitoring Alerts"), ("service_requests", "Service Requests"),
              ("incidents", "Incidents"), ("changes", "Change Requests")]
LEVELS = ["L1", "L2", "L3"]
BD_LEVELS = ["L1", "L2", "L3", "Architect"]   # buffered/breakdown levels, matches engine _MS_LEVELS
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
               "for this skill. Per-level **buffers** are configured on the **Effort & FTE** tab. "
               "(Per-severity detail, patching and activities come in later phases.)")
    wl = sk.setdefault("workload", {})

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
        # Buffers are applied by the engine from the skill's role_buffers (Effort & FTE tab),
        # so the workload rows carry only the raw volume/split.
        wl[cat_key] = {"All": {"count": cnt, "minutes": mins, "L1_pct": l1, "L2_pct": l2, "L3_pct": l3}}
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
        "rates_by_category": ss.get("ms_rates_by_category", {}) or {},   # InfraOps/CloudOps band rates (INR)
        "sdm_overhead_pct": float(ss.get("sdm_overhead_pct", 5.0) or 0.0),
        "sdm_rate_inr": float(ss.get("ms_sdm_rate_inr", 0.0) or 0.0),
        "exchange_rates": ss.get("exchange_rates", {}) or {},
        # AI Team Optimizer realism knobs (default no-op); set on the Optimize tab.
        "context_switch_pct": float(ss.get("ms_context_switch_pct", 0.0) or 0.0),
        "enforce_min_shift": bool(ss.get("ms_enforce_min_shift", False)),
        "contingency_pct": float(ss.get("contingency_pct", 10.0) or 0.0),
        "monthly_working_hours": float(ss.get("monthly_working_hours", 160.0) or 160.0),
        "productive_utilisation": float(ss.get("productive_utilisation", 75.0) or 75.0),
        "fte_basis": ss.get("fte_basis", "rounded"),
        "custom_hours_per_day": ss.get("custom_hours_per_day", 8),
        "custom_days_per_week": ss.get("custom_days_per_week", 5),
        "additional_costs": [], "sla_provision_included": "No", "sla_provision_pct": 0.0,
        "target_margin_pct": float(ss.get("target_margin_pct", 20.0) or 0.0),
    }


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

    def _table(title, kind, sdm_val):
        rows, col_tot, grand = _fte_matrix(model, names, kind)
        gtot = grand + sdm_val
        if sdm and sdm_val > 0:
            rows += (f"<tr><td>SDM <span style='color:#7A8A99'>(engagement)</span></td>"
                     f"<td class='r'>—</td><td class='r'>—</td><td class='r'>—</td><td class='r'>—</td>"
                     f"<td class='r'><strong>{sdm_val:.2f}</strong></td></tr>")
        tcells = "".join(f"<td class='r'><strong>{col_tot[lvl]:.2f}</strong></td>" for lvl in BD_LEVELS)
        rows += (f"<tr class='total-row'><td><strong>Grand total</strong></td>{tcells}"
                 f"<td class='r'><strong>{gtot:.2f}</strong></td></tr>")
        st.markdown(f"<div style='font-size:0.82rem;color:#1A5F6A;font-weight:600;margin:.4rem 0 .2rem'>{title}</div>",
                    unsafe_allow_html=True)
        st.markdown(
            f"""<table class="styled-table"><thead><tr>
            <th>Skill</th><th class="r">L1</th><th class="r">L2</th><th class="r">L3</th>
            <th class="r">Architect</th><th class="r">Total</th></tr></thead><tbody>{rows}</tbody></table>""",
            unsafe_allow_html=True)
        return gtot

    raw_grand = _table("Raw FTE (exact, pre-pooling)", "raw", sdm_raw)
    fin_grand = _table("Final FTE (delivered team, pooled-aware)", "final", sdm_final)

    g1, g2 = st.columns(2)
    g1.metric("Total Raw FTE", f"{raw_grand:.2f}")
    g2.metric("Total Final FTE (headcount)", f"{fin_grand:.1f}",
              help="Equals the engagement Total FTE (pooling applied where configured)")


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
        "SDM overhead % (one engagement SDM)", min_value=0.0, max_value=50.0, step=0.5,
        value=float(st.session_state.get("sdm_overhead_pct", 5.0) or 0.0), key="ms_sdm")

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


def _default_grade(band, available):
    """First eligible genus grade for a band that exists in the rate card, else first available."""
    for g in GRADE_ELIGIBILITY.get(band, []):
        if g in available:
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
            if fg.get(band) not in available:
                fg[band] = _default_grade(band, available)
    if st.session_state.get("ms_sdm_grade") not in available:
        st.session_state["ms_sdm_grade"] = _default_grade("SDM", available)

    section_hdr("🎓 Rate family → grade mapping")
    callout("Map each rate family (InfraOps / CloudOps) and band to a genus grade from the rate "
            "card; the hourly rate (converted to INR) is read from the card. A skill prices off its "
            "family's bands. <em>CloudOps defaults to the same grades as InfraOps until your rate "
            "card carries CLOUDOPS grades.</em>", "info")
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
    names = {s["id"]: (s.get("name") or s["id"]) for s in skills}

    # Per-skill monthly cost
    st.divider()
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

    # Engagement cost → price
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
    if a1.button("✅ Apply to estimate", key="ms_opt_apply", type="primary", disabled=not accepted_groups):
        st.session_state["resource_sharing"] = accepted_groups
        st.success(f"Applied {len(accepted_groups)} move(s) — Effort & Cost now reflect the leaner team.")
    if a2.button("↩ Reset", key="ms_opt_clear", disabled=not st.session_state.get("resource_sharing")):
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
# Entry point
# ──────────────────────────────────────────────────────────────────────────────
def render_multi_skill_app():
    page_header(0, "Multi-skill Estimate",
                "Define skills, enter per-skill workload, review effort & FTE, price it, and optimise the team.")
    if st.button("← Switch to Single-skill mode", key="ms_to_single", type="secondary"):
        st.session_state["estimation_mode"] = "single"
        st.rerun()
    t1, t2, t3, t4, t5 = st.tabs(["1 · Skills", "2 · Workload", "3 · Effort & FTE",
                                  "4 · Rates & Cost", "5 · Optimize (AI)"])
    with t1:
        _render_skill_setup()
    with t2:
        _render_workload()
    with t3:
        _render_dashboard()
    with t4:
        _render_rates_cost()
    with t5:
        _render_optimize()
