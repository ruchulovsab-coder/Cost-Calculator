"""
Pure multi-skill model-state builder.

Extracted from the multi_skill UI module so non-UI code (session_manager.run_model,
the approval email artifacts, the Excel export, scenario compare) can compute the
multi-skill model without importing the Streamlit UI. Returns the plain state dict
consumed by engine.compute_multi_skill_model. See docs/multi-skill-parity.md.
"""
import copy

import streamlit as st

from config.settings import ACTIVITY_FORMULAS
from modules.calculations.engine import derive_activity_hours


def skill_volumes(sk) -> dict:
    """This skill's monthly ticket counts, for auto-deriving activity effort."""
    wl = sk.get("workload", {}) or {}
    return {c: float((wl.get(c, {}) or {}).get("All", {}).get("count", 0) or 0)
            for c in ("alerts", "service_requests", "incidents", "changes")}


def _refresh_activities(skills):
    """Recompute 'auto' activity hours from each skill's volumes/servers, in place."""
    for sk in skills or []:
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
