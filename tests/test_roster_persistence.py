"""Shift Plan / Roster config must round-trip with the estimate.

serialize_inputs()/load_scenario() only touch keys registered in _get_initial_state(),
so these tests guard that the roster inputs are registered. Regression guard for the bug
where a saved or shared estimate reopened with the Shift Plan reset to defaults (the same
bug class that was fixed for the Transition tabs — roster was missed until now).
"""
from modules.state.session_manager import _build_initial_state

# The genuine user inputs the Shift Plan tab writes (not derived/ephemeral widget keys).
ROSTER_INPUT_KEYS = [
    "roster_strategy", "roster_customer_tz", "roster_delivery_tz",
    "roster_bh_start", "roster_bh_end", "roster_shift_len", "roster_prefs",
]


def test_roster_keys_registered_in_initial_state():
    s = _build_initial_state()
    for k in ROSTER_INPUT_KEYS:
        assert k in s, f"{k} missing from initial state — it won't round-trip on save/share"


def test_roster_defaults_are_neutral():
    s = _build_initial_state()
    assert s["roster_strategy"] == "Balanced"
    assert s["roster_customer_tz"] == "EST"
    assert s["roster_delivery_tz"] == "IST"
    assert s["roster_bh_start"] == "09:00"
    assert s["roster_bh_end"] == "17:00"
    assert s["roster_shift_len"] == 8
    assert s["roster_prefs"] == {}


def test_roster_widget_keys_not_persisted():
    # The *_w widget keys and per-skill widgets recompute on render and must not be saved.
    s = _build_initial_state()
    for k in ("roster_customer_tz_w", "roster_delivery_tz_w", "roster_shift_len_w",
              "roster_strategy_w"):
        assert k not in s
