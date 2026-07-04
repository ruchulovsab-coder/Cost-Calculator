"""Transition Strategy — deterministic builder + timeline solver tests.

Read-only projection of the estimate: same model+config → identical plan; timeline reconciles;
RACI is valid (exactly one Accountable); never mutates the model; engine never imports it."""
import copy
from datetime import date

import pytest

from modules.calculations.engine import compute_multi_skill_model
from modules.transition.builder import (build_transition_plan, default_phase_config, validate_raci)
from modules.transition.timeline import solve_timeline
from modules.transition import catalog as C
from tests.test_multi_skill import _multi_1skill_state


def _cfg(**kw):
    base = {"start_date": "2026-08-03", "duration_weeks": 20, "go_live_date": None,
            "customer_tz": "EST", "sequencing": "Sequential", "incumbent_present": True,
            "phases": default_phase_config()}
    base.update(kw)
    return base


def test_sequential_timeline_is_contiguous():
    tl = solve_timeline("2026-08-03", default_phase_config(), sequencing="Sequential")
    rows = tl["rows"]
    assert len(rows) == len(C.PHASES)
    assert rows[0]["start"] == date(2026, 8, 3)
    for a, b in zip(rows, rows[1:]):
        assert b["start"] == a["end"], "sequential phases must be contiguous"


def test_overlap_pulls_phase_earlier():
    phases = default_phase_config()
    phases[3]["overlap_lead_weeks"] = 2   # Shadow starts 2 weeks before KT ends
    seq = solve_timeline("2026-08-03", default_phase_config(), sequencing="Sequential")
    ovl = solve_timeline("2026-08-03", phases, sequencing="Overlap")
    assert ovl["rows"][3]["start"] < seq["rows"][3]["start"]


def test_milestones_and_go_live_gate():
    tl = solve_timeline("2026-08-03", default_phase_config(), sequencing="Sequential")
    ids = [m["id"] for m in tl["milestones"]]
    assert ids == ["M1", "M2", "M3", "Go-Live", "M4"]
    go_live = next(m for m in tl["milestones"] if m["id"] == "Go-Live")
    rs = next(r for r in tl["rows"] if r["key"] == "reverse_shadow")
    assert go_live["date"] == rs["end"]


def test_duration_mismatch_advisory():
    tl = solve_timeline("2026-08-03", default_phase_config(), sequencing="Sequential",
                        overall_weeks=99)
    assert any("overall duration" in a for a in tl["advisories"])


def test_go_live_before_signoff_advisory():
    tl = solve_timeline("2026-08-03", default_phase_config(), sequencing="Sequential",
                        go_live="2026-08-10")
    assert any("before the Reverse-Shadow" in a for a in tl["advisories"])


def test_greenfield_advisory():
    tl = solve_timeline("2026-08-03", default_phase_config(), incumbent_present=False)
    assert any("greenfield" in a.lower() for a in tl["advisories"])


def test_raci_is_valid():
    assert validate_raci(C.RACI) == []


def test_deterministic_and_covers_skills():
    model = compute_multi_skill_model(_multi_1skill_state())
    a = build_transition_plan(model, _cfg())
    b = build_transition_plan(model, _cfg())
    assert a == b
    assert a["skill_plans"] and all(sp["knowledge_transition"] for sp in a["skill_plans"])
    assert not any("Accountable" in adv for adv in a["advisories"])


def test_excluded_phase_drops_from_plan():
    phases = default_phase_config()
    for p in phases:
        if p["key"] == "shadow":
            p["included"] = False
    model = compute_multi_skill_model(_multi_1skill_state())
    plan = build_transition_plan(model, _cfg(phases=phases))
    assert all(r["key"] != "shadow" for r in plan["timeline"])
    assert all(row["phase"] != "shadow" for row in plan["raci"])


def test_does_not_mutate_model():
    model = compute_multi_skill_model(_multi_1skill_state())
    snap = copy.deepcopy(model)
    build_transition_plan(model, _cfg())
    assert model == snap


def test_transition_excel_builds():
    from modules.outputs.transition_excel import build_transition_workbook
    model = compute_multi_skill_model(_multi_1skill_state())
    plan = build_transition_plan(model, _cfg())
    data = build_transition_workbook(plan, "Demo RFP")
    assert data[:2] == b"PK" and len(data) > 2000


def test_engine_does_not_import_transition():
    import inspect
    from modules.calculations import engine
    from modules.state import multi_state
    for mod in (engine, multi_state):
        src = inspect.getsource(mod)
        assert "modules.transition" not in src, f"{mod.__name__} must not import modules.transition"
