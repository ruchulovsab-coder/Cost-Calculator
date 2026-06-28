"""
Core calculation engine.
All functions are pure: (inputs) → outputs, zero side-effects.
Full 22-step processing order is implemented here.
"""
import math
from typing import Dict, Any, List, Optional, Tuple

# ─────────────────────────────────────────────────────────────────────────────
# STEP 1-4  Workload → Effort hours
# ─────────────────────────────────────────────────────────────────────────────

def calc_category_hours(cat_data: Dict[str, Dict]) -> Tuple[Dict[str, float], float]:
    """
    Compute per-sublabel effort hours and category total from the new data model.
    Each sublabel row: {count, minutes, L1_pct, L2_pct, L3_pct}
    Returns (per_sublabel_hours_dict, total_hours).
    """
    per_row: Dict[str, float] = {}
    total = 0.0
    for label, row in cat_data.items():
        h = (row.get("count", 0) * row.get("minutes", 0)) / 60.0
        per_row[label] = h
        total += h
    return per_row, total


def calc_category_role_hours(cat_data: Dict[str, Dict]) -> Dict[str, float]:
    """
    For one category, return buffered hours per role (L1/L2/L3).
    Each sublabel contributes, per role:
        count × minutes / 60 × role_pct / 100 × (1 + role_buffer% / 100)
    The per-row, per-role buffer defaults to DEFAULT_ROLE_BUFFER_PCT when absent.
    """
    from config.settings import DEFAULT_ROLE_BUFFER_PCT
    role_hours = {"L1": 0.0, "L2": 0.0, "L3": 0.0}
    for label, row in cat_data.items():
        total_h = (row.get("count", 0) * row.get("minutes", 0)) / 60.0
        for role in ("L1", "L2", "L3"):
            base = total_h * row.get(f"{role}_pct", 0.0) / 100.0
            buf = row.get(f"{role}_buffer", DEFAULT_ROLE_BUFFER_PCT)
            role_hours[role] += base * (1.0 + buf / 100.0)
    return role_hours


def calc_all_ticket_role_hours(
    alerts: Dict, service_requests: Dict, incidents: Dict, changes: Dict
) -> Dict[str, float]:
    """
    Aggregate L1/L2/L3 hours across all four ticket categories.
    Returns {"L1": hours, "L2": hours, "L3": hours}.
    """
    result = {"L1": 0.0, "L2": 0.0, "L3": 0.0}
    for cat_data in (alerts, service_requests, incidents, changes):
        for role, h in calc_category_role_hours(cat_data).items():
            result[role] += h
    return result


def validate_sublabel_row(row: Dict) -> Tuple[bool, str]:
    """Validate L1+L2+L3 pct sum = 100 and count >= 0."""
    pct_sum = row.get("L1_pct", 0) + row.get("L2_pct", 0) + row.get("L3_pct", 0)
    if abs(pct_sum - 100.0) > 0.5:
        return False, f"L1+L2+L3 = {pct_sum:.1f}% (must be 100%)"
    if row.get("count", 0) < 0:
        return False, "Count cannot be negative"
    return True, ""


def validate_category_counts(cat_data: Dict, declared_total: int) -> Tuple[bool, str]:
    """Validate sum of sublabel counts equals the declared total volume."""
    actual = sum(row.get("count", 0) for row in cat_data.values())
    if actual != declared_total:
        return False, f"Sub-counts sum to {actual:,}, declared total is {declared_total:,}"
    return True, ""


# STEP 5  Patching effort
# ─────────────────────────────────────────────────────────────────────────────

def calc_patching_effort(
    included: bool,
    num_servers: int,
    method: str,
    manual_effort_per_server: float = 45.0,
    auto_effort_per_server: float = 30.0,
    error_rate_pct: float = 0.0,
    **_legacy,
) -> Dict[str, Any]:
    """
    Patching effort (÷ 60 for hours):
      Manual      = num_servers × manual_effort_per_server
      Tool-Based  = failed_servers × auto_effort_per_server,
                    where failed_servers = round(num_servers × error_rate_pct / 100)
                    (the tool auto-handles the rest; only failures need manual effort).
    """
    if not included:
        return {"hours": 0.0, "detail": "Not included"}
    num_servers = num_servers or 0
    if method == "Manual":
        per = manual_effort_per_server
        hours = (num_servers * per) / 60.0
        return {
            "hours": hours, "servers": num_servers, "method": "Manual",
            "effort_per_server_min": per,
            "detail": f"{num_servers} servers × {per:.0f} min/server",
        }
    # Tool-Based: only the error-rate share of servers needs manual effort
    failed = round(num_servers * (error_rate_pct or 0) / 100.0)
    hours = (failed * auto_effort_per_server) / 60.0
    return {
        "hours": hours, "servers": num_servers, "method": "Tool-Based",
        "failed_servers": failed, "error_rate_pct": error_rate_pct,
        "effort_per_server_min": auto_effort_per_server,
        "detail": f"{failed} of {num_servers} servers ({error_rate_pct:.0f}% error) "
                  f"× {auto_effort_per_server:.0f} min/server",
    }


def derive_activity_hours(activity_name: str, servers: int, volumes: Dict[str, float]) -> float:
    """
    Recommended monthly effort (hours) for an auto-derived additional activity,
    using the per-unit-minute coefficients in config.ACTIVITY_FORMULAS.
      volumes : {"alerts", "incidents", "service_requests", "changes"}
    Returns 0.0 for activities without a defined formula.
    """
    from config.settings import ACTIVITY_FORMULAS
    cfg = ACTIVITY_FORMULAS.get(activity_name)
    if not cfg:
        return 0.0
    total_min = 0.0
    for driver, per_min in cfg["drivers"].items():
        qty = servers if driver == "servers" else volumes.get(driver, 0)
        total_min += (qty or 0) * per_min
    return total_min / 60.0


# ─────────────────────────────────────────────────────────────────────────────
# STEP 6  Resolution split → per-role hours
# ─────────────────────────────────────────────────────────────────────────────

def apply_resolution_split(category_avg_minutes, resolution_split):
    """Legacy shim — not used in v4. Use calc_all_ticket_role_hours instead."""
    return {"L1": 0.0, "L2": 0.0, "L3": 0.0}


def calc_overhead_hours(
    total_operational_hours: float,
    overhead_pcts: Dict[str, float],
) -> Dict[str, float]:
    """
    Architect/SDM/SSDM hours defined as % of total operational effort.
    E.g. {"Architect": 5, "SDM": 5, "SSDM": 3}
    """
    return {
        role: total_operational_hours * (pct / 100.0)
        for role, pct in overhead_pcts.items()
    }


# ─────────────────────────────────────────────────────────────────────────────
# STEP 8-9  Base effort, contingency, total effort
# ─────────────────────────────────────────────────────────────────────────────

def calc_base_effort(
    alert_hours: float,
    sr_hours: float,
    incident_hours: float,
    change_hours: float,
    patching_hours: float,
    additional_hours: float,
) -> Dict[str, float]:
    breakdown = {
        "Monitoring Alerts": alert_hours,
        "Service Requests":  sr_hours,
        "Incidents":         incident_hours,
        "Change Requests":   change_hours,
        "Patching":          patching_hours,
        "Additional Activities": additional_hours,
    }
    breakdown["Base Effort"] = sum(v for k, v in breakdown.items() if k != "Base Effort")
    return breakdown


def calc_contingency(base_effort: float, contingency_pct: float) -> Dict[str, float]:
    contingency_hours = base_effort * (contingency_pct / 100.0)
    return {
        "base_effort":        base_effort,
        "contingency_pct":    contingency_pct,
        "contingency_hours":  contingency_hours,
        "total_effort":       base_effort + contingency_hours,
    }


# ─────────────────────────────────────────────────────────────────────────────
# STEP 10  Assemble full role hours (resolution + overhead + patching share)
# ─────────────────────────────────────────────────────────────────────────────

def assemble_role_hours(
    ticket_role_hours: Dict[str, float],   # L1/L2/L3 from resolution split
    overhead_role_hours: Dict[str, float], # Architect/SDM/SSDM
    patching_hours: float,
    patching_role: str,                    # which role handles patching (e.g. "L2")
    additional_activities: List[Dict],     # All additional activities with hours and role distributions
    contingency_pct: float                 # Contingency buffer percentage
) -> Dict[str, float]:
    """
    Combine all sources into a single role → hours map.
    Patching effort is assigned to a single designated role.
    Additional activities are distributed based on their explicit role percentage distributions.
    Contingency is applied to all base operational hours before adding overhead.
    """
    from config.settings import ALL_ROLES
    result = {r: 0.0 for r in ALL_ROLES}
    
    # 1. Distribute additional hours based on each activity's explicit distribution
    add_dist = {r: 0.0 for r in ALL_ROLES}
    if additional_activities:
        for act in additional_activities:
            act_hours = act.get("hours", 0.0)
            dist = act.get("dist", {})
            if act_hours > 0:
                for role in ALL_ROLES:
                    pct = dist.get(role, 0.0)
                    add_dist[role] += act_hours * (pct / 100.0)

    # 2. Accumulate base operational hours for each role
    base_ops = {r: 0.0 for r in ALL_ROLES}
    for role, hours in ticket_role_hours.items():
        base_ops[role] = base_ops.get(role, 0.0) + hours
    
    for role, hours in add_dist.items():
        base_ops[role] = base_ops.get(role, 0.0) + hours
        
    base_ops[patching_role] = base_ops.get(patching_role, 0.0) + patching_hours

    # 3. Apply contingency to all operational base hours
    cont_multiplier = 1.0 + (contingency_pct / 100.0)
    for role in ALL_ROLES:
        result[role] = base_ops[role] * cont_multiplier

    # 4. Add overhead (already calculated as % of total operational effort)
    for role, hours in overhead_role_hours.items():
        result[role] = result.get(role, 0.0) + hours
        
    return result



# ─────────────────────────────────────────────────────────────────────────────
# STEP 11  FTE calculation
# ─────────────────────────────────────────────────────────────────────────────

def ceil_half(value: float) -> float:
    """Ceiling to nearest 0.5."""
    return math.ceil(value * 2) / 2


def calc_productive_hours(monthly_working_hours: float, utilisation_pct: float) -> float:
    return monthly_working_hours * (utilisation_pct / 100.0)


def calc_coverage_multiplier(
    model: str,
    custom_hours_per_day: float = 8,
    custom_days_per_week: float = 5,
) -> float:
    from config.settings import COVERAGE_MODELS
    if model == "Custom":
        weekly = custom_hours_per_day * custom_days_per_week
    else:
        cfg = COVERAGE_MODELS.get(model, COVERAGE_MODELS["8×5"])
        weekly = cfg["weekly_hours"]
    return weekly / 40.0


def calc_fte(
    role_hours: Dict[str, float],
    productive_hours: float,
    coverage_multiplier: float,
) -> Dict[str, Dict[str, Any]]:
    """
    FTE per role.
    Coverage multiplier → L1, L2 only.
    Minimum FTE 0.5 for any role with hours > 0.
    Both raw and final FTE retained for dashboard transparency.
    """
    from config.settings import COVERAGE_APPLICABLE_ROLES
    result = {}
    for role, hours in role_hours.items():
        if hours <= 0:
            result[role] = {"hours": 0.0, "raw_fte": 0.0, "final_fte": 0.0, "coverage_applied": False}
            continue
        raw = hours / productive_hours if productive_hours > 0 else 0.0
        cov = role in COVERAGE_APPLICABLE_ROLES
        adjusted = raw * coverage_multiplier if cov else raw
        final = max(ceil_half(adjusted), 0.5)
        result[role] = {
            "hours": hours,
            "raw_fte": adjusted,
            "final_fte": final,
            "coverage_applied": cov,
        }
    return result


# ─────────────────────────────────────────────────────────────────────────────
# STEP 12-14  Cost calculation
# ─────────────────────────────────────────────────────────────────────────────

def convert_rate_to_inr(rate: float, rate_currency: str, exchange_rates: Dict[str, float]) -> float:
    if not rate_currency or str(rate_currency).strip().upper() in ["NONE", "NAN", ""]:
        rate_currency = "INR"
    if rate_currency == "INR":
        return rate
    fx = exchange_rates.get(rate_currency)
    if fx and fx > 0:
        return rate * fx
    raise ValueError(f"No exchange rate found for currency '{rate_currency}'. Please enter it in Step 8.")


def calc_resource_cost(
    fte_result: Dict[str, Dict[str, Any]],
    monthly_working_hours: float,
    role_rates_inr: Dict[str, float],
    role_genus: Dict[str, Optional[str]],
    fte_key: str = "final_fte",
) -> Dict[str, Dict[str, Any]]:
    """fte_key selects the staffing basis used for billing: 'final_fte' (rounded
    to 0.5) or 'raw_fte' (un-rounded)."""
    result = {}
    for role, fte_data in fte_result.items():
        fte = fte_data.get(fte_key, 0.0)
        billed_hours = fte * monthly_working_hours
        rate = role_rates_inr.get(role, 0.0)
        cost = billed_hours * rate if (fte > 0 and rate > 0) else 0.0
        result[role] = {
            "fte": fte,
            "billed_hours": billed_hours,
            "rate_inr": rate,
            "genus": role_genus.get(role),
            "cost_inr": cost,
        }
    return result


def calc_total_delivery_cost(
    resource_cost_inr: float,
    transition_cost_inr: float,
    additional_expenses_inr: float,
    sla_provision_pct: float,
) -> Dict[str, float]:
    subtotal = resource_cost_inr + transition_cost_inr + additional_expenses_inr
    sla_amount = subtotal * (sla_provision_pct / 100.0)
    total = subtotal + sla_amount
    return {
        "resource_cost":        resource_cost_inr,
        "transition_cost":      transition_cost_inr,
        "additional_expenses":  additional_expenses_inr,
        "subtotal_before_sla":  subtotal,
        "sla_provision":        sla_amount,
        "total_delivery_cost":  total,
    }


# ─────────────────────────────────────────────────────────────────────────────
# STEP 15  Selling price
# ─────────────────────────────────────────────────────────────────────────────

def calc_selling_price(total_delivery_cost_inr: float, margin_pct: float) -> Dict[str, float]:
    if margin_pct >= 100:
        raise ValueError("Margin cannot be 100% or greater.")
    selling_price = total_delivery_cost_inr / (1.0 - margin_pct / 100.0)
    gross_profit  = selling_price - total_delivery_cost_inr
    return {
        "total_delivery_cost": total_delivery_cost_inr,
        "margin_pct":          margin_pct,
        "selling_price":       selling_price,
        "gross_profit":        gross_profit,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Transition & Onboarding planner cost
#   Weekly cost per resource = count × utilisation × weekly_hours × hourly_rate.
#   Reuses the same Genus INR rates as the monthly model — no separate costing.
# ─────────────────────────────────────────────────────────────────────────────

def transition_week_phase_map(phases: List[Dict], total_weeks: int) -> Dict[int, str]:
    """Map each 1-based week number to its phase name, allocating weeks to phases
    sequentially in configured order. Weeks past the configured phases map to None."""
    mapping: Dict[int, str] = {}
    week = 1
    for ph in phases or []:
        n = int(ph.get("weeks", 0) or 0)
        for _ in range(n):
            if total_weeks and week > total_weeks:
                break
            mapping[week] = ph.get("name", "")
            week += 1
    return mapping


def calc_transition_cost(
    planner: Optional[Dict[str, Any]],
    role_rates_inr: Dict[str, float],
    weekly_hours: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Compute the Transition & Onboarding cost from the planner config.

    planner = {
      enabled: bool, total_weeks: int,
      phases: [{name, weeks}], resources: [{id, role, count}],
      allocation: {resource_id: {week: utilisation}},   # week keys int or str
      treatment: "recurring"|"one_time"|"absorb", amortisation_months: int,
    }
    Per (resource, week):  count × utilisation × weekly_hours × hourly_rate_inr[role].
    Returns the total, per-resource / per-phase breakdowns, and the commercial
    figures (monthly recurring, one-time fee, absorbed, net charged).
    """
    if weekly_hours is None:
        from config.settings import TRANSITION_WEEKLY_HOURS
        weekly_hours = TRANSITION_WEEKLY_HOURS

    out: Dict[str, Any] = {
        "enabled": False, "total": 0.0, "weekly_hours": weekly_hours,
        "treatment": "one_time", "amortisation_months": 12,
        "monthly_recurring": 0.0, "one_time_fee": 0.0, "absorbed": 0.0,
        "net_charged": 0.0, "per_resource": [], "per_phase": {}, "total_weeks": 0,
    }
    if not planner or not planner.get("enabled"):
        return out

    total_weeks = int(planner.get("total_weeks", 0) or 0)
    phases = planner.get("phases", []) or []
    resources = planner.get("resources", []) or []
    allocation = planner.get("allocation", {}) or {}
    rates = role_rates_inr or {}
    week_phase = transition_week_phase_map(phases, total_weeks)

    per_phase: Dict[str, float] = {}
    per_resource: List[Dict[str, Any]] = []
    total = 0.0
    for res in resources:
        rid = str(res.get("id", ""))
        role = res.get("role")
        count = float(res.get("count", 0) or 0)
        rate = float(rates.get(role, 0.0) or 0.0)
        # allocation may be keyed by the str(id) (JSON round-trip) or the raw id
        alloc = allocation.get(rid) or allocation.get(res.get("id")) or {}
        r_hours = 0.0
        r_cost = 0.0
        for wk, util in alloc.items():
            try:
                w = int(wk)
            except (TypeError, ValueError):
                continue
            if w < 1 or (total_weeks and w > total_weeks):
                continue
            u = float(util or 0)
            if u <= 0 or count <= 0:
                continue
            hours = count * u * weekly_hours
            cost = hours * rate
            r_hours += hours
            r_cost += cost
            ph = week_phase.get(w)
            if ph:
                per_phase[ph] = per_phase.get(ph, 0.0) + cost
        total += r_cost
        per_resource.append({
            "id": rid, "role": role, "count": count,
            "hours": r_hours, "rate_inr": rate, "cost": r_cost,
        })

    treatment = planner.get("treatment", "one_time") or "one_time"
    months = max(int(planner.get("amortisation_months", 12) or 12), 1)
    out.update({
        "enabled": True, "total": total, "treatment": treatment,
        "amortisation_months": months, "per_resource": per_resource,
        "per_phase": per_phase, "total_weeks": total_weeks,
    })
    if treatment == "recurring":
        out["monthly_recurring"] = total / months
        out["net_charged"] = total
    elif treatment == "absorb":
        out["absorbed"] = total
        out["net_charged"] = 0.0
    else:  # one_time
        out["one_time_fee"] = total
        out["net_charged"] = total
    return out


# ─────────────────────────────────────────────────────────────────────────────
# STEP 16  Currency conversion
# ─────────────────────────────────────────────────────────────────────────────

def convert_to_currency(value_inr: float, target_currency: str, exchange_rates: Dict[str, float]) -> float:
    if target_currency == "INR":
        return value_inr
    rate = exchange_rates.get(target_currency)
    if rate and rate > 0:
        return value_inr / rate
    return value_inr


def build_exchange_rates(
    base_rates: Dict[str, Optional[float]],
    custom_currencies: List[Dict],
) -> Dict[str, float]:
    rates = {}
    for currency, rate in base_rates.items():
        if rate and rate > 0:
            rates[currency] = float(rate)
    for entry in custom_currencies:
        code = entry.get("code", "").strip().upper()
        rate = entry.get("rate", 0)
        if code and rate and float(rate) > 0:
            rates[code] = float(rate)
    return rates


# ─────────────────────────────────────────────────────────────────────────────
# Validation helpers
# ─────────────────────────────────────────────────────────────────────────────

def validate_resolution_split(split, category_totals):
    """Legacy shim — not used in v4."""
    return {}


def validate_overhead_pcts(overhead_pcts: Dict[str, float]) -> Tuple[float, bool, str]:
    total = sum(overhead_pcts.values())
    # Overhead can be any value; we just warn if > 30%
    if total > 30:
        return total, True, f"⚠️ Overhead roles sum to {total:.1f}% — unusually high."
    return total, True, ""


# ─────────────────────────────────────────────────────────────────────────────
# Rate-card resolution (genus → hourly rate) — centralised here so the dashboard
# and Step 7 agree. Honours the selected delivery location instead of hardcoding
# India. pandas is imported lazily to keep the rest of the engine dependency-free.
# ─────────────────────────────────────────────────────────────────────────────

def filter_rate_card(df, country: Optional[str] = None, location: Optional[str] = None):
    """
    Return the subset of the rate card for the given country/location.
    Columns are assumed lower-cased ('country', 'location', 'genus', 'hourly rate',
    'rate currency'). If a filter yields no rows it is ignored (graceful fallback).
    """
    if df is None or len(df) == 0:
        return df
    out = df
    if country:
        sub = out[out["country"].astype(str).str.strip().str.lower() == country.strip().lower()]
        if len(sub) > 0:
            out = sub
    if location:
        sub = out[out["location"].astype(str).str.strip().str.lower() == location.strip().lower()]
        if len(sub) > 0:
            out = sub
    return out


def resolve_role_rates(
    df,
    role_genus: Dict[str, Optional[str]],
    country: Optional[str] = None,
    location: Optional[str] = None,
    exchange_rates: Optional[Dict[str, float]] = None,
) -> Dict[str, float]:
    """
    Map each role's selected genus to an hourly rate (converted to INR) from the
    rate card, scoped to the selected country/location. Returns {role: rate_inr}.
    Roles with no genus or no matching row are omitted.
    """
    if df is None or len(df) == 0:
        return {}
    exchange_rates = exchange_rates or {}
    scoped = filter_rate_card(df, country, location)
    rates: Dict[str, float] = {}
    for role, genus in (role_genus or {}).items():
        if not genus:
            continue
        row = scoped[scoped["genus"] == genus]
        if len(row) == 0:
            continue
        raw = float(row.iloc[0]["hourly rate"])
        currency = row.iloc[0].get("rate currency", "INR") if hasattr(row.iloc[0], "get") else "INR"
        try:
            rates[role] = convert_rate_to_inr(raw, currency, exchange_rates)
        except ValueError:
            # Unknown FX for this card row — fall back to raw value so the model
            # still produces a number; the UI surfaces missing-FX warnings.
            rates[role] = raw
    return rates


# ─────────────────────────────────────────────────────────────────────────────
# Unified pipeline — single source of truth for the whole calculation.
# Pure: (state dict) → (results dict), no Streamlit, no side effects.
# Every consumer (dashboard, Excel/PDF export, what-if sliders, tests) calls this
# so displayed and exported numbers can never drift apart.
# ─────────────────────────────────────────────────────────────────────────────

def compute_full_model(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the entire effort → FTE → cost → price pipeline from a plain state dict.

    Expected keys (all optional, sensible defaults applied):
      alerts, service_requests, incidents, changes : workload sublabel dicts
      patching_included ("Yes"/"No"), num_servers, patching_method,
      manual_effort_per_server, patch_failure_rate, patch_remediation_effort,
      patching_role
      additional_activities : list of {hours, dist}
      contingency_pct, overhead_pcts
      coverage_model, custom_hours_per_day, custom_days_per_week,
      monthly_working_hours, productive_utilisation
      role_rates_inr : {role: inr_rate}  (pre-resolved from the rate card)
      role_genus : {role: genus}
      additional_costs : list of {cost}
      sla_provision_included ("Yes"/"No"), sla_provision_pct
      target_margin_pct
      reporting_currency, exchange_rates
    """
    g = state.get

    # 1. Ticket effort per category
    _, alert_h = calc_category_hours(g("alerts", {}) or {})
    _, sr_h    = calc_category_hours(g("service_requests", {}) or {})
    _, inc_h   = calc_category_hours(g("incidents", {}) or {})
    _, chg_h   = calc_category_hours(g("changes", {}) or {})

    # 2. Patching
    patching = calc_patching_effort(
        g("patching_included") == "Yes",
        g("num_servers", 0) or 0,
        g("patching_method") or "Manual",
        g("manual_effort_per_server", 45) or 45,
        g("auto_effort_per_server", 30) or 30,
        error_rate_pct=g("patch_error_rate", 0) or 0,
    )
    patch_h = patching["hours"]

    # 3. Additional activities
    additional_activities = g("additional_activities", []) or []
    add_h = sum(a.get("hours", 0.0) for a in additional_activities)

    # 4. Base effort + contingency
    breakdown = calc_base_effort(alert_h, sr_h, inc_h, chg_h, patch_h, add_h)
    base_effort = breakdown["Base Effort"]
    contingency_pct = float(g("contingency_pct", 0.0) or 0.0)
    cont = calc_contingency(base_effort, contingency_pct)
    total_effort = cont["total_effort"]

    # 5. Role hours (resolution split + overhead + patching share + contingency)
    ticket_role_hours = calc_all_ticket_role_hours(
        g("alerts", {}) or {}, g("service_requests", {}) or {},
        g("incidents", {}) or {}, g("changes", {}) or {},
    )
    overhead_pcts = g("overhead_pcts", {}) or {}
    overhead_role_hours = calc_overhead_hours(total_effort, overhead_pcts)
    role_hours = assemble_role_hours(
        ticket_role_hours, overhead_role_hours, patch_h,
        g("patching_role", "L2") or "L2",
        additional_activities, contingency_pct,
    )

    # 6. FTE
    multiplier = calc_coverage_multiplier(
        g("coverage_model") or "8×5",
        g("custom_hours_per_day", 8) or 8,
        g("custom_days_per_week", 5) or 5,
    )
    monthly_working_hours = float(g("monthly_working_hours", 160.0) or 160.0)
    utilisation = float(g("productive_utilisation", 75.0) or 75.0)
    productive_hrs = calc_productive_hours(monthly_working_hours, utilisation)
    fte_result = calc_fte(role_hours, productive_hrs, multiplier)

    # FTE basis for costing/display: rounded (⌈0.5⌉) or raw
    fte_basis = (g("fte_basis", "rounded") or "rounded").lower()
    fte_key = "raw_fte" if fte_basis == "raw" else "final_fte"
    total_fte = sum(v[fte_key] for v in fte_result.values())
    total_fte_raw = sum(v["raw_fte"] for v in fte_result.values())
    total_fte_final = sum(v["final_fte"] for v in fte_result.values())

    # 7. Resource cost (billed on the chosen FTE basis)
    role_rates_inr = g("role_rates_inr", {}) or {}
    role_genus = g("role_genus", {}) or {}
    resource_costs = calc_resource_cost(fte_result, monthly_working_hours, role_rates_inr, role_genus, fte_key=fte_key)
    total_resource_cost = sum(v["cost_inr"] for v in resource_costs.values())

    # 8. Delivery cost + price (transition is one-time, excluded from monthly)
    additional_costs = g("additional_costs", []) or []
    total_additional = sum(c.get("cost", 0.0) for c in additional_costs)
    sla_pct = float(g("sla_provision_pct", 0.0) or 0.0) if g("sla_provision_included") == "Yes" else 0.0
    cost_result = calc_total_delivery_cost(total_resource_cost, 0.0, total_additional, sla_pct)
    margin = float(g("target_margin_pct", 0.0) or 0.0)
    price_result = calc_selling_price(cost_result["total_delivery_cost"], margin)

    # 8b. Transition & Onboarding — calculated from the planner, applied to the
    # PRICE post-margin (never marked up). Recurring adds total/months to the
    # monthly price; one-time is a separate line; absorb nets it to zero.
    transition = calc_transition_cost(g("transition_planner"), role_rates_inr)
    if transition["enabled"]:
        transition_cost_legacy = transition["one_time_fee"]   # >0 only for one-time
    else:
        transition_cost_legacy = float(g("transition_total_cost", 0.0) or 0.0)
    monthly_price_with_transition = price_result["selling_price"] + transition["monthly_recurring"]

    # 9. Currency conversion of headline figures
    reporting_currency = g("reporting_currency", "INR") or "INR"
    exchange_rates = g("exchange_rates", {}) or {}
    fx = dict(exchange_rates); fx.setdefault("INR", 1.0)
    def _conv(v): return convert_to_currency(v, reporting_currency, fx)

    return {
        "effort_sources": {
            "Monitoring Alerts": alert_h, "Service Requests": sr_h,
            "Incidents": inc_h, "Change Requests": chg_h,
            "Patching": patch_h, "Additional Activities": add_h,
            "Contingency": cont["contingency_hours"],
        },
        "patching": patching,
        "base_effort": base_effort,
        "contingency": cont,
        "total_effort": total_effort,
        "ticket_role_hours": ticket_role_hours,
        "overhead_role_hours": overhead_role_hours,
        "role_hours": role_hours,
        "coverage_multiplier": multiplier,
        "productive_hours": productive_hrs,
        "fte_result": fte_result,
        "fte_basis": fte_basis,
        "total_fte": total_fte,
        "total_fte_raw": total_fte_raw,
        "total_fte_final": total_fte_final,
        "resource_costs": resource_costs,
        "total_resource_cost": total_resource_cost,
        "cost_result": cost_result,
        "price_result": price_result,
        "reporting_currency": reporting_currency,
        "selling_price_converted": _conv(price_result["selling_price"]),
        "delivery_cost_converted": _conv(cost_result["total_delivery_cost"]),
        "transition": transition,
        "monthly_price_with_transition": monthly_price_with_transition,
        "monthly_price_with_transition_converted": _conv(monthly_price_with_transition),
        "transition_cost": transition_cost_legacy,
        "transition_cost_converted": _conv(transition_cost_legacy),
    }
