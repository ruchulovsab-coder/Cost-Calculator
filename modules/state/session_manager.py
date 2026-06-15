"""
Session state initialisation and scenario I/O.

New workload data model (v4):
Each category key (alerts, service_requests, incidents, changes) stores:
  {sublabel: {count: int, minutes: float, L1_pct: float, L2_pct: float, L3_pct: float}}

Total volume per category is stored as:
  workload_totals: {"alerts": int, "service_requests": int, "incidents": int, "changes": int}

This replaces the old split between session state volumes and a separate resolution_split dict.
"""
import copy
import math
from datetime import date
import streamlit as st
from config.settings import (
    CATEGORY_SUBLABELS, DEFAULT_VOLUME_DIST_PCT, DEFAULT_EFFORT_MINUTES,
    DEFAULT_RESOLUTION_PCT, ALL_ROLES, DEFAULT_CURRENCIES, TICKET_CATEGORIES,
    DEFAULT_ADDITIONAL_ACTIVITIES
)


def _build_workload_section(cat_key: str, total: int) -> dict:
    """
    Build the per-sublabel data structure for a workload category
    given a total volume. Applies all three sets of industry defaults.
    """
    sublabels   = CATEGORY_SUBLABELS[cat_key]
    dist_pct    = DEFAULT_VOLUME_DIST_PCT[cat_key]
    effort_mins = DEFAULT_EFFORT_MINUTES[cat_key]
    res_pct     = DEFAULT_RESOLUTION_PCT[cat_key]

    section = {}
    remaining = total
    for i, label in enumerate(sublabels):
        if i == len(sublabels) - 1:
            # last row gets the remainder to avoid rounding gaps
            count = remaining
        else:
            count = round(total * dist_pct[label] / 100)
            remaining -= count

        section[label] = {
            "dist_pct": float(dist_pct[label]),
            "count":    max(0, count),
            "minutes":  float(effort_mins[label]),
            "L1_pct":   float(res_pct[label]["L1"]),
            "L2_pct":   float(res_pct[label]["L2"]),
            "L3_pct":   float(res_pct[label]["L3"]),
        }
    return section


def _default_workload(cat_key: str) -> dict:
    """Zero-volume section with all defaults intact."""
    return _build_workload_section(cat_key, 0)


def _build_initial_state():
    """Build the initial state dict lazily to avoid Streamlit ScriptRunContext
    warnings that occur when module-level code accesses st internals at import time."""
    return {
        # ── Step 1 + 2: Total volumes (user enters these 4 numbers) ──
        "workload_totals": {
            "alerts":           100,
            "service_requests": 25,
            "incidents":        10,
            "changes":          8,
        },

        # ── Per-sublabel detail (auto-populated, user-editable) ───────
        "alerts":           _build_workload_section("alerts", 100),
        "service_requests": _build_workload_section("service_requests", 25),
        "incidents":        _build_workload_section("incidents", 10),
        "changes":          _build_workload_section("changes", 8),

        # ── Overhead roles % of total operational effort ──────────────
        "overhead_pcts": {"Architect": 5.0, "SDM": 5.0, "SSDM": 3.0},

        # ── Patching role assignment ───────────────────────────────────
        "patching_role": "L2",

        # ── Step 3: Patching ──────────────────────────────────────────
        "patching_included":       "Yes",
        "num_servers":              50,
        "patching_method":          "Tool-Based",
        "manual_effort_per_server": 30.0,
        "patch_failure_rate":       20.0,
        "patch_remediation_effort": 0.0,

        # ── Step 4: Additional Activities ────────────────────────────
        "additional_activities": copy.deepcopy(DEFAULT_ADDITIONAL_ACTIVITIES),

        # ── Step 5: Contingency ───────────────────────────────────────
        "contingency_pct": 10.0,

        # ── Step 6: Coverage & FTE ────────────────────────────────────
        "coverage_model":         None,
        "custom_hours_per_day":   8,
        "custom_days_per_week":   5,
        "monthly_working_hours":  160.0,
        "productive_utilisation": 75.0,

        # ── Step 7: Rate Card & Grade Mapping ─────────────────────────
        "rate_card_df":       None,
        "rate_card_currency": "INR",
        "delivery_country":   "India",
        "delivery_location":  None,
        "role_genus": {r: None for r in ALL_ROLES},

        # ── Step 8: Cost & Pricing (INR only) ─────────────────────────
        "exchange_rates":    {},
        "custom_currencies": [],

        "transition_included":            "No",
        "transition_total_cost":          0.0,
        "transition_amortisation_months": 12,

        "additional_costs": [
            {"name": "Shift Allowance",              "cost": 0.0, "custom": False},
            {"name": "On-Call Allowance",            "cost": 0.0, "custom": False},
            {"name": "Travel Expense",               "cost": 0.0, "custom": False},
            {"name": "Tools & Tooling Subscription", "cost": 0.0, "custom": False},
            {"name": "Software Licensing",           "cost": 0.0, "custom": False},
            {"name": "Training & Certifications",    "cost": 0.0, "custom": False},
            {"name": "Other Expense",                "cost": 0.0, "custom": False},
        ],

        "sla_provision_included": "No",
        "sla_provision_pct":       0.0,
        "target_margin_pct":       20.0,
        "reporting_currency":      "INR",

        # ── Navigation ────────────────────────────────────────────────
        "current_step": 1,

        # ── Scenario management ───────────────────────────────────────
        "saved_scenarios": [],
        "_last_scenario":   None,
    }


# Keep INITIAL_STATE as a module-level reference for backward compatibility
# (used by export_scenario, load_scenario, apply_total_volume).
# It is populated lazily on first access via init_session_state().
INITIAL_STATE = None


def _get_initial_state():
    """Return (and cache) the initial state dict."""
    global INITIAL_STATE
    if INITIAL_STATE is None:
        INITIAL_STATE = _build_initial_state()
    return INITIAL_STATE


def sanitize_additional_activities():
    """Ensure additional_activities in session state has all required dist fields (backward compatibility)."""
    if "additional_activities" not in st.session_state:
        return
    activities = st.session_state["additional_activities"]
    
    # Pre-defined default distributions for standard activities
    defaults = {
        "Scheduled Maintenance":          {"L1": 0.0, "L2": 70.0, "L3": 30.0, "Architect": 0.0, "SDM": 0.0, "SSDM": 0.0},
        "Root Cause Analysis (RCA)":      {"L1": 0.0, "L2": 20.0, "L3": 50.0, "Architect": 30.0, "SDM": 0.0, "SSDM": 0.0},
        "Problem Management":             {"L1": 0.0, "L2": 0.0, "L3": 70.0, "Architect": 20.0, "SDM": 10.0, "SSDM": 0.0},
        "Documentation & Knowledge Base": {"L1": 0.0, "L2": 20.0, "L3": 50.0, "Architect": 30.0, "SDM": 0.0, "SSDM": 0.0},
        "Service Review Preparation":     {"L1": 0.0, "L2": 40.0, "L3": 50.0, "Architect": 0.0, "SDM": 10.0, "SSDM": 0.0},
        "Other":                          {"L1": 0.0, "L2": 100.0, "L3": 0.0, "Architect": 0.0, "SDM": 0.0, "SSDM": 0.0},
    }
    
    for act in activities:
        if "dist" not in act or not isinstance(act["dist"], dict):
            name = act.get("name", "")
            if name in defaults:
                act["dist"] = copy.deepcopy(defaults[name])
            else:
                act["dist"] = {r: (100.0 if r == "L2" else 0.0) for r in ALL_ROLES}
        else:
            # Ensure all roles are present in the dictionary
            for r in ALL_ROLES:
                if r not in act["dist"]:
                    act["dist"][r] = 0.0


def init_session_state():
    for key, default in _get_initial_state().items():
        if key not in st.session_state:
            st.session_state[key] = (
                copy.deepcopy(default) if isinstance(default, (dict, list)) else default
            )
    sanitize_additional_activities()


def reset_all():
    for key, default in _get_initial_state().items():
        st.session_state[key] = (
            copy.deepcopy(default) if isinstance(default, (dict, list)) else default
        )
    sanitize_additional_activities()


def apply_total_volume(cat_key: str, new_total: int):
    """
    Called when the user changes the total volume for a category.
    Re-distributes counts using default percentages while preserving
    any manually edited minutes/resolution values the user has set.
    """
    sublabels = CATEGORY_SUBLABELS[cat_key]
    dist_pct  = DEFAULT_VOLUME_DIST_PCT[cat_key]
    existing  = st.session_state.get(cat_key, {})

    remaining = new_total
    for i, label in enumerate(sublabels):
        row = existing.get(label, {})
        # Recompute count from the stored dist_pct (user may have edited it)
        stored_dist = row.get("dist_pct", float(dist_pct[label]))
        if i == len(sublabels) - 1:
            count = remaining
        else:
            count = round(new_total * stored_dist / 100)
            remaining -= count

        existing[label] = {
            "dist_pct": stored_dist,
            "count":    max(0, count),
            "minutes":  row.get("minutes", DEFAULT_EFFORT_MINUTES[cat_key][label]),
            "L1_pct":   row.get("L1_pct",  DEFAULT_RESOLUTION_PCT[cat_key][label]["L1"]),
            "L2_pct":   row.get("L2_pct",  DEFAULT_RESOLUTION_PCT[cat_key][label]["L2"]),
            "L3_pct":   row.get("L3_pct",  DEFAULT_RESOLUTION_PCT[cat_key][label]["L3"]),
        }
    st.session_state[cat_key] = existing


# Keys consumed by the calculation pipeline (compute_full_model).
_MODEL_KEYS = [
    "alerts", "service_requests", "incidents", "changes",
    "patching_included", "num_servers", "patching_method",
    "manual_effort_per_server", "patch_failure_rate", "patch_remediation_effort",
    "patching_role", "additional_activities", "contingency_pct", "overhead_pcts",
    "coverage_model", "custom_hours_per_day", "custom_days_per_week",
    "monthly_working_hours", "productive_utilisation", "role_genus",
    "additional_costs", "sla_provision_included", "sla_provision_pct",
    "target_margin_pct", "transition_total_cost",
    "reporting_currency", "exchange_rates",
    "delivery_country", "delivery_location",
]


def build_model_state() -> dict:
    """
    Assemble the plain-dict state consumed by engine.compute_full_model from the
    live Streamlit session, resolving per-role INR rates from the uploaded rate
    card scoped to the selected delivery location. Single source of truth for
    every output (dashboard, exports, what-if).
    """
    from modules.calculations.engine import resolve_role_rates
    state = {k: st.session_state.get(k) for k in _MODEL_KEYS}
    exchange_rates = st.session_state.get("exchange_rates", {}) or {}
    state["role_rates_inr"] = resolve_role_rates(
        st.session_state.get("rate_card_df"),
        st.session_state.get("role_genus", {}) or {},
        st.session_state.get("delivery_country"),
        st.session_state.get("delivery_location"),
        exchange_rates,
    )
    return state


def export_scenario(name: str, description: str) -> dict:
    import pandas as pd
    keys = [k for k in _get_initial_state() if k not in ("saved_scenarios", "_last_scenario")]
    inputs = {}
    for k in keys:
        v = st.session_state.get(k)
        if isinstance(v, pd.DataFrame):
            inputs[k] = v.to_dict(orient="records")
        elif isinstance(v, (dict, list)):
            inputs[k] = copy.deepcopy(v)
        else:
            inputs[k] = v
    return {
        "meta": {"name": name, "description": description,
                 "date": str(date.today()), "version": "4.0"},
        "inputs": inputs,
    }


def load_scenario(data: dict):
    import pandas as pd
    for key, val in data.get("inputs", {}).items():
        if key == "rate_card_df" and isinstance(val, list):
            st.session_state[key] = pd.DataFrame(val) if val else None
        elif key in _get_initial_state():
            st.session_state[key] = val
    sanitize_additional_activities()
    st.session_state["current_step"] = 8
