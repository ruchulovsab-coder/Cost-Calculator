"""End-to-end tests for compute_full_model and session defaults."""
import pytest

from config.settings import ALL_ROLES
from modules.calculations.engine import compute_full_model
from modules.state.session_manager import _build_initial_state


@pytest.fixture
def state():
    s = _build_initial_state()
    s["role_rates_inr"] = {"L1": 800, "L2": 1200, "L3": 1800,
                           "Architect": 2500, "SDM": 2200, "SSDM": 2800}
    s["coverage_model"] = "24×7"
    return s


def test_initial_state_defaults():
    s = _build_initial_state()
    assert s["workload_totals"] == {"alerts": 100, "service_requests": 25, "incidents": 10, "changes": 8}
    assert s["patching_included"] == "Yes"
    assert s["delivery_country"] == "India"
    assert s["reporting_currency"] == "INR"
    # Sub-counts reconcile to declared totals
    for cat, total in s["workload_totals"].items():
        assert sum(r["count"] for r in s[cat].values()) == total


def test_compute_full_model_shape(state):
    m = compute_full_model(state)
    for key in ("total_effort", "role_hours", "fte_result", "resource_costs",
                "cost_result", "price_result", "total_fte"):
        assert key in m
    assert set(m["role_hours"]) == set(ALL_ROLES)


def test_compute_full_model_price_exceeds_delivery(state):
    m = compute_full_model(state)
    assert m["total_effort"] > 0
    assert m["total_resource_cost"] > 0
    assert m["price_result"]["selling_price"] > m["cost_result"]["total_delivery_cost"]


def test_compute_full_model_currency_conversion(state):
    state["reporting_currency"] = "USD"
    state["exchange_rates"] = {"USD": 83.0}
    m = compute_full_model(state)
    inr = m["price_result"]["selling_price"]
    assert m["selling_price_converted"] == pytest.approx(inr / 83.0)


def test_compute_full_model_default_reporting_is_inr(state):
    m = compute_full_model(state)
    assert m["reporting_currency"] == "INR"
    assert m["selling_price_converted"] == pytest.approx(m["price_result"]["selling_price"])


def test_compute_full_model_zero_volume_is_safe():
    s = _build_initial_state()
    for cat in ("alerts", "service_requests", "incidents", "changes"):
        for row in s[cat].values():
            row["count"] = 0
    s["patching_included"] = "No"
    s["additional_activities"] = []
    s["role_rates_inr"] = {r: 1000 for r in ALL_ROLES}
    m = compute_full_model(s)
    assert m["total_effort"] == 0.0
    # No effort -> no FTE -> no cost
    assert m["total_resource_cost"] == 0.0
