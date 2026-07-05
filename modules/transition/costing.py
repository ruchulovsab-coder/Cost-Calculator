"""Multi-skill transition COST — a separate priced line derived from a user-configured,
leaner transition team per skill × level (capped by the steady-state team) plus a shared SDM.

PURE / deterministic. Reuses the steady-state genus rates already resolved on Rates & Cost.
Kept OUT of `compute_multi_skill_model` — it never perturbs the monthly run-rate (FTE/cost/
price). Adapts automatically: the steady-state team, active levels and rates all come from the
current estimate, so adding skills / changing levels or coverage just flows through.
"""
from __future__ import annotations

from math import ceil
from typing import Any, Dict

from config.settings import TRANSITION_PARTICIPATION, TRANSITION_WEEKLY_HOURS
from modules.calculations.engine import compute_multi_skill_model

LEVELS = ("L1", "L2", "L3", "Architect")


def steady_state_seats(model: Dict[str, Any]) -> Dict[str, Dict[str, int]]:
    """Whole-person steady-state team per skill × level (⌈rounded FTE⌉), active levels only —
    this is the MAXIMUM allowable transition team for each skill."""
    out: Dict[str, Dict[str, int]] = {}
    for sid, ps in (model.get("per_skill", {}) or {}).items():
        fbl = ps.get("fte_by_level", {}) or {}
        seats = {}
        for lvl in LEVELS:
            f = float(fbl.get(lvl, 0) or 0)
            if f > 0:
                seats[lvl] = int(ceil(f))
        out[sid] = seats
    return out


def default_transition_seats(steady: Dict[str, Dict[str, int]]) -> Dict[str, Dict[str, int]]:
    """AMS-default transition team: senior-weighted % of the steady-state team, min 1 per active
    level, capped at the steady-state team. Users can override every value."""
    out: Dict[str, Dict[str, int]] = {}
    for sid, seats in steady.items():
        out[sid] = {lvl: max(1, min(mx, round(mx * TRANSITION_PARTICIPATION.get(lvl, 1.0))))
                    for lvl, mx in seats.items()}
    return out


def reconcile_team(team: Dict[str, Dict[str, int]],
                   steady: Dict[str, Dict[str, int]]) -> Dict[str, Dict[str, int]]:
    """Self-heal the saved config against the current steady-state team: seed missing skills/levels
    with the AMS default, cap every value at the steady-state seat count, and drop skills/levels that
    no longer exist. Keeps the config valid as the estimate changes."""
    defaults = default_transition_seats(steady)
    out: Dict[str, Dict[str, int]] = {}
    for sid, cap in steady.items():
        cur = (team or {}).get(sid, {}) or {}
        row = {}
        for lvl, mx in cap.items():                      # active levels only
            v = cur.get(lvl, defaults.get(sid, {}).get(lvl, mx))
            row[lvl] = int(max(0, min(int(v or 0), mx)))
        out[sid] = row
    return out


def compute_transition_cost(state: Dict[str, Any], *, team: Dict[str, Dict[str, int]],
                            weeks: float, utilisation_pct: float, sdm_fte: float,
                            weekly_hours: float = TRANSITION_WEEKLY_HOURS) -> Dict[str, Any]:
    """Transition cost breakdown. `team` = {skill_id: {level: seats}} (capped here defensively).

    hours(skill,level) = seats × weeks × weekly_hours × utilisation;  cost = hours × genus rate.
    SDM is a shared, independent effort: hours = sdm_fte × weeks × weekly_hours (at full allocation);
    cost = hours × SDM rate. Deterministic: same inputs → identical output.
    """
    model = compute_multi_skill_model({**state, "fte_basis": "rounded"})
    rates_by_cat = state.get("rates_by_category", {}) or {}
    sdm_rate = float(state.get("sdm_rate_inr", 0) or 0)
    weeks = max(0.0, float(weeks or 0))
    util = max(0.0, float(utilisation_pct or 0)) / 100.0
    wh = max(0.0, float(weekly_hours or 0))
    per_seat_hours = weeks * wh * util

    steady = steady_state_seats(model)
    per_skill: Dict[str, Any] = {}
    by_level = {lvl: {"seats": 0, "hours": 0.0, "cost": 0.0} for lvl in LEVELS}
    total_hours = total_cost = total_fte = 0.0

    for sid, ps in (model.get("per_skill", {}) or {}).items():
        cat = ps.get("genus_category")
        cfg = (team or {}).get(sid, {}) or {}
        cap = steady.get(sid, {})
        levels_out, s_hours, s_cost, s_seats = {}, 0.0, 0.0, 0
        for lvl in LEVELS:
            if lvl not in cap:                            # only active steady-state levels
                continue
            seats = int(min(int(cfg.get(lvl, 0) or 0), cap[lvl]))   # never exceed steady-state
            if seats <= 0:
                continue
            rate = float((rates_by_cat.get(cat, {}) or {}).get(lvl, 0) or 0)
            hrs = seats * per_seat_hours
            cost = hrs * rate
            levels_out[lvl] = {"seats": seats, "steady": cap[lvl], "rate_inr": rate,
                               "hours": hrs, "cost": cost, "fte": seats * util}
            s_hours += hrs; s_cost += cost; s_seats += seats
            by_level[lvl]["seats"] += seats
            by_level[lvl]["hours"] += hrs
            by_level[lvl]["cost"] += cost
        per_skill[sid] = {"name": ps.get("name") or sid, "genus_category": cat,
                          "levels": levels_out, "seats": s_seats, "hours": s_hours,
                          "cost": s_cost, "fte": s_seats * util}
        total_hours += s_hours; total_cost += s_cost; total_fte += s_seats * util

    sdm_fte = max(0.0, float(sdm_fte or 0))
    sdm_hours = sdm_fte * weeks * wh
    sdm_cost = sdm_hours * sdm_rate
    total_hours += sdm_hours; total_cost += sdm_cost; total_fte += sdm_fte

    return {
        "weeks": weeks, "utilisation_pct": float(utilisation_pct or 0), "weekly_hours": wh,
        "per_skill": per_skill, "by_level": by_level,
        "sdm": {"fte": sdm_fte, "hours": sdm_hours, "rate_inr": sdm_rate, "cost": sdm_cost},
        "total_hours": total_hours, "total_cost": total_cost, "total_fte": total_fte,
        "steady_seats": steady,
    }
