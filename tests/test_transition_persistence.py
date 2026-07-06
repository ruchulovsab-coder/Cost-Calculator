"""Transition Strategy + Transition Cost config must round-trip with the estimate.

serialize_inputs()/load_scenario() only touch keys registered in _get_initial_state(),
so these tests guard that the multi-mode transition inputs are registered (and that the
date coercion used on resume is correct). Regression guard for the bug where a saved or
shared estimate reopened with the Transition tabs blank.
"""
from datetime import date, datetime

from modules.state.session_manager import _build_initial_state, coerce_transition_date

# The genuine user inputs the two tabs write (not derived/ephemeral keys).
TRANSITION_INPUT_KEYS = [
    "transition_start", "transition_go_live", "transition_customer_tz",
    "transition_sequencing", "transition_incumbent", "transition_phase_cfg",
    "transition_alloc", "transition_sdm_alloc",
]


def test_transition_keys_registered_in_initial_state():
    s = _build_initial_state()
    for k in TRANSITION_INPUT_KEYS:
        assert k in s, f"{k} missing from initial state — it won't round-trip on save/share"


def test_transition_defaults_are_neutral():
    s = _build_initial_state()
    assert s["transition_start"] is None and s["transition_go_live"] is None
    assert s["transition_customer_tz"] == "EST"
    assert s["transition_sequencing"] == "Sequential"
    assert s["transition_incumbent"] is True
    assert s["transition_phase_cfg"] == []
    assert s["transition_alloc"] == {} and s["transition_sdm_alloc"] == {}


def test_derived_keys_not_persisted():
    # These recompute on render and must not be treated as saved inputs.
    s = _build_initial_state()
    for k in ("transition_duration_weeks", "_transition_seq_prev",
              "transition_cost_result", "transition_workbook"):
        assert k not in s


def test_coerce_transition_date_from_iso_string():
    assert coerce_transition_date("2026-08-05") == date(2026, 8, 5)


def test_coerce_transition_date_passes_through_date():
    d = date(2026, 8, 5)
    assert coerce_transition_date(d) is d


def test_coerce_transition_date_from_datetime():
    assert coerce_transition_date(datetime(2026, 8, 5, 9, 30)) == date(2026, 8, 5)


def test_coerce_transition_date_bad_or_empty():
    assert coerce_transition_date("") is None
    assert coerce_transition_date("not-a-date") is None
    assert coerce_transition_date(None) is None
    assert coerce_transition_date(12345) is None
