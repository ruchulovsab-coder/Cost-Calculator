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
    "demo_monitoring": {
        "alerts": (800, 10, 100, 0, 0),
        "service_requests": (200, 15, 100, 0, 0),
        "incidents": (100, 20, 100, 0, 0),
    },
    "demo_cloudops": {
        "service_requests": (300, 30, 0, 70, 30),
        "incidents": (120, 60, 0, 50, 50),
        "changes": (80, 90, 0, 40, 60),
    },
    "demo_devops": {
        "service_requests": (150, 45, 0, 60, 40),
        "changes": (200, 60, 0, 50, 50),
        "incidents": (60, 90, 0, 40, 60),
    },
    "demo_linux": {
        "service_requests": (250, 25, 0, 70, 30),
        "incidents": (90, 75, 0, 50, 50),
        "changes": (120, 45, 0, 60, 40),
    },
}


def _skill(sid, name, genus, levels, coverage, arch_pct):
    has_arch = arch_pct > 0
    return {
        "id": sid, "name": name, "genus_category": genus, "active_levels": list(levels),
        "has_architect": has_arch, "architect_pct": float(arch_pct or 5.0),
        "coverage_model": coverage, "visible": True, "level_visible": {},
        "role_buffers": {"L1": 20.0, "L2": 20.0, "L3": 20.0, "Architect": 0.0},
        "workload": {cat: {"All": {"count": c, "minutes": m,
                                   "L1_pct": l1, "L2_pct": l2, "L3_pct": l3}}
                     for cat, (c, m, l1, l2, l3) in _WORKLOADS[sid].items()},
        "patching": None, "activities": [],
    }


def _demo_skills():
    # Monitoring: L1-only 24×7 (no architect). Cloud/DevOps/Linux: L2+L3 with 25% architect;
    # Cloud Ops on 16×5, the rest on 24×7. Two InfraOps + two CloudOps rate families.
    return [
        _skill("demo_monitoring", "Monitoring", "InfraOps", ["L1"], "24×7", 0),
        _skill("demo_cloudops", "Cloud Operations", "CloudOps", ["L2", "L3"], "16×5", 25),
        _skill("demo_devops", "DevOps", "CloudOps", ["L2", "L3"], "24×7", 25),
        _skill("demo_linux", "Linux Administration", "InfraOps", ["L2", "L3"], "24×7", 25),
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
