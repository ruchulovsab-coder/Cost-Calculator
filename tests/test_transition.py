"""Transition Strategy — deterministic builder + timeline solver tests.

Read-only projection of the estimate: same model+config → identical plan; timeline reconciles;
RACI is valid (exactly one Accountable); never mutates the model; engine never imports it."""
import copy
from datetime import date

import pytest

from modules.calculations.engine import compute_multi_skill_model
from modules.transition.builder import (build_transition_plan, default_phase_config,
                                        validate_raci, _skill_family)
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


def test_skill_family_classification():
    assert _skill_family("Linux Administration") == "compute"
    assert _skill_family("Windows / Active Directory") == "compute"
    assert _skill_family("Network & Firewall") == "network"
    assert _skill_family("Oracle DBA") == "database"
    assert _skill_family("Cloud Operations (Azure)") == "cloud"
    assert _skill_family("DevOps / SRE") == "platform"
    assert _skill_family("Something Unmapped") is None


def test_family_aware_skill_detail():
    """A DB skill gets DB-specific activities; an unmapped skill falls back to the generic set."""
    model = compute_multi_skill_model(_multi_1skill_state())
    # Rename the single skill to a Database skill so classification fires.
    sid = next(iter(model["per_skill"]))
    model["per_skill"][sid]["name"] = "Oracle Database"
    plan = build_transition_plan(model, _cfg())
    sp = plan["skill_plans"][0]
    assert sp["family"] == "database"
    assert sp["family_label"] == C.FAMILY_LABELS["database"]
    kt = " ".join(sp["knowledge_transition"])
    assert "Oracle Database" in kt
    assert "PITR" in kt or "HA/replication" in kt   # DB-specific, absent from the generic template

    # Unmapped name → generic technical layer + "General" label (still gets the process backbone).
    model["per_skill"][sid]["name"] = "Zzz Unmapped Skill"
    gen = build_transition_plan(model, _cfg())["skill_plans"][0]
    assert gen["family"] is None and gen["family_label"] == "General"
    assert any("Functional & technical knowledge transfer for Zzz Unmapped Skill" in x
               for x in gen["knowledge_transition"])
    # …and the common process backbone is present even for an unmapped skill.
    assert any("incident management" in x.lower() for x in gen["knowledge_transition"])


def test_operational_process_backbone_covered_for_every_skill():
    """Every skill's woven plan covers the full ITIL process framework (same set for all)."""
    model = compute_multi_skill_model(_multi_1skill_state())
    sp = build_transition_plan(model, _cfg())["skill_plans"][0]
    kt = " ".join(sp["knowledge_transition"]).lower()
    # one representative keyword per OPERATIONAL_PROCESS_AREAS entry
    for kw in ("workflow", "incident management", "major incident", "problem management",
               "change management", "service request", "access management",
               "monitoring & event", "patching", "escalation & communication",
               "cmdb", "reporting & governance"):
        assert kw in kt, f"KT missing process area keyword: {kw!r}"
    # process discipline is also exercised downstream, not only understood in KT
    assert any("major incident" in x.lower() for x in sp["reverse_shadow"])
    assert any("independently run" in x.lower() for x in sp["stabilization"])


def test_new_skill_reflects_in_skill_plans():
    """Adding a skill to the estimate surfaces it (with full woven detail) in the plan —
    the plan is derived live from the model, so it is never static."""
    model = compute_multi_skill_model(_multi_1skill_state())
    base = build_transition_plan(model, _cfg())
    assert len(base["skill_plans"]) == len(model["per_skill"])
    # Simulate the user adding a new skill to the estimate.
    src = next(iter(model["per_skill"].values()))
    model["per_skill"]["new_sid"] = {**src, "name": "Cloud Operations"}
    grown = build_transition_plan(model, _cfg())
    assert len(grown["skill_plans"]) == len(base["skill_plans"]) + 1
    added = next(sp for sp in grown["skill_plans"] if sp["skill"] == "Cloud Operations")
    assert added["family"] == "cloud" and added["knowledge_transition"]
    assert any("landing-zone" in x for x in added["knowledge_transition"])


def _rs_end(plan):
    return next(r["end"] for r in plan["timeline"] if r["key"] == "reverse_shadow")


def test_go_live_reshapes_timeline():
    """Changing the Go-Live date moves Reverse-Shadow's end to that date (phases fit the window)."""
    model = compute_multi_skill_model(_multi_1skill_state())
    near = build_transition_plan(model, _cfg(go_live_date="2026-11-01"))
    far = build_transition_plan(model, _cfg(go_live_date="2027-03-01"))
    # Reverse-Shadow ends on (≈) the configured Go-Live date, within rounding.
    assert abs((_rs_end(near) - date(2026, 11, 1)).days) <= 1
    assert abs((_rs_end(far) - date(2027, 3, 1)).days) <= 1
    # A later Go-Live yields a longer overall span — the Gantt reflects the change.
    assert far["span_weeks"] > near["span_weeks"]
    # The Go-Live milestone lands on the Go-Live date too.
    gl = next(m for m in far["milestones"] if m["id"] == "Go-Live")
    assert abs((gl["date"] - date(2027, 3, 1)).days) <= 1


def test_start_date_shifts_timeline():
    model = compute_multi_skill_model(_multi_1skill_state())
    a = build_transition_plan(model, _cfg(start_date="2026-08-03", go_live_date="2026-12-01"))
    b = build_transition_plan(model, _cfg(start_date="2026-09-03", go_live_date="2026-12-01"))
    assert b["start"] > a["start"]                    # start moves
    assert b["timeline"][0]["start"] == date(2026, 9, 3)


def test_no_go_live_leaves_phases_unscaled():
    """Without a Go-Live date, phases keep their configured durations (no fitting)."""
    model = compute_multi_skill_model(_multi_1skill_state())
    plan = build_transition_plan(model, _cfg(go_live_date=None))
    kt = next(r for r in plan["timeline"] if r["key"] == "knowledge_transition")
    assert kt["duration_weeks"] == 4                  # default, unscaled


def test_acceptance_gate_per_skill():
    """Exit/Sign-off are detailed governance gates: open items owned & agreed, residual risk
    accepted by both parties, ownership transfer, named sign-off — with a family critical check."""
    model = compute_multi_skill_model(_multi_1skill_state())
    sid = next(iter(model["per_skill"]))
    model["per_skill"][sid]["name"] = "Oracle Database"
    plan = build_transition_plan(model, _cfg())
    sp = plan["skill_plans"][0]

    exit_txt = " ".join(sp["exit_criteria"]).lower()
    signoff_txt = " ".join(sp["signoff_criteria"]).lower()
    assert "owner" in exit_txt and "agreed by both parties" in exit_txt
    assert "no open p1/p2" in exit_txt
    assert "accepted by both parties" in signoff_txt          # residual risk acceptance
    assert "ownership of" in signoff_txt and "transferred" in signoff_txt
    assert "no-go" in signoff_txt or "conditional-go" in signoff_txt

    # Family-specific critical check (DB → restore/failover); generic fallback for unmapped.
    assert "restore" in sp["family_critical_check"].lower()
    assert "Oracle Database" in sp["family_critical_check"]
    model["per_skill"][sid]["name"] = "Zzz Unmapped Skill"
    gen = build_transition_plan(model, _cfg())["skill_plans"][0]
    assert gen["family_critical_check"] == \
        C.GENERIC_CRITICAL_CHECK.format(skill="Zzz Unmapped Skill")

    # Fillable register + named sign-off block templates present at plan level.
    assert plan["open_items_columns"] == C.OPEN_ITEMS_RISK_COLUMNS
    parties = {p for p, _ in plan["signoff_signatories"]}
    assert parties == {"Customer", "Nagarro"}                 # both parties sign
    assert "Go" in plan["signoff_decision"]


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
