"""
TEMPORARY testing aid — representative multi-skill sample-data seeding.

TODO (REMOVE BEFORE PRODUCTION RELEASE)
--------------------------------------
This module pre-populates a realistic multi-skill AMS scenario so testers don't have
to re-enter data after every deployment. It is gated by config.settings.DEMO_SEED_DATA.

To revert:
  • Quick disable : set DEMO_SEED_DATA = False in config/settings.py
  • Full removal  : delete this file, the DEMO_SEED_DATA flag, and the seed_demo_data()
                    import/call in main.py.
Tracked in the "demo-seed-temporary" memory note.

Behaviour: seeds ONLY empty session fields (never overwrites user input), runs once per
session, and does NOT change the estimation mode (the user still picks Single/Multi as
normal — seeded skills simply appear pre-filled when Multi is chosen). Scope: the
multi-skill flow only (single-mode steps and Chat are not seeded).
"""
import streamlit as st

from config.settings import DEMO_SEED_DATA

# workload tuple = (count, minutes/ticket, L1_pct, L2_pct, L3_pct); level splits sum to 100%.
_WORKLOADS = {
    # Monitoring is an L1-only alert-watching function: alerts only (100), no SRs /
    # incidents / changes, and 100% L1 (no L2/L3).
    "demo_monitoring": {
        "alerts": (100, 10, 100, 0, 0),
    },
    # Volume caps (per user): service requests < 20, incidents 6–9, change requests 5–7.
    "demo_cloudops": {
        "service_requests": (18, 30, 0, 70, 30),
        "incidents": (8, 60, 0, 50, 50),
        "changes": (6, 90, 0, 40, 60),
    },
    "demo_devops": {
        "service_requests": (15, 45, 0, 60, 40),
        "changes": (7, 60, 0, 50, 50),
        "incidents": (9, 90, 0, 40, 60),
    },
    "demo_linux": {
        "service_requests": (12, 25, 0, 70, 30),
        "incidents": (6, 75, 0, 50, 50),
        "changes": (5, 45, 0, 60, 40),
    },
}


def _skill(sid, name, genus, levels, coverage, arch_pct, patching=None, activities=None):
    has_arch = arch_pct > 0
    return {
        "id": sid, "name": name, "genus_category": genus, "active_levels": list(levels),
        "has_architect": has_arch, "architect_pct": float(arch_pct or 5.0),
        "coverage_model": coverage, "visible": True, "level_visible": {},
        "role_buffers": {"L1": 20.0, "L2": 20.0, "L3": 20.0, "Architect": 0.0},
        "workload": {cat: {"All": {"count": c, "minutes": m,
                                   "L1_pct": l1, "L2_pct": l2, "L3_pct": l3}}
                     for cat, (c, m, l1, l2, l3) in _WORKLOADS[sid].items()},
        "patching": patching, "activities": activities or [],
    }


def _demo_skills():
    # Monitoring: L1-only 24×7 (no architect). Cloud/DevOps/Linux: L2+L3 with 25% architect;
    # Cloud Ops on 16×5, the rest on 24×7. Two InfraOps + two CloudOps rate families.
    return [
        _skill("demo_monitoring", "Monitoring", "InfraOps", ["L1"], "24×7", 0),
        _skill("demo_cloudops", "Cloud Operations", "CloudOps", ["L2", "L3"], "16×5", 25),
        _skill("demo_devops", "DevOps", "CloudOps", ["L2", "L3"], "24×7", 25),
        _skill("demo_linux", "Linux Administration", "InfraOps", ["L2", "L3"], "24×7", 25,
               patching={"included": True, "num_servers": 20, "method": "Manual",
                         "manual_effort_per_server": 45.0, "auto_effort_per_server": 30.0,
                         "error_rate_pct": 10.0, "patching_role": "L2"},
               activities=[{"name": "Scheduled Maintenance", "hours": 10.0, "auto": True,
                            "dist": {"L2": 70.0, "L3": 30.0, "Architect": 0.0}}]),
    ]


def seed_demo_data():
    """Populate the representative multi-skill scenario into empty session fields.
    Idempotent per session; gated by DEMO_SEED_DATA; never overwrites existing values."""
    if not DEMO_SEED_DATA or st.session_state.get("_demo_seeded"):
        return
    ss = st.session_state
    if not ss.get("skills"):
        ss["skills"] = _demo_skills()
    # Delivery location is unset by default (country defaults to India) — fill it so the
    # Rates & Cost tab resolves grades → INR out of the box. Only sets if still unset.
    ss.setdefault("delivery_location", "Noida")
    ss["_demo_seeded"] = True


def _split_for(levels) -> tuple:
    """Representative L1/L2/L3 split (sums to 100) spread across a skill's ACTIVE levels
    so every level a skill uses gets some ticket work."""
    active = [l for l in ("L1", "L2", "L3") if l in (levels or [])] or ["L2"]
    weights = {"L1": 0.5, "L2": 0.3, "L3": 0.2}
    tot = sum(weights[l] for l in active)
    split = {l: round(weights[l] / tot * 100) for l in active}
    split[active[0]] += 100 - sum(split.values())   # absorb rounding into the first level
    return split.get("L1", 0), split.get("L2", 0), split.get("L3", 0)


def demo_fill_skill(sk: dict) -> dict:
    """TEMPORARY testing aid — pre-fill a newly-added skill's workload with representative
    volumes across its active levels, so testers skip manual entry for each new skill while
    DEMO_SEED_DATA is on. Gated by the flag; only fills when the skill has no workload yet
    (never overwrites). Volumes honour the caps: SR<20, incidents 6–9, changes 5–7. No
    alerts here: monitoring alerts are the central Monitoring skill's landing zone for the
    whole estate, so other skills only get SR / incidents / changes. Revert with the flag."""
    if not DEMO_SEED_DATA or sk.get("workload"):
        return sk
    l1, l2, l3 = _split_for(sk.get("active_levels") or ["L1", "L2", "L3"])
    sk["workload"] = {
        cat: {"All": {"count": c, "minutes": m, "L1_pct": l1, "L2_pct": l2, "L3_pct": l3}}
        for cat, (c, m) in (("service_requests", (15, 30)), ("incidents", (8, 60)), ("changes", (6, 60)))
    }
    return sk
