"""Tests for the deterministic recommendation helpers (modules/recommend.py)."""
from modules.recommend import recommend_routing, recommend_architect, recommend_skill_pyramid


def test_routing_all_levels_matches_base():
    l1, l2, l3, why = recommend_routing("incidents", "P1", ["L1", "L2", "L3"])
    assert (l1, l2, l3) == (10, 40, 50)          # base default, unchanged
    assert l1 + l2 + l3 == 100
    assert why


def test_routing_folds_inactive_level():
    # P1 base (10,40,50); with L3 inactive its share folds into L1/L2, summing to 100
    l1, l2, l3, _ = recommend_routing("incidents", "P1", ["L1", "L2"])
    assert l3 == 0
    assert l1 + l2 == 100
    assert (l1, l2) == (20, 80)


def test_routing_single_active_level():
    l1, l2, l3, _ = recommend_routing("incidents", "P1", ["L1"])
    assert (l1, l2, l3) == (100, 0, 0)


def test_routing_defaults_to_l1_when_none_active():
    l1, l2, l3, _ = recommend_routing("incidents", "P3", [])
    assert (l1, l2, l3) == (100, 0, 0)


def test_architect_archetypes():
    assert recommend_architect({"name": "Monitoring"})[0] == 0
    assert recommend_architect({"name": "SOC"})[0] == 30
    assert recommend_architect({"name": "Cloud Operations"})[0] == 22
    assert recommend_architect({"name": "DevOps"})[0] == 18
    assert recommend_architect({"name": "Network Management"})[0] == 12


def test_architect_falls_back_to_family():
    assert recommend_architect({"name": "Widget Ops", "genus_category": "CloudOps"})[0] == 20
    assert recommend_architect({"name": "Widget Ops", "genus_category": "InfraOps"})[0] == 10


def test_architect_returns_rationale():
    pct, why = recommend_architect({"name": "SOC"})
    assert isinstance(pct, int) and why


def test_skill_pyramid_data_driven_sums_100_on_active():
    # P1-heavy incident skill on L1/L2/L3 should lean L3 and sum to 100
    sk = {"active_levels": ["L1", "L2", "L3"],
          "workload": {"incidents": {"P1": {"count": 100, "minutes": 180, "L1_pct": 0, "L2_pct": 0, "L3_pct": 0}}}}
    pyr, data_driven = recommend_skill_pyramid(sk)
    assert data_driven is True
    assert pyr["L1"] + pyr["L2"] + pyr["L3"] == 100
    assert pyr["L3"] >= pyr["L1"]                      # P1 escalates upward


def test_skill_pyramid_folds_onto_active_levels():
    sk = {"active_levels": ["L1", "L2"],
          "workload": {"incidents": {"P1": {"count": 10, "minutes": 180, "L1_pct": 0, "L2_pct": 0, "L3_pct": 0}}}}
    pyr, _ = recommend_skill_pyramid(sk)
    assert pyr["L3"] == 0
    assert pyr["L1"] + pyr["L2"] == 100


def test_skill_pyramid_falls_back_without_volume():
    sk = {"active_levels": ["L1", "L2", "L3"], "workload": {}}
    pyr, data_driven = recommend_skill_pyramid(sk)
    assert data_driven is False
    assert pyr and pyr["L1"] + pyr["L2"] + pyr["L3"] == 100
