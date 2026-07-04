"""Compose the framework catalog + timeline solver + the estimate's skills into a proposal-ready
TransitionPlan. PURE read-only over the estimate model; never mutates it."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from config.settings import SKILL_CANONICAL_KEYWORDS

from . import catalog as C
from .timeline import solve_timeline, fit_phases_to_go_live


def _skill_family(name: str) -> Optional[str]:
    """Map a free-text skill name → a transition technology family (else None).

    Reuses config.SKILL_CANONICAL_KEYWORDS (the AI Team Optimizer's classification) so
    family detection stays consistent across features; unknown names fall back to the
    generic activity templates."""
    s = (name or "").lower()
    for token, kws in SKILL_CANONICAL_KEYWORDS.items():
        if token in s or any(kw in s for kw in kws):
            return C.SKILL_TOKEN_TO_FAMILY.get(token)
    return None


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
        family = _skill_family(name)
        technical = C.FAMILY_STAGE_TEMPLATES.get(family, C.SKILL_STAGE_TEMPLATES)
        # Each stage = the common ITIL process backbone (same for every skill) + the
        # technology-specific technical activities for this skill's family.
        stages = {stage: [t.format(skill=name)
                          for t in (C.PROCESS_STAGE_ACTIVITIES.get(stage, [])
                                    + technical.get(stage, []))]
                  for stage in C.STAGE_KEYS}
        critical = (C.FAMILY_CRITICAL_CHECK.get(family) or C.GENERIC_CRITICAL_CHECK).format(skill=name)
        plans.append({
            "skill": name, "levels": levels, "coverage": ps.get("coverage_model", ""),
            "family": family, "family_label": C.FAMILY_LABELS.get(family, "General"),
            "knowledge_transition": stages["knowledge_transition"],
            "shadow": stages["shadow"], "reverse_shadow": stages["reverse_shadow"],
            "stabilization": stages["stabilization"],
            "exit_criteria": [t.format(skill=name) for t in C.SKILL_EXIT_CRITERIA],
            "signoff_criteria": [t.format(skill=name) for t in C.SKILL_SIGNOFF_CRITERIA],
            "family_critical_check": critical,
        })
    return plans


def build_transition_plan(model: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
    """model = compute_multi_skill_model(...) output; config = TransitionConfig dict.
    Deterministic: same model + config → identical plan."""
    phases = config.get("phases") or default_phase_config()
    seq = config.get("sequencing", "Sequential")
    # The start→Go-Live window drives the schedule: scale the phases up to Go-Live so Reverse-Shadow
    # ends on the configured Go-Live date (phases after Go-Live keep their durations). So changing
    # either the start or the Go-Live date reshapes the Gantt. No-op when Go-Live isn't set.
    phases = fit_phases_to_go_live(config.get("start_date"), phases, config.get("go_live_date"), seq)
    tl = solve_timeline(
        config.get("start_date"), phases, sequencing=seq,
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
        # Acceptance-gate templates (same for every skill; rendered per skill).
        "open_items_columns": C.OPEN_ITEMS_RISK_COLUMNS,
        "signoff_signatories": C.SIGNOFF_SIGNATORIES,
        "signoff_decision": C.SIGNOFF_DECISION,
        "advisories": tl["advisories"] + validate_raci(raci),
    }
