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
import json
import hashlib
from datetime import date
import streamlit as st
from config.settings import (
    CATEGORY_SUBLABELS, DEFAULT_VOLUME_DIST_PCT, DEFAULT_EFFORT_MINUTES,
    DEFAULT_RESOLUTION_PCT, ALL_ROLES, DEFAULT_CURRENCIES, TICKET_CATEGORIES,
    DEFAULT_ADDITIONAL_ACTIVITIES, DEFAULT_ROLE_BUFFER_PCT
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
            "L1_buffer": DEFAULT_ROLE_BUFFER_PCT,
            "L2_buffer": DEFAULT_ROLE_BUFFER_PCT,
            "L3_buffer": DEFAULT_ROLE_BUFFER_PCT,
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

        # ── Step 3: Patching (effort = min/server × servers) ──────────
        "patching_included":       "Yes",
        "num_servers":              20,
        "patching_method":          "Tool-Based",
        "manual_effort_per_server": 45.0,
        "auto_effort_per_server":   30.0,
        "patch_error_rate":         10.0,   # Tool-Based: % of servers needing manual effort

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

        # Transition & Onboarding Planner (phase/week resource grid). Empty until
        # enabled; the planner UI seeds default phases/roster on first enable.
        "transition_planner": {
            "enabled":             False,
            "total_weeks":         8,
            "phases":              [],   # [{id, name, weeks}]
            "resources":           [],   # [{id, role, count}]
            "allocation":          {},   # {resource_id: {week: utilisation}}
            "treatment":           "recurring",   # recurring | one_time | absorb
            "amortisation_months": 12,
        },

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
        "fte_basis":               "rounded",   # "rounded" (⌈0.5⌉) or "raw"

        # ── Project / estimate identity ───────────────────────────────
        "project_name": "",     # Customer / RFP name (required to proceed)
        "prepared_by":  "",     # Author / estimator

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
    
    from config.settings import ACTIVITY_FORMULAS
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
        # Backfill the auto flag: activities with a derivation formula default to
        # Auto (formula-driven), everything else to manual entry.
        if "auto" not in act:
            act["auto"] = act.get("name") in ACTIVITY_FORMULAS


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


# Per-page reset: (plain state keys to restore, exact widget keys to drop, widget-key prefixes to drop)
_STEP_RESET = {
    1: (["workload_totals", "alerts", "service_requests", "incidents", "changes",
         "coverage_model", "custom_hours_per_day", "custom_days_per_week",
         "delivery_country", "delivery_location"],
        ["total_alerts", "total_service_requests", "total_incidents", "total_changes",
         "coverage_model_w", "custom_hours_per_day_w", "custom_days_per_week_w",
         "dc_select", "dl_select"], []),
    2: (["alerts", "service_requests", "incidents", "changes"],
        [], ["alerts_", "service_requests_", "incidents_", "changes_"]),
    3: (["patching_included", "num_servers", "patching_method",
         "manual_effort_per_server", "auto_effort_per_server", "patch_error_rate", "patching_role"],
        ["patching_included_w", "num_servers_w", "patching_method_w",
         "manual_effort_per_server_w", "auto_effort_per_server_w", "patch_error_rate_w",
         "patching_role_w"], []),
    4: (["additional_activities"], [], ["act_"]),
    5: (["contingency_pct", "overhead_pcts"],
        ["contingency_pct_w", "overhead_architect", "overhead_sdm", "overhead_ssdm"], []),
    6: (["monthly_working_hours", "productive_utilisation"],
        ["monthly_working_hours_w", "productive_utilisation_w"], []),
    7: (["role_genus"], [], ["genus_"]),
    8: (["transition_included", "transition_total_cost", "transition_planner", "additional_costs",
         "sla_provision_included", "sla_provision_pct", "target_margin_pct",
         "reporting_currency", "exchange_rates", "fte_basis"],
        ["transition_included", "transition_total_cost_input", "sla_provision_included",
         "sla_provision_pct", "target_margin_pct", "reporting_currency", "fte_basis_w"],
        ["addcost_", "ac_p_", "ac_h_", "ac_r_", "fx_", "tp_"]),
}


def step_has_reset(step: int) -> bool:
    return step in _STEP_RESET


def reset_step(step: int):
    """Restore only this page's inputs to defaults (other pages untouched).
    Also drops the page's widget keys so the inputs visibly re-seed from defaults."""
    cfg = _STEP_RESET.get(step)
    if not cfg:
        return
    plain, widgets, prefixes = cfg
    initial = _get_initial_state()
    for k in plain:
        if k in initial:
            d = initial[k]
            st.session_state[k] = copy.deepcopy(d) if isinstance(d, (dict, list)) else d
    for wk in widgets:
        st.session_state.pop(wk, None)
    if prefixes:
        for k in [kk for kk in st.session_state.keys() if any(kk.startswith(p) for p in prefixes)]:
            st.session_state.pop(k, None)
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
            "L1_buffer": row.get("L1_buffer", DEFAULT_ROLE_BUFFER_PCT),
            "L2_buffer": row.get("L2_buffer", DEFAULT_ROLE_BUFFER_PCT),
            "L3_buffer": row.get("L3_buffer", DEFAULT_ROLE_BUFFER_PCT),
        }
    st.session_state[cat_key] = existing


# Keys consumed by the calculation pipeline (compute_full_model).
_MODEL_KEYS = [
    "alerts", "service_requests", "incidents", "changes",
    "patching_included", "num_servers", "patching_method",
    "manual_effort_per_server", "auto_effort_per_server", "patch_error_rate",
    "patching_role", "additional_activities", "contingency_pct", "overhead_pcts",
    "coverage_model", "custom_hours_per_day", "custom_days_per_week",
    "monthly_working_hours", "productive_utilisation", "role_genus",
    "additional_costs", "sla_provision_included", "sla_provision_pct",
    "target_margin_pct", "transition_total_cost", "transition_planner",
    "reporting_currency", "exchange_rates",
    "delivery_country", "delivery_location", "fte_basis",
]


def workload_volumes() -> dict:
    """Current ticket volumes used to derive activity defaults."""
    totals = st.session_state.get("workload_totals", {}) or {}
    return {
        "alerts":           totals.get("alerts", 0),
        "incidents":        totals.get("incidents", 0),
        "service_requests": totals.get("service_requests", 0),
        "changes":          totals.get("changes", 0),
    }


def refresh_auto_activity_hours():
    """Recompute hours for every additional activity still in Auto mode from the
    current server count and ticket volumes. Manual (Auto-off) rows are left as-is."""
    from config.settings import ACTIVITY_FORMULAS
    from modules.calculations.engine import derive_activity_hours
    servers = int(st.session_state.get("num_servers", 0) or 0)
    volumes = workload_volumes()
    for act in st.session_state.get("additional_activities", []) or []:
        if act.get("auto") and act.get("name") in ACTIVITY_FORMULAS:
            act["hours"] = round(derive_activity_hours(act["name"], servers, volumes), 1)


def build_model_state() -> dict:
    """
    Assemble the plain-dict state consumed by engine.compute_full_model from the
    live Streamlit session, resolving per-role INR rates from the uploaded rate
    card scoped to the selected delivery location. Single source of truth for
    every output (dashboard, exports, what-if).
    """
    from modules.calculations.engine import resolve_role_rates
    refresh_auto_activity_hours()  # keep Auto-derived activity hours current
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


@st.cache_data(show_spinner=False)
def _compute_cached(state: dict) -> dict:
    """Memoised pipeline. Cached on the (hashable) state dict so navigating back to
    the dashboard with unchanged inputs reuses the result instead of recomputing."""
    from modules.calculations.engine import compute_full_model
    return compute_full_model(state)


def run_model() -> dict:
    """Compute the full model from the current session. Result is read-only —
    do not mutate the returned dict (it may be a shared cached object)."""
    return _compute_cached(build_model_state())


# ── Change detection (divergence from the last saved version) ────────────────────
def inputs_fingerprint() -> str:
    """Stable hash of the inputs that affect the computed estimate (_MODEL_KEYS only,
    so navigation/UI-only state never registers as a change). Used to tell when the
    live estimate has changed since it was last saved or loaded."""
    snap = {k: st.session_state.get(k) for k in _MODEL_KEYS}
    return hashlib.sha256(
        json.dumps(snap, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def mark_saved_baseline():
    """Record the current inputs as the 'last saved' baseline — call right after a
    version is saved or loaded, so subsequent edits register as divergence."""
    st.session_state["_saved_fingerprint"] = inputs_fingerprint()


def inputs_changed_since_save() -> bool:
    """True when the live inputs differ from the recorded saved baseline. False when
    there is no baseline yet (unknown → never block)."""
    base = st.session_state.get("_saved_fingerprint")
    return base is not None and base != inputs_fingerprint()


def serialize_inputs() -> dict:
    """Snapshot all user inputs from session as a JSON-serialisable dict.
    Shared by scenario export and the cloud estimate store."""
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
    return inputs


def build_estimate_summary(model: dict) -> dict:
    """Headline figures stored alongside a saved estimate (for listings)."""
    return {
        "total_fte": round(model.get("total_fte", 0) or 0, 2),
        "delivery_cost": round(model.get("cost_result", {}).get("total_delivery_cost", 0) or 0, 0),
        "selling_price": round(model.get("price_result", {}).get("selling_price", 0) or 0, 0),
        "reporting_currency": model.get("reporting_currency", "INR"),
        "fte_basis": model.get("fte_basis", "rounded"),
    }


def export_scenario(name: str, description: str) -> dict:
    return {
        "meta": {"name": name, "description": description,
                 "date": str(date.today()), "version": "4.0"},
        "inputs": serialize_inputs(),
    }


def save_scenario_to_session(name: str, description: str) -> dict:
    """Capture the current inputs as a named scenario kept in-session, so it can be
    compared without round-tripping through a downloaded file."""
    scen = export_scenario(name, description)
    saved = st.session_state.setdefault("saved_scenarios", [])
    # Replace an existing scenario with the same name, else append.
    for i, s in enumerate(saved):
        if s.get("meta", {}).get("name") == name:
            saved[i] = scen
            break
    else:
        saved.append(scen)
    st.session_state["_last_scenario"] = scen
    return scen


def model_from_inputs(inputs: dict) -> dict:
    """Recompute the full model from a scenario's stored inputs (used by the
    comparison view). Rebuilds role rates from the stored rate card + location."""
    import pandas as pd
    from modules.calculations.engine import compute_full_model, resolve_role_rates
    state = dict(inputs)
    df = inputs.get("rate_card_df")
    if isinstance(df, list):
        df = pd.DataFrame(df) if df else None
    fx = inputs.get("exchange_rates", {}) or {}
    state["role_rates_inr"] = resolve_role_rates(
        df, inputs.get("role_genus", {}) or {},
        inputs.get("delivery_country"), inputs.get("delivery_location"), fx,
    )
    return compute_full_model(state)


def load_scenario(data: dict):
    import pandas as pd
    for key, val in data.get("inputs", {}).items():
        if key == "rate_card_df" and isinstance(val, list):
            st.session_state[key] = pd.DataFrame(val) if val else None
        elif key in _get_initial_state():
            st.session_state[key] = val
    sanitize_additional_activities()
    st.session_state["current_step"] = 9  # land on Results Dashboard
