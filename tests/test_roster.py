"""Shift Plan / Roster Designer — deterministic scheduler tests.

The roster is a PURE read-only projection of the estimate: same model+config → identical
plan, seats reconcile to ceil(FTE), and it never touches the engine (one-way dependency)."""
import copy

import pytest

from modules.calculations.engine import compute_multi_skill_model
from modules.roster.scheduler import (
    build_roster, parse_hhmm, fmt_hhmm, convert, TZ_OFFSETS)
from tests.test_multi_skill import _multi_1skill_state


def _cfg(**kw):
    base = {"strategy": "Balanced", "customer_tz": "EST", "delivery_tz": "IST",
            "business_start": "09:00", "business_end": "17:00", "shift_length_h": 8,
            "coverage_prefs": {}}
    base.update(kw)
    return base


def test_time_helpers():
    assert parse_hhmm("09:00") == 9.0
    assert parse_hhmm("5:30 PM") == 17.5
    assert parse_hhmm("bad", 8.0) == 8.0
    assert fmt_hhmm(17.5) == "17:30"
    assert fmt_hhmm(23.75) == "23:45"
    # EST 09:00 → IST is +10.5h → 19:30
    assert fmt_hhmm(convert(9.0, TZ_OFFSETS["EST"], TZ_OFFSETS["IST"])) == "19:30"


def test_deterministic():
    model = compute_multi_skill_model(_multi_1skill_state())
    a = build_roster(model, _cfg())
    b = build_roster(model, _cfg())
    assert a == b


def test_seats_reconcile_to_ceil_fte():
    model = compute_multi_skill_model(_multi_1skill_state())
    plan = build_roster(model, _cfg())
    assert plan["reconciliation"], "expected reconciliation rows"
    import math
    for r in plan["reconciliation"]:
        assert r["seats"] == max(1, math.ceil(r["fte"] - 1e-9))
        assert r["delta"] == round(r["seats"] - r["fte"], 2)
    assert plan["totals"]["deployable_seats"] == sum(r["seats"] for r in plan["reconciliation"])


def test_247_gets_three_shift_blocks():
    st = _multi_1skill_state()
    st["skills"][0]["coverage_model"] = "24×7"
    st["skills"][0]["active_levels"] = ["L1", "L2"]
    st["skills"][0]["has_architect"] = False
    model = compute_multi_skill_model(st)
    plan = build_roster(model, _cfg())
    l1_shifts = [s for s in plan["shifts"] if s["level"] == "L1"]
    assert len(l1_shifts) == 3
    assert all(s["days"] == "Mon–Sun" for s in l1_shifts)


def _tiny_skill_state(coverage, level):
    """A deliberately tiny single-level workload so seats are minimal (advisory territory)."""
    st = _multi_1skill_state()
    sk = st["skills"][0]
    sk["coverage_model"] = coverage
    sk["active_levels"] = [level]
    sk["has_architect"] = False
    sk["patching"] = {"included": False}
    sk["activities"] = []
    row = {"count": 1, "minutes": 15, "L1_pct": 0, "L2_pct": 0, "L3_pct": 0,
           "L1_buffer": 0, "L2_buffer": 0, "L3_buffer": 0}
    row[f"{level}_pct"] = 100
    sk["workload"] = {"incidents": {"Low": row}, "alerts": {},
                      "service_requests": {}, "changes": {}}
    return st


def test_advisory_when_seats_cannot_cover_blocks():
    # 16×5 = 2 shift blocks; a tiny L2-only workload yields 1 seat → cannot staff both blocks.
    st = _tiny_skill_state("16×5", "L2")
    model = compute_multi_skill_model(st)
    plan = build_roster(model, _cfg())
    l2 = next(r for r in plan["reconciliation"] if r["level"] == "L2")
    assert l2["seats"] == 1
    assert any("shift blocks" in a for a in plan["advisories"])


def test_l3_architect_are_business_plus_oncall_not_night():
    st = _multi_1skill_state()
    st["skills"][0]["coverage_model"] = "24×7"
    model = compute_multi_skill_model(st)
    plan = build_roster(model, _cfg())
    for s in plan["shifts"]:
        if s["level"] in ("L3", "Architect"):
            assert s["shift"].startswith("Business")
            assert s["days"] == "Mon–Fri"


def test_business_vs_nonbusiness_window_placement():
    st = _multi_1skill_state()
    st["skills"][0]["coverage_model"] = "8×5"
    st["skills"][0]["active_levels"] = ["L1"]
    st["skills"][0]["has_architect"] = False
    model = compute_multi_skill_model(st)
    sid = st["skills"][0]["id"]
    biz = build_roster(model, _cfg(coverage_prefs={sid: {"mode": "Business Hours"}}))
    non = build_roster(model, _cfg(coverage_prefs={sid: {"mode": "Non-Business Hours"}}))
    biz_win = next(s["customer"] for s in biz["shifts"] if s["level"] == "L1")
    non_win = next(s["customer"] for s in non["shifts"] if s["level"] == "L1")
    assert biz_win.startswith("09:00")
    assert non_win.startswith("17:00")


def test_roster_does_not_mutate_model():
    model = compute_multi_skill_model(_multi_1skill_state())
    snapshot = copy.deepcopy(model)
    build_roster(model, _cfg())
    assert model == snapshot


def test_engine_does_not_import_roster():
    """One-way dependency: the estimator must never depend on the roster."""
    import inspect
    from modules.calculations import engine
    from modules.state import multi_state
    for mod in (engine, multi_state):
        src = inspect.getsource(mod)
        assert "modules.roster" not in src, f"{mod.__name__} must not import modules.roster"
