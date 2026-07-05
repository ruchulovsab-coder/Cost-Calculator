"""Multi-skill transition cost — pure, deterministic, capped by the steady-state team,
and it never perturbs the steady-state run-rate."""
from math import ceil

from modules.calculations.engine import compute_multi_skill_model
from modules.transition.costing import (
    LEVELS, steady_state_seats, default_transition_seats, reconcile_team, compute_transition_cost,
)
from tests.test_multi_excel import _skill


def _state():
    return {
        "skills": [_skill("s1", "Cloud Operations", "CloudOps", ["L2", "L3"], 25),
                   _skill("s2", "Monitoring", "InfraOps", ["L1"], 0)],
        "resource_sharing": [], "sdm_overhead_pct": 5.0, "sdm_rate_inr": 2000,
        "rates_by_category": {"InfraOps": {"L1": 800, "L2": 1200, "L3": 1700, "Architect": 2500},
                              "CloudOps": {"L1": 1000, "L2": 1500, "L3": 2200, "Architect": 3000}},
        "contingency_pct": 10.0, "monthly_working_hours": 160.0, "productive_utilisation": 75.0,
        "fte_basis": "rounded", "target_margin_pct": 25.0,
        "custom_hours_per_day": 8, "custom_days_per_week": 5,
    }


def test_steady_seats_are_ceil_of_fte_active_only():
    model = compute_multi_skill_model({**_state(), "fte_basis": "rounded"})
    seats = steady_state_seats(model)
    for sid, ps in model["per_skill"].items():
        fbl = ps["fte_by_level"]
        for lvl in LEVELS:
            f = float(fbl.get(lvl, 0) or 0)
            if f > 0:
                assert seats[sid][lvl] == int(ceil(f))
            else:
                assert lvl not in seats[sid]           # inactive levels excluded


def test_default_team_is_senior_weighted_min1_capped():
    steady = {"s1": {"L1": 4, "L2": 2, "L3": 2}}
    d = default_transition_seats(steady)["s1"]
    assert d["L1"] == 2          # 50% of 4
    assert d["L2"] == 2          # 75% of 2 → round(1.5)=2, capped at 2
    assert d["L3"] == 2          # 100%
    assert all(v >= 1 for v in d.values()) and all(d[l] <= steady["s1"][l] for l in d)


def test_reconcile_caps_seeds_and_drops():
    steady = {"s1": {"L2": 3, "L3": 2}}
    # over-cap + a stale skill + a stale level
    team = {"s1": {"L2": 9, "L3": 1, "L1": 5}, "old": {"L2": 2}}
    out = reconcile_team(team, steady)
    assert out == {"s1": {"L2": 3, "L3": 1}}          # L2 capped to 3, L1 dropped, old skill dropped


def test_cost_uses_capped_team_and_reconciles():
    state = _state()
    model = compute_multi_skill_model({**state, "fte_basis": "rounded"})
    steady = steady_state_seats(model)
    # Ask for more than steady on every level; it must cap.
    team = {sid: {lvl: 99 for lvl in cap} for sid, cap in steady.items()}
    res = compute_transition_cost(state, team=team, weeks=10, utilisation_pct=100, sdm_fte=1.0)

    wh = 40
    exp_total_hours = exp_total_cost = 0.0
    for sid, cap in steady.items():
        cat = model["per_skill"][sid]["genus_category"]
        for lvl, mx in cap.items():
            seats = mx                                  # capped to steady
            hrs = seats * 10 * wh * 1.0
            rate = state["rates_by_category"][cat][lvl]
            exp_total_hours += hrs
            exp_total_cost += hrs * rate
            assert res["per_skill"][sid]["levels"][lvl]["seats"] == mx
    # + SDM
    exp_total_hours += 1.0 * 10 * wh
    exp_total_cost += 1.0 * 10 * wh * state["sdm_rate_inr"]
    assert abs(res["total_hours"] - exp_total_hours) < 1e-6
    assert abs(res["total_cost"] - exp_total_cost) < 1e-6
    # by-level + per-skill roll up to the totals
    assert abs(sum(l["cost"] for lv in res["by_level"].values() for l in [lv]) + res["sdm"]["cost"]
               - res["total_cost"]) < 1e-6


def test_utilisation_and_weeks_scale_linearly():
    state = _state()
    a = compute_transition_cost(state, team=default_transition_seats(
        steady_state_seats(compute_multi_skill_model({**state, "fte_basis": "rounded"}))),
        weeks=10, utilisation_pct=100, sdm_fte=0)
    b = compute_transition_cost(state, team=default_transition_seats(
        steady_state_seats(compute_multi_skill_model({**state, "fte_basis": "rounded"}))),
        weeks=20, utilisation_pct=50, sdm_fte=0)
    # 20 weeks @ 50% == 10 weeks @ 100% (same seats, sdm=0)
    assert abs(a["total_hours"] - b["total_hours"]) < 1e-6
    assert abs(a["total_cost"] - b["total_cost"]) < 1e-6


def test_deterministic_and_does_not_perturb_run_rate():
    state = _state()
    before = compute_multi_skill_model(state)["total_fte"]
    team = default_transition_seats(steady_state_seats(
        compute_multi_skill_model({**state, "fte_basis": "rounded"})))
    r1 = compute_transition_cost(state, team=team, weeks=12, utilisation_pct=100, sdm_fte=1.0)
    r2 = compute_transition_cost(state, team=team, weeks=12, utilisation_pct=100, sdm_fte=1.0)
    assert r1 == r2                                     # deterministic
    after = compute_multi_skill_model(state)["total_fte"]
    assert before == after                              # run-rate untouched


def test_excel_builds():
    from modules.outputs.transition_excel import build_transition_cost_workbook
    state = _state()
    team = default_transition_seats(steady_state_seats(
        compute_multi_skill_model({**state, "fte_basis": "rounded"})))
    res = compute_transition_cost(state, team=team, weeks=12, utilisation_pct=100, sdm_fte=1.0)
    data = build_transition_cost_workbook(res, "Demo RFP")
    assert data[:2] == b"PK" and len(data) > 1500
