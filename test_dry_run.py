"""Dry run test — verifies all features work without errors."""
import sys, os
os.environ['STREAMLIT_SERVER_HEADLESS'] = 'true'

# Simulate Streamlit session state
class FakeSessionState(dict):
    def __getattr__(self, key):
        try: return self[key]
        except KeyError: raise AttributeError(key)
    def __setattr__(self, key, val):
        self[key] = val

import streamlit as st
st.session_state = FakeSessionState()

# 1. Test settings
from config.settings import DEFAULT_CURRENCIES, CURRENCY_SYMBOLS, ALL_ROLES
assert DEFAULT_CURRENCIES == ["INR"], f"FAIL: currencies = {DEFAULT_CURRENCIES}"
assert list(CURRENCY_SYMBOLS.keys()) == ["INR"], f"FAIL: symbols = {CURRENCY_SYMBOLS}"
print("1.  Settings: INR only                      OK")

# 2. Test session defaults
from modules.state.session_manager import _build_initial_state
state = _build_initial_state()
assert state["workload_totals"]["alerts"] == 100
assert state["workload_totals"]["service_requests"] == 25
assert state["workload_totals"]["incidents"] == 10
assert state["workload_totals"]["changes"] == 8
print("2.  Default volumes (100/25/10/8)            OK")

assert state["patching_included"] == "Yes"
assert state["num_servers"] == 50
assert state["patching_method"] == "Tool-Based"
assert state["manual_effort_per_server"] == 30.0
assert state["patch_failure_rate"] == 20.0
print("3.  Patching defaults (Yes/50/Tool/30/20)    OK")

assert state["rate_card_currency"] == "INR"
assert state["delivery_country"] == "India"
assert state["exchange_rates"] == {}
print("4.  Currency/Location defaults (INR/India)   OK")

# 3. Test workload sections
alerts = state["alerts"]
total_alert_count = sum(v["count"] for v in alerts.values())
assert total_alert_count == 100, f"FAIL: alert total = {total_alert_count}"
sr = state["service_requests"]
total_sr = sum(v["count"] for v in sr.values())
assert total_sr == 25, f"FAIL: SR total = {total_sr}"
inc = state["incidents"]
total_inc = sum(v["count"] for v in inc.values())
assert total_inc == 10, f"FAIL: incidents total = {total_inc}"
chg = state["changes"]
total_chg = sum(v["count"] for v in chg.values())
assert total_chg == 8, f"FAIL: changes total = {total_chg}"
print("5.  Workload sections pre-populated          OK")

# 4. Test engine functions
from modules.calculations.engine import (
    calc_resource_cost, convert_rate_to_inr, calc_productive_hours,
    calc_coverage_multiplier, calc_fte, calc_total_delivery_cost,
    calc_selling_price, calc_patching_effort, assemble_role_hours
)

# convert_rate_to_inr
r = convert_rate_to_inr(500.0, "INR", {"INR": 1.0})
assert r == 500.0
r2 = convert_rate_to_inr(500.0, None, {"INR": 1.0})
assert r2 == 500.0
r3 = convert_rate_to_inr(500.0, "None", {"INR": 1.0})
assert r3 == 500.0
r4 = convert_rate_to_inr(500.0, "", {"INR": 1.0})
assert r4 == 500.0
print("6.  convert_rate_to_inr (INR/None/empty)     OK")

# FTE
role_hours = {"L1": 80, "L2": 40, "L3": 20, "Architect": 10, "SDM": 10, "SSDM": 5}
prod_hrs = calc_productive_hours(160, 75)
mult = calc_coverage_multiplier("8x5", 8, 5)
fte = calc_fte(role_hours, prod_hrs, mult)
assert all(role in fte for role in ALL_ROLES)
print("7.  FTE calculation                          OK")

# Resource cost (FTE-based)
rates_inr = {"L1": 400, "L2": 600, "L3": 900, "Architect": 1200, "SDM": 1100, "SSDM": 1500}
genus = {"L1": "G1", "L2": "G2", "L3": "G3", "Architect": "G4", "SDM": "G5", "SSDM": "G6"}
rc = calc_resource_cost(fte, 160.0, rates_inr, genus)
total_cost = sum(v["cost_inr"] for v in rc.values())
assert total_cost > 0, f"FAIL: total cost = {total_cost}"
for role in ALL_ROLES:
    assert "fte" in rc[role], f"FAIL: missing fte for {role}"
    assert "billed_hours" in rc[role], f"FAIL: missing billed_hours for {role}"
    assert "rate_inr" in rc[role], f"FAIL: missing rate_inr for {role}"
    assert "cost_inr" in rc[role], f"FAIL: missing cost_inr for {role}"
print(f"8.  Resource cost (total={total_cost:,.0f} INR)    OK")

# Patching — Tool-Based: hours = ceil(50 * 20%) = 10 failed * remediation_min / 60
patch = calc_patching_effort(True, 50, "Tool-Based", 30, 20, 30)
assert patch["hours"] > 0, f"FAIL: patch hours = {patch['hours']}"
print(f"9.  Patching effort ({patch['hours']:.1f} hrs)             OK")

# Delivery cost
dc = calc_total_delivery_cost(total_cost, 0.0, 5000.0, 2.0)
assert dc["total_delivery_cost"] > 0
print("10. Total delivery cost                      OK")

# Selling price
sp = calc_selling_price(dc["total_delivery_cost"], 20.0)
assert sp["selling_price"] > dc["total_delivery_cost"]
print("11. Selling price (with margin)              OK")

# 4b. Test assemble_role_hours with custom additional activities distribution
ticket_role_hours = {"L1": 10.0, "L2": 20.0, "L3": 30.0}
overhead_role_hours = {"Architect": 5.0, "SDM": 5.0, "SSDM": 0.0}
patch_hours = 10.0
patching_role = "L2"
additional_activities = [
    {
        "name": "Scheduled Maintenance",
        "hours": 10.0,
        "custom": False,
        "dist": {"L1": 0.0, "L2": 70.0, "L3": 30.0, "Architect": 0.0, "SDM": 0.0, "SSDM": 0.0}
    },
    {
        "name": "Problem Management",
        "hours": 20.0,
        "custom": False,
        "dist": {"L1": 0.0, "L2": 0.0, "L3": 70.0, "Architect": 20.0, "SDM": 10.0, "SSDM": 0.0}
    }
]
contingency_pct = 10.0

res_hours = assemble_role_hours(
    ticket_role_hours,
    overhead_role_hours,
    patch_hours,
    patching_role,
    additional_activities,
    contingency_pct
)

assert abs(res_hours["L1"] - 11.0) < 0.01, f"L1: {res_hours['L1']}"
assert abs(res_hours["L2"] - 40.7) < 0.01, f"L2: {res_hours['L2']}"
assert abs(res_hours["L3"] - 51.7) < 0.01, f"L3: {res_hours['L3']}"
assert abs(res_hours["Architect"] - 9.4) < 0.01, f"Architect: {res_hours['Architect']}"
assert abs(res_hours["SDM"] - 7.2) < 0.01, f"SDM: {res_hours['SDM']}"
assert abs(res_hours["SSDM"] - 0.0) < 0.01, f"SSDM: {res_hours['SSDM']}"
print("11b. Role hours assembly (explicit dist)     OK")

# 5. Check no undefined variable references in key files
import ast
undefined_issues = []
for fpath in [
    "modules/inputs/steps_6_7.py",
    "modules/outputs/dashboard.py",
    "modules/outputs/excel_export.py",
]:
    with open(fpath, "r", encoding="utf-8") as f:
        source = f.read()
    # Check for rate_currency as a bare name (not in string/comment)
    for i, line in enumerate(source.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if "rate_currency" in stripped and "session_state" not in stripped and '"INR"' not in stripped and "= " not in stripped:
            # This might be a bare reference to the old variable
            if "f\"" in stripped or "f'" in stripped:
                undefined_issues.append(f"  {fpath}:{i}: {stripped}")

if undefined_issues:
    print("12. Undefined variable scan                  FAIL")
    for issue in undefined_issues:
        print(issue)
else:
    print("12. Undefined variable scan                  OK")

print()
print("=" * 50)
if not undefined_issues:
    print("ALL 12 TESTS PASSED - DRY RUN SUCCESSFUL")
else:
    print("SOME TESTS FAILED")
print("=" * 50)
