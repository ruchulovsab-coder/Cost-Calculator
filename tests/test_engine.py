"""Unit tests for the pure calculation engine."""
import math
import pandas as pd
import pytest

from config.settings import ALL_ROLES, COVERAGE_APPLICABLE_ROLES
from modules.calculations.engine import (
    convert_rate_to_inr, convert_to_currency, calc_productive_hours,
    calc_coverage_multiplier, calc_fte, ceil_half, calc_patching_effort,
    calc_total_delivery_cost, calc_selling_price, assemble_role_hours,
    calc_resource_cost, filter_rate_card, resolve_role_rates,
)


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
    assert calc_patching_effort(False, 50, "Manual", 30)["hours"] == 0.0


def test_patching_manual():
    res = calc_patching_effort(True, 50, "Manual", 30)
    assert res["hours"] == pytest.approx(50 * 30 / 60.0)  # 25.0


def test_patching_tool_based_uses_ceil_of_failures():
    # ceil(50 * 22%) = ceil(11.0) = 11 failed * 30 min / 60
    res = calc_patching_effort(True, 50, "Tool-Based", 0, 22.0, 30.0)
    assert res["failed_servers"] == math.ceil(50 * 0.22)
    assert res["hours"] == pytest.approx(res["failed_servers"] * 30 / 60.0)


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
