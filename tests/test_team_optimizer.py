"""Tests for the AI Team Optimizer core (pure heuristics + engine re-run)."""
import pytest

from modules.optimize.team_optimizer import (
    canonical_skill, optimize_team, apply_optimization,
)


def _skill(sid, name, genus, levels, coverage, arch_pct, sr):
    return {
        "id": sid, "name": name, "genus_category": genus, "active_levels": levels,
        "has_architect": arch_pct > 0, "architect_pct": float(arch_pct),
        "coverage_model": coverage, "visible": True, "level_visible": {},
        "role_buffers": {"L1": 20.0, "L2": 20.0, "L3": 20.0, "Architect": 0.0},
        "workload": {"service_requests": {"All": {"count": sr, "minutes": 60,
                                                  "L1_pct": 0, "L2_pct": 50, "L3_pct": 50}}},
        "patching": None, "activities": [],
    }


def _state(skills):
    return {"skills": skills, "resource_sharing": [], "rates_by_category": {},
            "sdm_overhead_pct": 0.0, "sdm_rate_inr": 0.0, "contingency_pct": 10.0,
            "monthly_working_hours": 160.0, "productive_utilisation": 75.0,
            "fte_basis": "rounded", "custom_hours_per_day": 8, "custom_days_per_week": 5,
            "target_margin_pct": 20.0}


def test_canonical_matching():
    assert canonical_skill("Cloud Operations") == "cloud"
    assert canonical_skill("DevOps Engineering") == "devops"
    assert canonical_skill("Linux Administration") == "linux"
    assert canonical_skill("Totally Unknown Skill") is None


def test_adjacent_skills_pool_and_save():
    # Cloud + DevOps are adjacent (same family) with small L3/architect → poolable.
    skills = [
        _skill("s1", "Cloud Operations", "CloudOps", ["L2", "L3"], "24×7", 25, 10),
        _skill("s2", "DevOps", "CloudOps", ["L2", "L3"], "24×7", 25, 10),
    ]
    res = optimize_team(_state(skills))
    assert res["suggestions"], "expected at least one pooling suggestion"
    # every suggestion actually saves FTE, respects the fill ceiling, never touches L1
    for s in res["suggestions"]:
        assert s["fte_saved"] > 0
        assert s["fill_pct"] <= 85.0 + 1e-6
        assert s["level"] in ("Architect", "L3", "L2")
    applied = apply_optimization(_state(skills), [s["group"] for s in res["suggestions"]])
    assert applied["total_fte"] < res["baseline"]["total_fte"]


def test_non_adjacent_skills_not_pooled():
    # Linux (InfraOps) and Cloud (CloudOps) are neither adjacent nor same family.
    skills = [
        _skill("s1", "Linux Administration", "InfraOps", ["L2", "L3"], "24×7", 25, 10),
        _skill("s2", "Cloud Operations", "CloudOps", ["L2", "L3"], "24×7", 25, 10),
    ]
    res = optimize_team(_state(skills))
    assert res["suggestions"] == []


def test_l1_only_skill_has_no_suggestions():
    skills = [
        _skill("s1", "Cloud Operations", "CloudOps", ["L1"], "24×7", 0, 10),
        _skill("s2", "DevOps", "CloudOps", ["L1"], "24×7", 0, 10),
    ]
    # both L1-only → nothing shareable (L1 never pools)
    res = optimize_team(_state(skills))
    assert all(s["level"] != "L1" for s in res["suggestions"])
    assert res["suggestions"] == []
