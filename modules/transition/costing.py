"""Multi-skill transition COST — a separate priced line built from a per-phase × per-skill × per-level
FRACTIONAL resource allocation (0.25 = 25% of one resource), plus a shared engagement SDM.

Mirrors the reference framework (per-skill blocks, roles as rows, time as columns) but uses the
Transition Strategy's PHASES as the columns. PURE / deterministic. Reuses the steady-state genus rates.
Kept OUT of `compute_multi_skill_model` — it never perturbs the monthly run-rate.

Effort(skill, level) = Σ_phase  resource[phase] × phase_weeks × weekly_hours.
Cost = effort × genus rate.  Selling = cost / (1 − margin).  SDM is one engagement row.
"""
from __future__ import annotations

from math import ceil
from typing import Any, Dict, List

from config.settings import (TRANSITION_PARTICIPATION, TRANSITION_PHASE_UTILISATION,
                             TRANSITION_WEEKLY_HOURS)
from modules.calculations.engine import compute_multi_skill_model

LEVELS = ("L1", "L2", "L3", "Architect")


def _quarter(x: float) -> float:
    """Round to the nearest 0.25 (the input granularity)."""
    return round(float(x) * 4) / 4.0


def steady_state_seats(model: Dict[str, Any]) -> Dict[str, Dict[str, int]]:
    """Whole-person steady-state team per skill × level (⌈rounded FTE⌉), active levels only —
    the MAXIMUM allowable transition resource per level (per phase)."""
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


def default_allocation(steady: Dict[str, Dict[str, int]],
                       phase_keys: List[str]) -> Dict[str, Dict[str, Dict[str, float]]]:
    """AMS-default per-phase allocation: senior-weighted participation × the phase's default
    utilisation, rounded to 0.25 and capped at the steady-state seats. Editable everywhere."""
    out: Dict[str, Dict[str, Dict[str, float]]] = {}
    for sid, seats in steady.items():
        out[sid] = {}
        for lvl, mx in seats.items():
            factor = TRANSITION_PARTICIPATION.get(lvl, 1.0)
            out[sid][lvl] = {pk: min(float(mx),
                                     _quarter(factor * TRANSITION_PHASE_UTILISATION.get(pk, 100) / 100.0))
                             for pk in phase_keys}
    return out


def default_sdm_allocation(phase_keys: List[str]) -> Dict[str, float]:
    """AMS-default engagement SDM allocation per phase (fraction of one SDM), rounded to 0.25."""
    return {pk: _quarter(TRANSITION_PHASE_UTILISATION.get(pk, 100) / 100.0) for pk in phase_keys}


def reconcile_allocation(alloc, steady, phase_keys):
    """Self-heal the saved allocation against the current steady-state team & phases: seed missing
    cells with the AMS default, cap each at the steady-state seats, drop stale skills/levels/phases."""
    defaults = default_allocation(steady, phase_keys)
    out: Dict[str, Dict[str, Dict[str, float]]] = {}
    for sid, seats in steady.items():
        cur = (alloc or {}).get(sid, {}) or {}
        out[sid] = {}
        for lvl, mx in seats.items():
            crow = cur.get(lvl, {}) or {}
            drow = defaults[sid][lvl]
            out[sid][lvl] = {pk: float(max(0.0, min(float(crow.get(pk, drow[pk]) or 0), float(mx))))
                             for pk in phase_keys}
    return out


def reconcile_sdm(sdm_alloc, phase_keys):
    d = default_sdm_allocation(phase_keys)
    cur = sdm_alloc or {}
    return {pk: float(max(0.0, float(cur.get(pk, d[pk]) or 0))) for pk in phase_keys}


def compute_transition_cost(state: Dict[str, Any], *, alloc, sdm_alloc, phase_weeks,
                            weekly_hours: float = TRANSITION_WEEKLY_HOURS) -> Dict[str, Any]:
    """Transition cost from the per-phase allocation. `alloc` = {sid: {level: {phase_key: resource}}};
    `sdm_alloc` = {phase_key: resource}; `phase_weeks` = {phase_key: weeks}. Deterministic."""
    model = compute_multi_skill_model({**state, "fte_basis": "rounded"})
    rates_by_cat = state.get("rates_by_category", {}) or {}
    sdm_rate = float(state.get("sdm_rate_inr", 0) or 0)
    margin = float(state.get("target_margin_pct", 0) or 0) / 100.0
    wh = max(0.0, float(weekly_hours or 0))
    total_weeks = sum(float(w or 0) for w in (phase_weeks or {}).values())
    denom = total_weeks * wh

    def _fte(h):
        return (h / denom) if denom > 0 else 0.0

    def _sell(c):
        return (c / (1 - margin)) if 0 < margin < 1 else c

    steady = steady_state_seats(model)
    per_skill: Dict[str, Any] = {}
    by_level = {lvl: {"hours": 0.0, "cost": 0.0} for lvl in LEVELS}
    by_phase = {pk: {"hours": 0.0, "cost": 0.0} for pk in (phase_weeks or {})}
    total_hours = total_cost = 0.0

    for sid, ps in (model.get("per_skill", {}) or {}).items():
        cat = ps.get("genus_category")
        cap = steady.get(sid, {})
        acfg = (alloc or {}).get(sid, {}) or {}
        levels_out, s_hours, s_cost = {}, 0.0, 0.0
        for lvl in LEVELS:
            if lvl not in cap:
                continue
            prow = acfg.get(lvl, {}) or {}
            rate = float((rates_by_cat.get(cat, {}) or {}).get(lvl, 0) or 0)
            l_hours = l_cost = 0.0
            for pk, wk in (phase_weeks or {}).items():
                res = max(0.0, min(float(prow.get(pk, 0) or 0), float(cap[lvl])))   # capped
                hrs = res * float(wk or 0) * wh
                cost = hrs * rate
                l_hours += hrs; l_cost += cost
                by_phase[pk]["hours"] += hrs; by_phase[pk]["cost"] += cost
            levels_out[lvl] = {"hours": l_hours, "cost": l_cost, "rate_inr": rate,
                               "fte": _fte(l_hours), "steady": cap[lvl]}
            by_level[lvl]["hours"] += l_hours; by_level[lvl]["cost"] += l_cost
            s_hours += l_hours; s_cost += l_cost
        per_skill[sid] = {"name": ps.get("name") or sid, "genus_category": cat, "levels": levels_out,
                          "hours": s_hours, "cost": s_cost, "fte": _fte(s_hours), "selling": _sell(s_cost)}
        total_hours += s_hours; total_cost += s_cost

    sdm_hours = sdm_cost = 0.0
    for pk, wk in (phase_weeks or {}).items():
        h = max(0.0, float((sdm_alloc or {}).get(pk, 0) or 0)) * float(wk or 0) * wh
        sdm_hours += h
        by_phase[pk]["hours"] += h; by_phase[pk]["cost"] += h * sdm_rate
    sdm_cost = sdm_hours * sdm_rate
    total_hours += sdm_hours; total_cost += sdm_cost

    return {
        "weeks": round(total_weeks, 1), "weekly_hours": wh, "phase_weeks": dict(phase_weeks or {}),
        "per_skill": per_skill, "by_level": by_level, "by_phase": by_phase,
        "sdm": {"hours": sdm_hours, "rate_inr": sdm_rate, "cost": sdm_cost,
                "fte": _fte(sdm_hours), "selling": _sell(sdm_cost)},
        "total_hours": total_hours, "total_cost": total_cost, "total_fte": _fte(total_hours),
        "total_selling": _sell(total_cost), "margin_pct": margin * 100, "steady_seats": steady,
    }
