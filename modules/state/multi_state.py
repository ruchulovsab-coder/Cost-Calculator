"""
Pure multi-skill model-state builder.

Extracted from the multi_skill UI module so non-UI code (session_manager.run_model,
the approval email artifacts, the Excel export, scenario compare) can compute the
multi-skill model without importing the Streamlit UI. Returns the plain state dict
consumed by engine.compute_multi_skill_model. See docs/multi-skill-parity.md.
"""
import copy

import streamlit as st

from config.settings import (ACTIVITY_FORMULAS, MS_CLASSIFICATIONS, MS_DEFAULT_DIST,
                             MS_DEFAULT_AHT, MS_DEFAULT_ROUTING)
from modules.calculations.engine import derive_activity_hours

_CAT_KEYS = ("alerts", "service_requests", "incidents", "changes")


def _class_row(cat: str, cls: str, count: float, minutes=None, split=None) -> dict:
    """A per-classification workload row seeded from defaults (minutes/split overridable)."""
    l1, l2, l3 = split if split is not None else MS_DEFAULT_ROUTING[cat].get(cls, (100, 0, 0))
    return {"count": round(count),
            "minutes": MS_DEFAULT_AHT[cat].get(cls, 0) if minutes is None else minutes,
            "L1_pct": l1, "L2_pct": l2, "L3_pct": l3}


def ensure_ms_workload(sk) -> dict:
    """Migrate/normalise a skill's workload to the per-classification model, in place.
    - Legacy `{'All': {...}}` rows are split across classifications by MS_DEFAULT_DIST,
      keeping the same AHT and L1/L2/L3 split so totals & routing are numerically
      UNCHANGED (safe migration; rounding remainder absorbed into the first class).
    - Classification-shaped categories just get any missing classes back-filled at 0.
    - Empty categories are left empty (no phantom volume)."""
    wl = sk.setdefault("workload", {})
    for cat in _CAT_KEYS:
        classes = MS_CLASSIFICATIONS[cat]
        rows = wl.get(cat) or {}
        if not rows:
            continue
        if "All" in rows:   # legacy single-bucket → distribute (numerically neutral)
            legacy = rows.get("All", {})
            total = float(legacy.get("count", 0) or 0)
            aht = float(legacy.get("minutes", 0) or 0)
            split = (float(legacy.get("L1_pct", 0) or 0), float(legacy.get("L2_pct", 0) or 0),
                     float(legacy.get("L3_pct", 0) or 0))
            new, assigned = {}, 0
            for cls in classes:
                c = round(total * MS_DEFAULT_DIST[cat].get(cls, 0) / 100.0)
                new[cls] = _class_row(cat, cls, c, minutes=aht, split=split)
                assigned += c
            if classes and assigned != round(total):   # keep the total exact
                new[classes[0]]["count"] += round(total) - assigned
            wl[cat] = new
        else:
            for cls in classes:
                rows.setdefault(cls, _class_row(cat, cls, 0))
    return sk


def skill_volumes(sk) -> dict:
    """This skill's monthly ticket counts (summed across classifications), for
    auto-deriving activity effort. Works for both the classification and legacy shapes."""
    wl = sk.get("workload", {}) or {}
    return {c: float(sum((r or {}).get("count", 0) or 0 for r in (wl.get(c, {}) or {}).values()))
            for c in _CAT_KEYS}


def _refresh_activities(skills):
    """Migrate workload to the classification model, then recompute 'auto' activity hours
    from each skill's volumes/servers, in place."""
    for sk in skills or []:
        ensure_ms_workload(sk)
        acts = sk.get("activities") or []
        if not acts:
            continue
        servers = int((sk.get("patching") or {}).get("num_servers", 0) or 0)
        vols = skill_volumes(sk)
        for a in acts:
            if a.get("auto") and a.get("name") in ACTIVITY_FORMULAS:
                a["hours"] = derive_activity_hours(a["name"], servers, vols)


def refresh_auto_activities():
    """Live-session refresh so numbers stay correct on tabs other than Workload
    (parity with single-mode refresh). Mutates the session's skills in place."""
    _refresh_activities(st.session_state.get("skills", []) or [])


def _assemble(g, skills) -> dict:
    """Build the engine state dict from a getter `g` (session_state.get or inputs.get)
    and an already-activity-refreshed `skills` list. Single source of truth so the
    live and stored-inputs builders stay in lock-step."""
    return {
        "skills": skills,
        "resource_sharing": g("resource_sharing", []) or [],
        "rates_by_category": g("ms_rates_by_category", {}) or {},   # InfraOps/CloudOps band rates (INR)
        "sdm_overhead_pct": float(g("sdm_overhead_pct", 5.0) or 0.0),
        "sdm_rate_inr": float(g("ms_sdm_rate_inr", 0.0) or 0.0),
        "exchange_rates": g("exchange_rates", {}) or {},
        # AI Team Optimizer realism knobs (default no-op); set on the Optimize tab.
        "context_switch_pct": float(g("ms_context_switch_pct", 0.0) or 0.0),
        "enforce_min_shift": bool(g("ms_enforce_min_shift", False)),
        "contingency_pct": float(g("contingency_pct", 10.0) or 0.0),
        "monthly_working_hours": float(g("monthly_working_hours", 160.0) or 160.0),
        "productive_utilisation": float(g("productive_utilisation", 75.0) or 75.0),
        "fte_basis": g("fte_basis", "rounded"),
        "delivery_country": g("delivery_country", "India"),
        "delivery_location": g("delivery_location"),
        "custom_hours_per_day": g("custom_hours_per_day", 8),
        "custom_days_per_week": g("custom_days_per_week", 5),
        "additional_costs": [], "sla_provision_included": "No", "sla_provision_pct": 0.0,
        "target_margin_pct": float(g("target_margin_pct", 20.0) or 0.0),
    }


def build_multi_model_state() -> dict:
    """Assemble the engine state from the live session. Keeps the engine pure/recalc-
    verifiable — all values come from session state, nothing is computed here beyond
    refreshing auto-derived activity hours."""
    refresh_auto_activities()
    return _assemble(st.session_state.get, st.session_state.get("skills", []) or [])


def build_multi_model_state_from(inputs: dict) -> dict:
    """Same as build_multi_model_state() but sourced from a stored inputs dict
    (scenario compare / saved-version recompute) rather than live session state.
    Works on a copy of the skills so the stored inputs are never mutated."""
    skills = copy.deepcopy(inputs.get("skills", []) or [])
    _refresh_activities(skills)
    return _assemble(inputs.get, skills)
