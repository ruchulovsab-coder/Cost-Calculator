"""Multi-skill transition cost — per-phase × per-skill × per-level fractional allocation.
Pure, deterministic, capped by the steady-state team, and it never perturbs the run-rate."""
from math import ceil

from modules.calculations.engine import compute_multi_skill_model
from modules.transition.costing import (
    LEVELS, steady_state_seats, default_allocation, default_sdm_allocation,
    reconcile_allocation, reconcile_sdm, compute_transition_cost,
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
        "fte_basis": "rounded", "target_margin_pct": 40.0,
        "custom_hours_per_day": 8, "custom_days_per_week": 5,
    }


PW = {"knowledge_transition": 4.0, "shadow": 2.0}   # phase_key -> weeks


def test_zero_workload_skill_excluded_from_transition_cost():
    """A skill with no workload has no steady-state team → it must not produce a (zero) cost
    line. Guards the skills-hygiene fix alongside the transition-plan exclusion."""
    st = _state()
    st["skills"][1]["workload"] = {}          # s2 (Monitoring) → no workload
    model = compute_multi_skill_model({**st, "fte_basis": "rounded"})
    steady = steady_state_seats(model)
    alloc = reconcile_allocation({}, steady, list(PW))
    sdm = reconcile_sdm({}, list(PW))
    res = compute_transition_cost(st, alloc=alloc, sdm_alloc=sdm, phase_weeks=PW)
    assert "s1" in res["per_skill"]
    assert "s2" not in res["per_skill"]


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
                assert lvl not in seats[sid]


def test_default_allocation_rounds_and_caps():
    steady = {"s1": {"L1": 4, "L2": 2}}
    d = default_allocation(steady, ["assessment", "knowledge_transition"])["s1"]
    # KT util 100%: L1 0.5×1=0.5 ; L2 0.75×1=0.75 (≤2)
    assert d["L1"]["knowledge_transition"] == 0.5
    assert d["L2"]["knowledge_transition"] == 0.75
    # everything is a 0.25 multiple and within the steady cap
    for lvl, mx in steady["s1"].items():
        for v in d[lvl].values():
            assert 0 <= v <= mx and abs((v * 4) - round(v * 4)) < 1e-9
    assert default_sdm_allocation(["knowledge_transition"])["knowledge_transition"] == 1.0


def test_reconcile_caps_seeds_and_drops():
    steady = {"s1": {"L2": 3, "L3": 2}}
    pk = ["knowledge_transition", "shadow"]
    alloc = {"s1": {"L2": {"knowledge_transition": 9},          # over-cap + missing 'shadow'
                    "L1": {"knowledge_transition": 1}},          # stale level
             "old": {"L2": {"knowledge_transition": 1}}}         # stale skill
    out = reconcile_allocation(alloc, steady, pk)
    assert set(out) == {"s1"} and set(out["s1"]) == {"L2", "L3"}   # stale skill/level dropped
    assert out["s1"]["L2"]["knowledge_transition"] == 3.0          # capped at steady
    assert "shadow" in out["s1"]["L2"]                             # missing phase seeded
    assert reconcile_sdm({"knowledge_transition": -5}, pk)["knowledge_transition"] == 0.0


def test_compute_caps_and_reconciles_totals():
    state = _state()
    model = compute_multi_skill_model({**state, "fte_basis": "rounded"})
    steady = steady_state_seats(model)
    wh, tw = 40, sum(PW.values())
    # Over-cap every cell; must clamp to steady seats.
    alloc = {sid: {lvl: {pk: 99.0 for pk in PW} for lvl in cap} for sid, cap in steady.items()}
    sdm_alloc = {pk: 1.0 for pk in PW}
    res = compute_transition_cost(state, alloc=alloc, sdm_alloc=sdm_alloc, phase_weeks=PW)

    exp_hours = exp_cost = 0.0
    for sid, cap in steady.items():
        cat = model["per_skill"][sid]["genus_category"]
        for lvl, mx in cap.items():
            for wk in PW.values():
                hrs = mx * wk * wh
                exp_hours += hrs
                exp_cost += hrs * state["rates_by_category"][cat][lvl]
            assert abs(res["per_skill"][sid]["levels"][lvl]["hours"] - mx * tw * wh) < 1e-6
    for wk in PW.values():
        exp_hours += 1.0 * wk * wh
        exp_cost += 1.0 * wk * wh * state["sdm_rate_inr"]
    assert abs(res["total_hours"] - exp_hours) < 1e-6
    assert abs(res["total_cost"] - exp_cost) < 1e-6
    # roll-ups
    assert abs(sum(d["cost"] for d in res["by_phase"].values()) - res["total_cost"]) < 1e-6
    assert abs(sum(d["cost"] for d in res["by_level"].values()) + res["sdm"]["cost"]
               - res["total_cost"]) < 1e-6
    # selling at the engagement margin
    assert abs(res["total_selling"] - res["total_cost"] / (1 - 0.40)) < 1e-3


def test_fraction_scales_effort():
    state = _state()
    steady = steady_state_seats(compute_multi_skill_model({**state, "fte_basis": "rounded"}))
    full = {sid: {lvl: {pk: 1.0 for pk in PW} for lvl in cap} for sid, cap in steady.items()}
    half = {sid: {lvl: {pk: 0.5 for pk in PW} for lvl in cap} for sid, cap in steady.items()}
    a = compute_transition_cost(state, alloc=full, sdm_alloc={}, phase_weeks=PW)
    b = compute_transition_cost(state, alloc=half, sdm_alloc={}, phase_weeks=PW)
    assert abs(a["total_hours"] - 2 * b["total_hours"]) < 1e-6
    assert abs(a["total_cost"] - 2 * b["total_cost"]) < 1e-6


def test_deterministic_and_does_not_perturb_run_rate():
    state = _state()
    before = compute_multi_skill_model(state)["total_fte"]
    steady = steady_state_seats(compute_multi_skill_model({**state, "fte_basis": "rounded"}))
    alloc = reconcile_allocation({}, steady, list(PW))
    r1 = compute_transition_cost(state, alloc=alloc, sdm_alloc=reconcile_sdm({}, list(PW)), phase_weeks=PW)
    r2 = compute_transition_cost(state, alloc=alloc, sdm_alloc=reconcile_sdm({}, list(PW)), phase_weeks=PW)
    assert r1 == r2
    assert compute_multi_skill_model(state)["total_fte"] == before


def test_excel_builds():
    from modules.outputs.transition_excel import build_transition_cost_workbook
    state = _state()
    steady = steady_state_seats(compute_multi_skill_model({**state, "fte_basis": "rounded"}))
    res = compute_transition_cost(state, alloc=reconcile_allocation({}, steady, list(PW)),
                                  sdm_alloc=reconcile_sdm({}, list(PW)), phase_weeks=PW)
    data = build_transition_cost_workbook(res, "Demo RFP")
    assert data[:2] == b"PK" and len(data) > 1500
