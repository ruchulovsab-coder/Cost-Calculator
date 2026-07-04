"""Compose the framework catalog + timeline solver + the estimate's skills into a proposal-ready
TransitionPlan. PURE read-only over the estimate model; never mutates it."""
from __future__ import annotations

from typing import Any, Dict, List

from . import catalog as C
from .timeline import solve_timeline


def default_phase_config() -> List[Dict[str, Any]]:
    """Seed the editable per-phase config from the framework defaults."""
    return [{"key": p["key"], "name": p["name"], "band": p["band"],
             "duration_weeks": p["default_weeks"], "included": True,
             "overlap_lead_weeks": 0, "milestone": p.get("milestone"),
             "ongoing": bool(p.get("ongoing"))} for p in C.PHASES]


def validate_raci(raci: List[Dict[str, Any]]) -> List[str]:
    """Every activity must have exactly one Accountable (A) and only known roles."""
    problems = []
    known = set(C.ALL_ROLES)
    for row in raci:
        cells = row.get("raci", {})
        a = [r for r, v in cells.items() if v == "A"]
        if len(a) != 1:
            problems.append(f"{row['activity']}: expected exactly one Accountable, found {len(a)}")
        for r in cells:
            if r not in known:
                problems.append(f"{row['activity']}: unknown role '{r}'")
    return problems


def _skill_plans(model: Dict[str, Any]) -> List[Dict[str, Any]]:
    plans = []
    for sid, ps in (model.get("per_skill", {}) or {}).items():
        name = ps.get("name") or sid
        levels = [l for l in ("L1", "L2", "L3", "Architect")
                  if float((ps.get("fte_by_level", {}) or {}).get(l, 0) or 0) > 0]
        stages = {stage: [t.format(skill=name) for t in tmpls]
                  for stage, tmpls in C.SKILL_STAGE_TEMPLATES.items()}
        plans.append({
            "skill": name, "levels": levels, "coverage": ps.get("coverage_model", ""),
            "knowledge_transition": stages["knowledge_transition"],
            "shadow": stages["shadow"], "reverse_shadow": stages["reverse_shadow"],
            "stabilization": stages["stabilization"],
            "exit_criteria": [t.format(skill=name) for t in C.SKILL_EXIT_CRITERIA],
            "signoff_criteria": [t.format(skill=name) for t in C.SKILL_SIGNOFF_CRITERIA],
        })
    return plans


def build_transition_plan(model: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
    """model = compute_multi_skill_model(...) output; config = TransitionConfig dict.
    Deterministic: same model + config → identical plan."""
    phases = config.get("phases") or default_phase_config()
    tl = solve_timeline(
        config.get("start_date"), phases,
        sequencing=config.get("sequencing", "Sequential"),
        overall_weeks=config.get("duration_weeks"),
        go_live=config.get("go_live_date"),
        incumbent_present=config.get("incumbent_present", True))

    included_keys = {r["key"] for r in tl["rows"]}
    phase_activities = [{"key": r["key"], "name": r["name"], "band": r["band"],
                         "start": r["start"], "end": r["end"], "milestone": r["milestone"],
                         **C.PHASE_DETAIL.get(r["key"], {})} for r in tl["rows"]]
    deliverables = [{"phase": r["name"], "key": r["key"],
                     "deliverables": C.PHASE_DETAIL.get(r["key"], {}).get("deliverables", []),
                     "exit": C.PHASE_DETAIL.get(r["key"], {}).get("exit", []),
                     "milestone": r["milestone"]} for r in tl["rows"]]
    raci = [row for row in C.RACI if row["phase"] in included_keys]

    return {
        "customer_tz": config.get("customer_tz", "EST"),
        "foundation": C.FOUNDATION,
        "start": tl["start"], "span_weeks": tl["span_weeks"],
        "timeline": tl["rows"], "milestones": tl["milestones"],
        "phase_activities": phase_activities,
        "skill_plans": _skill_plans(model),
        "raci": raci, "roles_customer": C.ROLES_CUSTOMER, "roles_nagarro": C.ROLES_NAGARRO,
        "deliverables": deliverables,
        "best_practice_artifacts": C.BEST_PRACTICE_ARTIFACTS,
        "advisories": tl["advisories"] + validate_raci(raci),
    }
