"""
AI Team Optimizer — core (pure, deterministic; unit-tested).

Given a multi-skill estimate, propose how to shrink the team by SHARING senior
resources (Architect / L3, and L2 to a degree) across technically-adjacent skills,
WITHOUT compromising coverage. The engine already knows how to pool — this module
decides *what* to pool and quantifies the effect by re-running the engine:

    AI/heuristics propose the sharing structure  →  engine computes the numbers.

Rules (v1):
  • Adjacency from config.SKILL_ADJACENCY_GROUPS (skill name → canonical token).
  • Pool only within one genus family (InfraOps / CloudOps).
  • Shareable levels: Architect, L3 (freely — no coverage multiplier), L2 (only when
    it still saves; L2 carries a coverage multiplier so cross-window pooling rarely
    helps). L1 is never pooled.
  • Coverage of a pool = the widest window among its members (coverage never drops).
  • Only suggest when it saves FTE AND the pooled resource's utilisation ≤ ceiling.

The optional AI layer (ai_narrative) only *explains/prioritises* — it never changes
the numbers, so results stay recalc-verifiable.
"""
from typing import Any, Dict, List, Optional

from config.settings import (
    SKILL_CANONICAL_KEYWORDS, SKILL_ADJACENCY_GROUPS, OPTIMIZER_UTIL_CEILING_PCT,
    COVERAGE_MODELS,
)
from modules.calculations.engine import compute_multi_skill_model

SHAREABLE_LEVELS = ("Architect", "L3", "L2")   # L1 never


def canonical_skill(name: str) -> Optional[str]:
    """Map a free-text skill name to a canonical token via keyword match (else None)."""
    s = (name or "").lower()
    for token, kws in SKILL_CANONICAL_KEYWORDS.items():
        if token in s or any(kw in s for kw in kws):
            return token
    return None


def _adjacent(a: str, b: str) -> bool:
    ca, cb = canonical_skill(a), canonical_skill(b)
    if not ca or not cb:
        return False
    if ca == cb:
        return True
    return any({ca, cb} <= grp for grp in SKILL_ADJACENCY_GROUPS)


def _clusters(skill_ids: List[str], names: Dict[str, str]) -> List[List[str]]:
    """Connected components of adjacent skills (only components of size ≥ 2)."""
    parent = {sid: sid for sid in skill_ids}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i, a in enumerate(skill_ids):
        for b in skill_ids[i + 1:]:
            if _adjacent(names[a], names[b]):
                parent[find(a)] = find(b)
    groups: Dict[str, List[str]] = {}
    for sid in skill_ids:
        groups.setdefault(find(sid), []).append(sid)
    return [g for g in groups.values() if len(g) >= 2]


def _widest_coverage(models: List[str]) -> str:
    """The coverage model with the most weekly hours (so a pool never under-covers)."""
    best, best_h = "8×5", -1.0
    for m in models:
        h = (COVERAGE_MODELS.get(m, {}) or {}).get("weekly_hours") or 0
        if h > best_h:
            best, best_h = m, h
    return best


def _pool_family(cluster, level, by_id, rates_by_cat) -> str:
    """Rate family for a (possibly cross-family) pool: the members' family if uniform,
    else the family with the higher band rate at this level (conservative costing)."""
    fams = {by_id[s].get("genus_category") for s in cluster}
    if len(fams) == 1:
        return next(iter(fams))
    best, best_rate = None, -1.0
    for f in fams:
        rate = float((rates_by_cat.get(f, {}) or {}).get(level, 0) or 0)
        if rate > best_rate:
            best, best_rate = f, rate
    if best is not None and best_rate > 0:
        return best
    from collections import Counter
    return Counter(by_id[s].get("genus_category") for s in cluster).most_common(1)[0][0]


def _rationale(level, names, cov, fte_saved, cost_saved, key_person, cross_family=False) -> str:
    who = " + ".join(names)
    bridge = " (a senior spanning both rate families)" if cross_family else ""
    core = (f"{who} are technically adjacent, so one {level} pool{bridge} (covering {cov}) can serve "
            f"all of them — saving {fte_saved:.1f} FTE"
            + (f" (~₹{cost_saved:,.0f}/mo)" if cost_saved > 0 else "") + ".")
    if key_person:
        core += " ⚠ Single shared resource — watch key-person risk / leave cover."
    return core


def optimize_team(state: Dict[str, Any],
                  ceiling_pct: float = OPTIMIZER_UTIL_CEILING_PCT,
                  share_levels=SHAREABLE_LEVELS,
                  cross_family: bool = False) -> Dict[str, Any]:
    """Return {'baseline': model, 'suggestions': [...], 'level_notes': {...}} without applying.
    Each suggestion is an independent, non-overlapping pooling opportunity. When cross_family
    is True, Architect/L3 may pool across rate families (InfraOps ↔ CloudOps) — the pool is
    priced at the higher-rate family; L2 always stays within one family (shift/coverage work)."""
    base_state = {**state, "resource_sharing": []}
    baseline = compute_multi_skill_model(base_state)
    rates_by_cat = state.get("rates_by_category", {}) or {}
    skills = [s for s in (state.get("skills", []) or []) if s.get("visible", True)]
    by_id = {s["id"]: s for s in skills}
    names = {s["id"]: (s.get("name") or s["id"]) for s in skills}

    suggestions: List[Dict[str, Any]] = []
    level_notes: Dict[str, Dict[str, int]] = {}
    for level in share_levels:
        eligible = [sid for sid, ps in baseline["per_skill"].items()
                    if ps["role_hours"].get(level, 0.0) > 1e-9 and sid in by_id]
        cross_ok = cross_family and level in ("Architect", "L3")
        if cross_ok:
            partitions = {"*": eligible}                     # one bucket, families ignored
        else:
            partitions = {}
            for sid in eligible:
                partitions.setdefault(by_id[sid].get("genus_category"), []).append(sid)
        clusters_found = suggested = rejected_ceiling = rejected_nosave = 0
        for _key, sids in partitions.items():
            for cluster in _clusters(sids, names):
                clusters_found += 1
                pool_fam = _pool_family(cluster, level, by_id, rates_by_cat)
                is_cross = len({by_id[s].get("genus_category") for s in cluster}) > 1
                cov = _widest_coverage([by_id[s].get("coverage_model", "8×5") for s in cluster])
                gid = f"opt_{level}_{'_'.join(cluster)}"
                grp = {"id": gid, "level": level, "skill_ids": list(cluster),
                       "genus_category": pool_fam, "coverage_model": cov}
                cand = compute_multi_skill_model({**state, "resource_sharing": [grp]})
                fte_saved = baseline["total_fte"] - cand["total_fte"]
                pooled = next((r for r in cand["resources"] if r.get("key") == f"group:{gid}"), None)
                if fte_saved <= 1e-9 or not pooled or pooled["final_fte"] <= 0:
                    rejected_nosave += 1
                    continue
                fill = pooled["raw_fte"] / pooled["final_fte"] * 100.0
                if fill > ceiling_pct + 1e-9:
                    rejected_ceiling += 1
                    continue  # too loaded — would risk coverage/quality
                suggested += 1
                cost_saved = baseline["total_resource_cost"] - cand["total_resource_cost"]
                fte_before = sum(baseline["per_skill"][s]["breakdown"][level]["fte_staffed"]
                                 for s in cluster)
                key_person = pooled["final_fte"] < 1.0 and len(cluster) >= 2
                suggestions.append({
                    "id": gid, "level": level, "skill_ids": list(cluster),
                    "skill_names": [names[s] for s in cluster], "genus": pool_fam,
                    "coverage_model": cov, "group": grp, "cross_family": is_cross,
                    "fte_before": fte_before, "fte_after": pooled["final_fte"],
                    "fte_saved": fte_saved, "cost_saved": max(cost_saved, 0.0),
                    "fill_pct": fill, "key_person_risk": bool(key_person),
                    "rationale": _rationale(level, [names[s] for s in cluster], cov,
                                            fte_saved, max(cost_saved, 0.0), key_person, is_cross),
                })
        level_notes[level] = {"eligible": len(eligible), "clusters": clusters_found,
                              "suggested": suggested, "rejected_ceiling": rejected_ceiling,
                              "rejected_nosave": rejected_nosave}
    suggestions.sort(key=lambda x: (x["fte_saved"], x["cost_saved"]), reverse=True)
    return {"baseline": baseline, "suggestions": suggestions, "level_notes": level_notes}


def apply_optimization(state: Dict[str, Any], groups: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Recompute the model with the chosen sharing groups applied."""
    return compute_multi_skill_model({**state, "resource_sharing": list(groups or [])})


# ── Optional AI narration (Groq) — explains/prioritises only, never changes maths ──
def ai_available() -> bool:
    try:
        from modules.llm.chat_assist import llm_configured
        return llm_configured()
    except Exception:
        return False


def ai_narrative(skill_names: List[str], suggestions: List[Dict[str, Any]],
                 totals: Dict[str, float], context: str = "") -> Dict[str, str]:
    """Ask Groq for a short executive summary of the optimization + any *advisory*
    cross-skill ideas the deterministic map may have missed. `context` is optional
    free-text constraints from the user (e.g. 'security must stay dedicated'). Returns
    {'summary': str} or {'error': str}. Never alters the computed suggestions."""
    try:
        from modules.llm.chat_assist import llm_configured, model_id
        if not llm_configured():
            return {"error": "AI narration isn't configured (GROQ_API_KEY not set)."}
        import os
        from groq import Groq
        lines = "; ".join(
            f"{'+'.join(s['skill_names'])} @ {s['level']} → save {s['fte_saved']:.1f} FTE"
            for s in suggestions) or "no pooling opportunities found"
        ctx = f" The delivery lead added these constraints/context: \"{context.strip()}\"." if context.strip() else ""
        prompt = (
            "You are an AMS staffing optimization advisor. Skills in this engagement: "
            f"{', '.join(skill_names)}. A deterministic optimizer proposed these resource-sharing "
            f"moves (Architect/L3/L2 pooled across adjacent skills): {lines}. Baseline team = "
            f"{totals.get('fte_before', 0):.1f} FTE; optimized = {totals.get('fte_after', 0):.1f} FTE."
            f"{ctx} In 3-4 sentences, give an executive rationale a delivery lead can trust: why these "
            "pairings make sense, the coverage/key-person caveat, and (advisory only) any adjacent "
            "skills that could also share seniors. Honour any stated constraints. Be concrete and "
            "concise. Plain text, no markdown."
        )
        client = Groq(api_key=os.environ["GROQ_API_KEY"].strip())
        resp = client.chat.completions.create(
            model=model_id(),
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3, max_tokens=400,
        )
        return {"summary": (resp.choices[0].message.content or "").strip()}
    except Exception as e:
        return {"error": f"AI request failed: {e}"}
