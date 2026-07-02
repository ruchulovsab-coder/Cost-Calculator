"""Phase 1 tests for the multi-skill engine (engine.compute_multi_skill_model).

Key guarantee: a single skill ("1 skill") reproduces the single-tower
compute_full_model, so the existing app is the N=1 special case. Plus aggregation,
resource sharing (pooled hours → one FTE), hide, and genus-family rates."""
import copy
import pytest

from modules.calculations.engine import compute_full_model, compute_multi_skill_model


def _cat(rows):
    return {lbl: dict(count=c, minutes=m, L1_pct=l1, L2_pct=l2, L3_pct=l3,
                      L1_buffer=20, L2_buffer=20, L3_buffer=20)
            for lbl, c, m, l1, l2, l3 in rows}


def _wl():
    return {
        "alerts": _cat([("Critical", 100, 30, 60, 30, 10)]),
        "service_requests": _cat([("Low", 300, 15, 90, 10, 0)]),
        "incidents": _cat([("High", 20, 120, 20, 50, 30)]),
        "changes": _cat([("Normal", 40, 60, 30, 50, 20)]),
    }


_RATES = {"L1": 700, "L2": 1100, "L3": 1600, "Architect": 2400, "SDM": 2200}


def _single_state():
    wl = _wl()
    return {**wl, "patching_included": "Yes", "num_servers": 20, "patching_method": "Manual",
            "manual_effort_per_server": 45, "auto_effort_per_server": 30, "patch_error_rate": 10,
            "patching_role": "L2",
            "additional_activities": [{"name": "RCA", "hours": 40.0,
                                       "dist": {"L1": 0, "L2": 30, "L3": 50, "Architect": 20, "SDM": 0}}],
            "contingency_pct": 10.0, "overhead_pcts": {"Architect": 5.0, "SDM": 5.0},
            "coverage_model": "8×5", "monthly_working_hours": 160.0, "productive_utilisation": 75.0,
            "role_rates_inr": dict(_RATES), "role_genus": {}, "additional_costs": [],
            "sla_provision_included": "No", "sla_provision_pct": 0.0,
            "target_margin_pct": 20.0, "reporting_currency": "INR", "fte_basis": "rounded"}


def _multi_1skill_state():
    return {
        "skills": [{
            "id": "s1", "name": "General", "genus_category": "InfraOps",
            "active_levels": ["L1", "L2", "L3"], "has_architect": True, "architect_pct": 5.0,
            "coverage_model": "8×5", "visible": True, "level_visible": {},
            "workload": _wl(),
            "patching": {"included": True, "num_servers": 20, "method": "Manual",
                         "manual_effort_per_server": 45, "auto_effort_per_server": 30,
                         "error_rate_pct": 10, "patching_role": "L2"},
            "activities": [{"name": "RCA", "hours": 40.0,
                            "dist": {"L1": 0, "L2": 30, "L3": 50, "Architect": 20}}],
        }],
        "resource_sharing": [],
        "rates_by_category": {"InfraOps": {"L1": 700, "L2": 1100, "L3": 1600, "Architect": 2400}},
        "sdm_overhead_pct": 5.0, "sdm_rate_inr": 2200,
        "contingency_pct": 10.0, "monthly_working_hours": 160.0, "productive_utilisation": 75.0,
        "additional_costs": [], "sla_provision_included": "No", "sla_provision_pct": 0.0,
        "target_margin_pct": 20.0, "fte_basis": "rounded",
    }


def test_single_skill_equals_single_tower():
    single = compute_full_model(_single_state())
    multi = compute_multi_skill_model(_multi_1skill_state())
    assert multi["engagement_total_effort"] == pytest.approx(single["total_effort"], rel=1e-3)
    rh = multi["per_skill"]["s1"]["role_hours"]
    for lvl in ("L1", "L2", "L3", "Architect"):
        assert rh[lvl] == pytest.approx(single["role_hours"][lvl], rel=1e-3), lvl
    assert multi["sdm_hours"] == pytest.approx(single["role_hours"]["SDM"], rel=1e-3)
    assert multi["total_resource_cost"] == pytest.approx(single["total_resource_cost"], rel=1e-3)
    assert multi["price_result"]["selling_price"] == pytest.approx(
        single["price_result"]["selling_price"], rel=1e-3)


def test_two_skills_aggregate():
    st = _multi_1skill_state()
    s2 = copy.deepcopy(st["skills"][0]); s2["id"] = "s2"; s2["name"] = "Cloud"
    st["skills"].append(s2)
    one = compute_multi_skill_model(_multi_1skill_state())
    two = compute_multi_skill_model(st)
    assert two["engagement_total_effort"] == pytest.approx(2 * one["engagement_total_effort"], rel=1e-3)
    assert set(two["per_skill"]) == {"s1", "s2"}


def _l3_skill(sid):
    return {"id": sid, "name": sid, "genus_category": "InfraOps", "active_levels": ["L3"],
            "has_architect": False, "coverage_model": "8×5", "visible": True, "level_visible": {},
            "workload": {"incidents": _cat([("High", 12, 120, 0, 0, 100)])},
            "patching": None, "activities": []}


def _share_base():
    return {"skills": [_l3_skill("a"), _l3_skill("b")], "resource_sharing": [],
            "rates_by_category": {"InfraOps": {"L3": 1600}}, "sdm_overhead_pct": 0.0,
            "contingency_pct": 0.0, "monthly_working_hours": 160.0, "productive_utilisation": 75.0,
            "target_margin_pct": 0.0, "fte_basis": "rounded"}


def test_resource_sharing_pools_fte():
    unshared = compute_multi_skill_model(_share_base())
    shared_state = _share_base()
    shared_state["resource_sharing"] = [
        {"id": "g1", "level": "L3", "skill_ids": ["a", "b"],
         "genus_category": "InfraOps", "coverage_model": "8×5"}]
    shared = compute_multi_skill_model(shared_state)
    # two dedicated L3 → 0.5 + 0.5 = 1.0 FTE; pooled → one 0.5 FTE
    assert unshared["total_fte"] == pytest.approx(1.0)
    assert shared["total_fte"] == pytest.approx(0.5)
    assert shared["total_resource_cost"] < unshared["total_resource_cost"]


def test_hidden_skill_excluded():
    st = _multi_1skill_state()
    s2 = copy.deepcopy(st["skills"][0]); s2["id"] = "s2"; s2["visible"] = False
    st["skills"].append(s2)
    res = compute_multi_skill_model(st)
    assert "s2" not in res["per_skill"]
    assert res["engagement_total_effort"] == pytest.approx(
        compute_multi_skill_model(_multi_1skill_state())["engagement_total_effort"], rel=1e-3)


def test_hidden_level_zeroed():
    st = _multi_1skill_state()
    st["skills"][0]["level_visible"] = {"L1": False}
    res = compute_multi_skill_model(st)
    assert res["per_skill"]["s1"]["role_hours"]["L1"] == 0.0
    assert res["per_skill"]["s1"]["role_hours"]["L2"] > 0.0
    assert not any(r["level"] == "L1" for r in res["resources"])


def test_breakdown_raw_buffered_final_reconciles():
    """Per-level build-up: final == role_hours, and raw ×(1+buf)×(1+cont) == final."""
    st = _multi_1skill_state()
    st["skills"][0]["role_buffers"] = {"L1": 20, "L2": 25, "L3": 30, "Architect": 10}
    st["contingency_pct"] = 10.0
    res = compute_multi_skill_model(st)
    ps = res["per_skill"]["s1"]
    bd, rh = ps["breakdown"], ps["role_hours"]
    for lvl in ("L1", "L2", "L3", "Architect"):
        d = bd[lvl]
        assert d["final"] == pytest.approx(rh[lvl], rel=1e-6), lvl          # final == staffed role hrs
        assert d["final"] == pytest.approx(d["buffered"] * 1.10, rel=1e-6), lvl  # contingency step
        assert d["raw"] <= d["buffered"] <= d["final"], lvl
    # Architect buffer (10%) actually moves the number vs a zero-buffer architect.
    st0 = _multi_1skill_state()
    st0["skills"][0]["role_buffers"] = {"L1": 20, "L2": 20, "L3": 20, "Architect": 0}
    arch0 = compute_multi_skill_model(st0)["per_skill"]["s1"]["role_hours"]["Architect"]
    assert res["per_skill"]["s1"]["role_hours"]["Architect"] > arch0


def test_zero_buffer_makes_raw_equal_buffered():
    st = _multi_1skill_state()
    st["skills"][0]["role_buffers"] = {"L1": 0, "L2": 0, "L3": 0, "Architect": 0}
    bd = compute_multi_skill_model(st)["per_skill"]["s1"]["breakdown"]
    for lvl in ("L1", "L2", "L3", "Architect"):
        assert bd[lvl]["raw"] == pytest.approx(bd[lvl]["buffered"], rel=1e-6), lvl


def test_context_switch_penalty_raises_pooled_fte():
    """A shared resource spanning >1 skill costs more effort when a penalty is set."""
    base_st = _share_base()
    base_st["resource_sharing"] = [
        {"id": "g1", "level": "L3", "skill_ids": ["a", "b"],
         "genus_category": "InfraOps", "coverage_model": "8×5"}]
    base = compute_multi_skill_model(base_st)
    penalised = compute_multi_skill_model({**base_st, "context_switch_pct": 50.0})
    assert penalised["total_fte"] > base["total_fte"]
    # Dedicated (unshared) resources are unaffected by the penalty (n_skills == 1).
    solo = compute_multi_skill_model(_share_base())
    solo_pen = compute_multi_skill_model({**_share_base(), "context_switch_pct": 50.0})
    assert solo["total_fte"] == pytest.approx(solo_pen["total_fte"])


def test_min_shift_floors_continuous_window_role():
    """A light 24×7 L2 desk floors to one continuous seat (ceil½ of the 4.2 multiplier)."""
    sk = {"id": "s1", "name": "NOC", "genus_category": "InfraOps", "active_levels": ["L2"],
          "has_architect": False, "coverage_model": "24×7", "visible": True, "level_visible": {},
          "workload": {"incidents": _cat([("High", 5, 60, 0, 100, 0)])},
          "patching": None, "activities": []}
    base = {"skills": [sk], "resource_sharing": [], "rates_by_category": {}, "sdm_overhead_pct": 0.0,
            "contingency_pct": 0.0, "monthly_working_hours": 160.0, "productive_utilisation": 75.0,
            "target_margin_pct": 0.0, "fte_basis": "rounded"}
    off = compute_multi_skill_model(base)
    on = compute_multi_skill_model({**base, "enforce_min_shift": True})
    l2_off = next(r for r in off["resources"] if r["level"] == "L2")
    l2_on = next(r for r in on["resources"] if r["level"] == "L2")
    assert l2_off["final_fte"] < 4.5
    assert l2_on["final_fte"] >= 4.5     # ceil½(4.2) = 4.5 — one continuous 24×7 seat


def test_genus_family_rates_differ():
    st = _multi_1skill_state()
    st["rates_by_category"] = {"InfraOps": {"L1": 700, "L2": 1100, "L3": 1600, "Architect": 2400},
                               "CloudOps": {"L1": 1000, "L2": 1500, "L3": 2200, "Architect": 3000}}
    infra = compute_multi_skill_model(st)
    cloud_state = copy.deepcopy(st); cloud_state["skills"][0]["genus_category"] = "CloudOps"
    cloud = compute_multi_skill_model(cloud_state)
    assert cloud["total_resource_cost"] > infra["total_resource_cost"]


def _active_levels_state(active):
    """One skill whose stored split routes 50/30/20 to L1/L2/L3 regardless of which
    levels are actually active — the state a de-activated level (or demo pre-fill) leaves."""
    return {
        "skills": [{
            "id": "m", "name": "Monitoring", "genus_category": "InfraOps",
            "active_levels": list(active), "has_architect": False, "architect_pct": 0.0,
            "coverage_model": "24×7", "visible": True, "level_visible": {},
            "role_buffers": {"L1": 20, "L2": 20, "L3": 20, "Architect": 0},
            "workload": {"service_requests": {"All": {"count": 100, "minutes": 30,
                                                      "L1_pct": 50, "L2_pct": 30, "L3_pct": 20}}},
            "patching": None, "activities": [],
        }],
        "resource_sharing": [],
        "rates_by_category": {"InfraOps": {"L1": 700, "L2": 1100, "L3": 1600, "Architect": 2400}},
        "sdm_overhead_pct": 5.0, "sdm_rate_inr": 2200,
        "contingency_pct": 10.0, "monthly_working_hours": 160.0, "productive_utilisation": 75.0,
        "additional_costs": [], "sla_provision_included": "No", "sla_provision_pct": 0.0,
        "target_margin_pct": 20.0, "fte_basis": "rounded",
    }


def test_grade_eligibility_by_family():
    """InfraOps prices off *-INFRAOPS (unchanged); CloudOps off *-CLOUD-INFRASTRUCTURE
    (same band numbers); SDM stays *-DELIVERY-ITIL for both."""
    from config.settings import grade_eligibility
    assert grade_eligibility("L1", "InfraOps") == ["2.1-INFRAOPS", "2.2-INFRAOPS"]
    assert grade_eligibility("L1", "CloudOps") == ["2.1-CLOUD-INFRASTRUCTURE", "2.2-CLOUD-INFRASTRUCTURE"]
    assert grade_eligibility("L2", "CloudOps") == ["2.3-CLOUD-INFRASTRUCTURE", "3.1-CLOUD-INFRASTRUCTURE"]
    assert grade_eligibility("L3", "CloudOps") == ["3.2-CLOUD-INFRASTRUCTURE", "3.3-CLOUD-INFRASTRUCTURE"]
    assert grade_eligibility("Architect", "CloudOps") == ["4.1-CLOUD-INFRASTRUCTURE"]
    assert grade_eligibility("SDM", "CloudOps") == ["4.1-DELIVERY-ITIL"]        # shared
    assert grade_eligibility("L1") == ["2.1-INFRAOPS", "2.2-INFRAOPS"]          # default InfraOps


def test_architect_requires_l3():
    """Architect is a role above L3 — the state builder drops has_architect when L3 is
    not an active level, so no architect effort/cost leaks in without L3."""
    from modules.state.multi_state import build_multi_model_state_from
    sk = {"id": "s1", "name": "Monitoring", "genus_category": "InfraOps",
          "active_levels": ["L1", "L2"], "has_architect": True, "architect_pct": 25.0,
          "role_buffers": {"L1": 20, "L2": 20, "L3": 20, "Architect": 0},
          "workload": {"incidents": {"P3": {"count": 50, "minutes": 30, "L1_pct": 60, "L2_pct": 40, "L3_pct": 0}}},
          "patching": None, "activities": []}
    state = build_multi_model_state_from({"estimation_mode": "multi", "skills": [sk]})
    assert state["skills"][0]["has_architect"] is False
    # with L3 active, it is preserved
    sk2 = dict(sk); sk2["active_levels"] = ["L1", "L2", "L3"]; sk2["has_architect"] = True
    state2 = build_multi_model_state_from({"estimation_mode": "multi", "skills": [sk2]})
    assert state2["skills"][0]["has_architect"] is True


def test_activities_distribute_only_on_staffed_roles():
    """An additional activity whose split points at L3/Architect on an L1/L2-only skill has
    its hours folded onto the staffed roles — no effort leaks to L3 or Architect."""
    st = {"skills": [{"id": "s1", "name": "S", "genus_category": "InfraOps",
                      "active_levels": ["L1", "L2"], "has_architect": False, "architect_pct": 0.0,
                      "role_buffers": {"L1": 0, "L2": 0, "L3": 0, "Architect": 0}, "coverage_model": "8×5",
                      "workload": {"incidents": {"P3": {"count": 10, "minutes": 60,
                                                        "L1_pct": 50, "L2_pct": 50, "L3_pct": 0}}},
                      "patching": None,
                      "activities": [{"name": "RCA", "hours": 40.0, "auto": False,
                                      "dist": {"L2": 20, "L3": 50, "Architect": 30}}]}],
          "resource_sharing": [], "rates_by_category": {"InfraOps": {"L1": 500, "L2": 800, "L3": 1200, "Architect": 2000}},
          "sdm_overhead_pct": 0.0, "sdm_rate_inr": 0, "monthly_working_hours": 160.0,
          "productive_utilisation": 75.0, "contingency_pct": 0.0, "fte_basis": "raw",
          "delivery_country": "India", "target_margin_pct": 0.0}
    m = compute_multi_skill_model(st)
    rh = m["per_skill"]["s1"]["role_hours"]
    assert rh["L3"] == pytest.approx(0.0)
    assert rh["Architect"] == pytest.approx(0.0)
    assert rh["L2"] == pytest.approx(45.0)                 # ticket 5h + all 40h activity folded to L2
    assert m["engagement_total_effort"] == pytest.approx(50.0)   # 10 ticket + 40 activity, preserved


def test_classification_migration_is_neutral():
    """Legacy single-bucket ('All') workload migrates to the per-classification model
    with identical total effort and per-level hours (safe, numerically neutral)."""
    from modules.state.multi_state import ensure_ms_workload, skill_volumes
    legacy_wl = {"incidents": {"All": {"count": 100, "minutes": 60,
                                       "L1_pct": 50, "L2_pct": 30, "L3_pct": 20}}}

    def _state(wl):
        return {"skills": [{"id": "s1", "name": "S", "genus_category": "InfraOps",
                            "active_levels": ["L1", "L2", "L3"], "has_architect": False,
                            "architect_pct": 0.0, "role_buffers": {"L1": 20, "L2": 20, "L3": 20, "Architect": 0},
                            "coverage_model": "8×5", "workload": copy.deepcopy(wl),
                            "patching": None, "activities": []}],
                "resource_sharing": [], "rates_by_category": {"InfraOps": {"L1": 500, "L2": 800, "L3": 1200, "Architect": 2000}},
                "sdm_overhead_pct": 5.0, "sdm_rate_inr": 2500, "monthly_working_hours": 160.0,
                "productive_utilisation": 75.0, "contingency_pct": 10.0, "fte_basis": "rounded",
                "delivery_country": "India", "target_margin_pct": 20.0}

    before = compute_multi_skill_model(_state(legacy_wl))
    sk = {"active_levels": ["L1", "L2", "L3"], "workload": copy.deepcopy(legacy_wl)}
    ensure_ms_workload(sk)
    # distributed to P1..P4, summing back to the original total
    assert sum(r["count"] for r in sk["workload"]["incidents"].values()) == 100
    assert skill_volumes(sk)["incidents"] == 100.0
    after = compute_multi_skill_model(_state(sk["workload"]))
    assert after["engagement_total_effort"] == pytest.approx(before["engagement_total_effort"], rel=1e-9)
    for lvl in ("L1", "L2", "L3"):
        assert after["per_skill"]["s1"]["role_hours"][lvl] == pytest.approx(
            before["per_skill"]["s1"]["role_hours"][lvl], rel=1e-6)


def test_active_levels_restrict_ticket_routing():
    """Tickets land ONLY on a skill's active levels; a stale split referencing an inactive
    level is renormalized away, and total effort is preserved (it's split-independent)."""
    full = compute_multi_skill_model(_active_levels_state(["L1", "L2", "L3"]))
    l1l2 = compute_multi_skill_model(_active_levels_state(["L1", "L2"]))
    only1 = compute_multi_skill_model(_active_levels_state(["L1"]))

    total = full["engagement_total_effort"]
    assert l1l2["engagement_total_effort"] == pytest.approx(total, rel=1e-9)
    assert only1["engagement_total_effort"] == pytest.approx(total, rel=1e-9)

    bd = l1l2["per_skill"]["m"]["breakdown"]
    assert bd["L3"]["final"] == pytest.approx(0.0)
    assert bd["L1"]["final"] > 0 and bd["L2"]["final"] > 0

    bd1 = only1["per_skill"]["m"]["breakdown"]
    assert bd1["L2"]["final"] == pytest.approx(0.0)
    assert bd1["L3"]["final"] == pytest.approx(0.0)
    assert bd1["L1"]["final"] > 0
