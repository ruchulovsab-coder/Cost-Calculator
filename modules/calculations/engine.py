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
    For one category, return hours per role (L1/L2/L3).
    Each sublabel contributes: count × minutes / 60 × role_pct / 100
    """
    role_hours = {"L1": 0.0, "L2": 0.0, "L3": 0.0}
    for label, row in cat_data.items():
        total_h = (row.get("count", 0) * row.get("minutes", 0)) / 60.0
        for role in ("L1", "L2", "L3"):
            role_hours[role] += total_h * row.get(f"{role}_pct", 0.0) / 100.0
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
    manual_effort_per_server: float = 0,
    failure_rate_pct: float = 0,
    remediation_effort: float = 0,
) -> Dict[str, Any]:
    if not included:
        return {"hours": 0.0, "detail": "Not included"}
    if method == "Manual":
        hours = (num_servers * manual_effort_per_server) / 60.0
        return {
            "hours": hours,
            "servers": num_servers,
            "effort_per_server_min": manual_effort_per_server,
            "detail": f"{num_servers} servers × {manual_effort_per_server} min/server",
        }
    # Tool-Based
    failed = math.ceil(num_servers * (failure_rate_pct / 100.0))
    hours = (failed * remediation_effort) / 60.0
    return {
        "hours": hours,
        "servers": num_servers,
        "failed_servers": failed,
        "failure_rate_pct": failure_rate_pct,
        "remediation_effort_min": remediation_effort,
        "detail": f"⌈{num_servers} × {failure_rate_pct}%⌉ = {failed} failed × {remediation_effort} min",
    }


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
) -> Dict[str, Dict[str, Any]]:
    result = {}
    for role, fte_data in fte_result.items():
        fte = fte_data.get("final_fte", 0.0)
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
