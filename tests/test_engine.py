"""Unit tests for the pure calculation engine."""
import math
import pandas as pd
import pytest

from config.settings import ALL_ROLES, COVERAGE_APPLICABLE_ROLES, ACTIVITY_FORMULAS
from modules.calculations.engine import (
    convert_rate_to_inr, convert_to_currency, calc_productive_hours,
    calc_coverage_multiplier, calc_fte, ceil_half, calc_patching_effort,
    calc_total_delivery_cost, calc_selling_price, assemble_role_hours,
    calc_resource_cost, filter_rate_card, resolve_role_rates, derive_activity_hours,
    calc_category_role_hours, calc_transition_cost, transition_week_phase_map,
)


# ── Per-row, per-role buffer on resolution split ───────────────────────────────

def test_category_role_hours_applies_explicit_buffer():
    # 100 tickets × 60 min = 100 base hrs, all to L1, +20% buffer = 120
    cat = {"Low": {"count": 100, "minutes": 60, "L1_pct": 100, "L2_pct": 0, "L3_pct": 0,
                   "L1_buffer": 20, "L2_buffer": 0, "L3_buffer": 0}}
    r = calc_category_role_hours(cat)
    assert r["L1"] == pytest.approx(120.0)
    assert r["L2"] == 0.0 and r["L3"] == 0.0


def test_category_role_hours_per_role_buffers_differ():
    cat = {"Hi": {"count": 60, "minutes": 60, "L1_pct": 50, "L2_pct": 30, "L3_pct": 20,
                  "L1_buffer": 0, "L2_buffer": 10, "L3_buffer": 50}}
    # base 60 hrs: L1 30, L2 18, L3 12 -> buffered: 30, 19.8, 18
    r = calc_category_role_hours(cat)
    assert r["L1"] == pytest.approx(30.0)
    assert r["L2"] == pytest.approx(19.8)
    assert r["L3"] == pytest.approx(18.0)


def test_category_role_hours_defaults_buffer_when_missing():
    # No buffer fields -> default 20%
    cat = {"x": {"count": 60, "minutes": 60, "L1_pct": 100, "L2_pct": 0, "L3_pct": 0}}
    assert calc_category_role_hours(cat)["L1"] == pytest.approx(72.0)  # 60 × 1.2


# ── Currency ──────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("currency", ["INR", None, "None", "", "nan"])
def test_convert_rate_to_inr_treats_blank_as_inr(currency):
    assert convert_rate_to_inr(500.0, currency, {"INR": 1.0}) == 500.0


def test_convert_rate_to_inr_foreign():
    assert convert_rate_to_inr(50.0, "USD", {"USD": 83.0}) == pytest.approx(4150.0)


def test_convert_rate_to_inr_missing_fx_raises():
    with pytest.raises(ValueError):
        convert_rate_to_inr(50.0, "USD", {})


def test_convert_to_currency_roundtrip():
    assert convert_to_currency(8300.0, "INR", {"INR": 1.0}) == 8300.0
    assert convert_to_currency(8300.0, "USD", {"USD": 83.0}) == pytest.approx(100.0)
    # Unknown currency falls back to INR value unchanged
    assert convert_to_currency(100.0, "XYZ", {}) == 100.0


# ── FTE ───────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("value,expected", [(2.0, 2.0), (2.1, 2.5), (2.5, 2.5), (2.6, 3.0), (0.01, 0.5)])
def test_ceil_half(value, expected):
    assert ceil_half(value) == expected


def test_calc_fte_coverage_and_minimum():
    role_hours = {r: 0.0 for r in ALL_ROLES}
    role_hours["L1"] = 80.0   # coverage role
    role_hours["L3"] = 5.0     # non-coverage, tiny -> min 0.5
    prod = calc_productive_hours(160, 75)        # 120
    mult = calc_coverage_multiplier("24×7")      # 4.2
    fte = calc_fte(role_hours, prod, mult)
    assert fte["L1"]["coverage_applied"] is True
    assert fte["L3"]["coverage_applied"] is False
    assert fte["L2"]["final_fte"] == 0.0          # zero hours -> zero FTE
    assert fte["L3"]["final_fte"] == 0.5          # min floor
    # L1 raw = 80/120*4.2 = 2.8 -> ceil_half 3.0
    assert fte["L1"]["final_fte"] == 3.0


def test_coverage_applicable_roles_config():
    assert set(COVERAGE_APPLICABLE_ROLES) == {"L1", "L2"}


# ── Patching ──────────────────────────────────────────────────────────────────

def test_patching_excluded():
    assert calc_patching_effort(False, 20, "Manual")["hours"] == 0.0


def test_patching_manual_default_45_per_server():
    res = calc_patching_effort(True, 20, "Manual", manual_effort_per_server=45.0)
    assert res["effort_per_server_min"] == 45.0
    assert res["hours"] == pytest.approx(20 * 45 / 60.0)  # 15.0


def test_patching_tool_based_uses_error_rate():
    # 100 servers, 15% error -> 15 failed servers × 30 min = 7.5 hrs
    res = calc_patching_effort(True, 100, "Tool-Based", auto_effort_per_server=30.0, error_rate_pct=15)
    assert res["failed_servers"] == 15
    assert res["hours"] == pytest.approx(15 * 30 / 60.0)  # 7.5


def test_patching_tool_based_zero_error_is_zero():
    res = calc_patching_effort(True, 100, "Tool-Based", auto_effort_per_server=30.0, error_rate_pct=0)
    assert res["failed_servers"] == 0 and res["hours"] == 0.0


# ── Auto-derived activity efforts ──────────────────────────────────────────────

def test_derive_scheduled_maintenance_uses_servers():
    h = derive_activity_hours("Scheduled Maintenance", 20, {})
    assert h == pytest.approx(20 * 30 / 60.0)  # 30 min/server


def test_derive_rca_uses_incidents():
    vols = {"alerts": 100, "incidents": 10, "service_requests": 25, "changes": 8}
    assert derive_activity_hours("Root Cause Analysis (RCA)", 20, vols) == pytest.approx(10 * 360 / 60.0)


def test_derive_problem_management_uses_incidents():
    vols = {"incidents": 10}
    assert derive_activity_hours("Problem Management", 20, vols) == pytest.approx(10 * 600 / 60.0)


def test_derive_documentation_uses_servers_and_volumes():
    vols = {"alerts": 100, "incidents": 10, "service_requests": 25, "changes": 8}
    # Documentation ignores alerts by design
    expected = (20 * 30 + 10 * 120 + 25 * 15 + 8 * 120) / 60.0
    assert derive_activity_hours("Documentation & Knowledge Base", 20, vols) == pytest.approx(expected)


def test_derive_unknown_activity_is_zero():
    assert derive_activity_hours("Service Review Preparation", 20, {"incidents": 10}) == 0.0


def test_all_formula_activities_resolve():
    vols = {"alerts": 50, "incidents": 5, "service_requests": 12, "changes": 4}
    for name in ACTIVITY_FORMULAS:
        assert derive_activity_hours(name, 10, vols) >= 0.0


# ── Cost / price ──────────────────────────────────────────────────────────────

def test_delivery_cost_with_sla():
    dc = calc_total_delivery_cost(100000.0, 0.0, 5000.0, 2.0)
    assert dc["subtotal_before_sla"] == 105000.0
    assert dc["sla_provision"] == pytest.approx(2100.0)
    assert dc["total_delivery_cost"] == pytest.approx(107100.0)


def test_selling_price_margin():
    sp = calc_selling_price(100000.0, 20.0)
    assert sp["selling_price"] == pytest.approx(125000.0)
    assert sp["gross_profit"] == pytest.approx(25000.0)


def test_selling_price_margin_100_raises():
    with pytest.raises(ValueError):
        calc_selling_price(100000.0, 100.0)


# ── Role hours assembly (regression on exact numbers) ──────────────────────────

def test_assemble_role_hours_explicit_distribution():
    res = assemble_role_hours(
        {"L1": 10.0, "L2": 20.0, "L3": 30.0},
        {"Architect": 5.0, "SDM": 5.0, "SSDM": 0.0},
        patching_hours=10.0,
        patching_role="L2",
        additional_activities=[
            {"hours": 10.0, "dist": {"L1": 0, "L2": 70, "L3": 30, "Architect": 0, "SDM": 0, "SSDM": 0}},
            {"hours": 20.0, "dist": {"L1": 0, "L2": 0, "L3": 70, "Architect": 20, "SDM": 10, "SSDM": 0}},
        ],
        contingency_pct=10.0,
    )
    assert res["L1"] == pytest.approx(11.0, abs=0.05)
    assert res["L2"] == pytest.approx(40.7, abs=0.05)
    assert res["L3"] == pytest.approx(51.7, abs=0.05)
    assert res["Architect"] == pytest.approx(9.4, abs=0.05)
    assert res["SDM"] == pytest.approx(7.2, abs=0.05)
    assert res["SSDM"] == pytest.approx(0.0, abs=0.05)


# ── Rate-card resolution / location scoping ────────────────────────────────────

@pytest.fixture
def rate_card():
    return pd.DataFrame([
        {"country": "India", "location": "Pune",  "genus": "2.1-INFRAOPS", "hourly rate": 800, "rate currency": "INR"},
        {"country": "India", "location": "Noida", "genus": "2.1-INFRAOPS", "hourly rate": 900, "rate currency": "INR"},
        {"country": "USA",   "location": "NYC",   "genus": "2.1-INFRAOPS", "hourly rate": 50,  "rate currency": "USD"},
    ])


def test_filter_rate_card_by_country_and_location(rate_card):
    assert len(filter_rate_card(rate_card, "India")) == 2
    assert len(filter_rate_card(rate_card, "India", "Pune")) == 1
    # Non-matching location is ignored gracefully (falls back to country scope)
    assert len(filter_rate_card(rate_card, "India", "Nowhere")) == 2


def test_resolve_role_rates_honours_location(rate_card):
    rates = resolve_role_rates(rate_card, {"L1": "2.1-INFRAOPS"}, "India", "Pune")
    assert rates["L1"] == 800
    rates = resolve_role_rates(rate_card, {"L1": "2.1-INFRAOPS"}, "India", "Noida")
    assert rates["L1"] == 900


def test_resolve_role_rates_converts_foreign_currency(rate_card):
    rates = resolve_role_rates(rate_card, {"L1": "2.1-INFRAOPS"}, "USA", "NYC", {"USD": 83.0})
    assert rates["L1"] == pytest.approx(50 * 83.0)


def test_resolve_role_rates_skips_unmapped(rate_card):
    rates = resolve_role_rates(rate_card, {"L1": None, "L2": "nonexistent"}, "India")
    assert rates == {}


# ── Transition & Onboarding planner cost ───────────────────────────────────────

def _planner(**over):
    p = {
        "enabled": True, "total_weeks": 4,
        "phases": [{"id": "p1", "name": "Assess", "weeks": 2},
                   {"id": "p2", "name": "KT", "weeks": 2}],
        "resources": [{"id": "a", "role": "L2", "count": 1}],
        "allocation": {"a": {1: 1.0, 2: 1.0, 3: 0.0, 4: 0.0}},
        "treatment": "one_time", "amortisation_months": 12,
    }
    p.update(over)
    return p


def test_transition_disabled_is_zero():
    out = calc_transition_cost(None, {"L2": 800})
    assert out["enabled"] is False and out["total"] == 0.0
    out = calc_transition_cost({"enabled": False}, {"L2": 800})
    assert out["total"] == 0.0


def test_transition_basic_total():
    # 1 × L2 × 40h × ₹800 for 2 weeks at 100% = 64,000
    out = calc_transition_cost(_planner(), {"L2": 800}, weekly_hours=40.0)
    assert out["total"] == pytest.approx(64000.0)
    assert out["one_time_fee"] == pytest.approx(64000.0)
    assert out["net_charged"] == pytest.approx(64000.0)


def test_transition_count_and_utilisation_multiply():
    p = _planner(resources=[{"id": "a", "role": "L2", "count": 3}],
                 allocation={"a": {1: 0.5}})
    out = calc_transition_cost(p, {"L2": 800}, weekly_hours=40.0)
    assert out["total"] == pytest.approx(3 * 0.5 * 40 * 800)  # 48,000


def test_transition_recurring_amortises():
    out = calc_transition_cost(_planner(treatment="recurring", amortisation_months=12),
                               {"L2": 800})
    assert out["monthly_recurring"] == pytest.approx(64000.0 / 12)
    assert out["net_charged"] == pytest.approx(64000.0)
    assert out["one_time_fee"] == 0.0


def test_transition_absorb_nets_to_zero():
    out = calc_transition_cost(_planner(treatment="absorb"), {"L2": 800})
    assert out["absorbed"] == pytest.approx(64000.0)
    assert out["net_charged"] == 0.0


def test_transition_per_phase_breakdown():
    out = calc_transition_cost(_planner(), {"L2": 800})
    # both worked weeks (1,2) fall in phase "Assess"
    assert out["per_phase"]["Assess"] == pytest.approx(64000.0)
    assert "KT" not in out["per_phase"]


def test_transition_ignores_weeks_past_total():
    p = _planner(total_weeks=2, allocation={"a": {1: 1.0, 2: 1.0, 3: 1.0}})
    out = calc_transition_cost(p, {"L2": 800})
    assert out["total"] == pytest.approx(2 * 40 * 800)  # week 3 dropped


def test_transition_handles_string_week_keys():
    # JSON round-trip stringifies the week keys
    p = _planner(allocation={"a": {"1": 1.0, "2": 1.0}})
    out = calc_transition_cost(p, {"L2": 800})
    assert out["total"] == pytest.approx(64000.0)


def test_transition_missing_rate_is_zero_cost():
    out = calc_transition_cost(_planner(), {})  # no rate for L2
    assert out["total"] == 0.0
    assert out["per_resource"][0]["rate_inr"] == 0.0


def test_transition_week_phase_map_sequential():
    m = transition_week_phase_map([{"name": "A", "weeks": 2}, {"name": "B", "weeks": 3}], 5)
    assert m == {1: "A", 2: "A", 3: "B", 4: "B", 5: "B"}
