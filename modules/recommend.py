"""
Deterministic, explainable recommendations for the multi-skill estimator.

NOT AI — these are transparent rules that produce a *seed* value plus a plain-language
rationale. The engine always uses the user-approved values, never the recommendation
directly. Reproducible (same inputs → same output) so estimates stay defensible.
See docs/classification-estimation.md.
"""
from config.settings import MS_DEFAULT_ROUTING, MS_CLASSIFICATIONS

_LEVELS = ("L1", "L2", "L3")
_CAT_KEYS = ("alerts", "service_requests", "incidents", "changes")


def recommend_routing(cat: str, cls: str, active_levels) -> tuple:
    """Recommended L1/L2/L3 split for a classification, **renormalised onto the skill's
    active levels** (an inactive level's share redistributes proportionally to the active
    ones, so what the user sees sums to 100 across the levels this skill actually uses and
    matches what the engine computes). Returns (l1, l2, l3, rationale)."""
    base = MS_DEFAULT_ROUTING.get(cat, {}).get(cls, (100, 0, 0))
    weights = dict(zip(_LEVELS, base))
    active = [l for l in _LEVELS if l in (active_levels or [])] or ["L1"]
    s = sum(weights[l] for l in active)
    out = {l: 0.0 for l in _LEVELS}
    if s > 0:
        for l in active:
            out[l] = round(weights[l] / s * 100.0)
    else:
        out[active[0]] = 100.0
    out[active[0]] += 100 - sum(out[l] for l in active)   # absorb rounding → exactly 100
    top = max(active, key=lambda l: out[l])
    folded = [l for l in _LEVELS if l not in active and weights[l] > 0]
    why = f"{cls}: routine work stays on L1, higher priority escalates — skews to {top}"
    if folded:
        why += f"; {'/'.join(folded)} inactive, its share folded into active levels"
    return out["L1"], out["L2"], out["L3"], why


# Suggested Architect % by skill archetype (first keyword match wins). Deterministic seed.
_ARCH_RULES = [
    (("monitor", "noc", "command centre", "command center", "l1 support"), 0),
    (("soc", "security operation", "siem"), 30),
    (("security", "iam", "identity", "vulnerabilit", "pam"), 25),
    (("cloud", "aws", "azure", " gcp", "kubernetes", "container", "openshift"), 22),
    (("devops", "ci/cd", "cicd", "pipeline", "sre", "platform eng"), 18),
    (("middleware", "platform", "app support", "application"), 15),
    (("database", "dba", "sql", "oracle", "postgres", "mongo"), 15),
    (("network", "firewall", "router", "switch", "lan", "wan", "load balanc"), 12),
]
_ARCH_DEFAULT = 10


def recommend_skill_pyramid(skill: dict):
    """Aggregate recommended L1/L2/L3 % for a whole skill: for each classification take the
    recommended routing (folded onto active levels) and weight it by that classification's
    effort (count × AHT), so a P1-heavy skill leans L3 and a request-heavy skill leans L1.
    Returns ({'L1','L2','L3'} summing to 100 across active levels, data_driven: bool). When
    no volume is entered yet, falls back to an unweighted average so the guidance still
    shows. Returns (None, False) only if there are no active ticket levels."""
    active = skill.get("active_levels") or []
    wl = skill.get("workload", {}) or {}
    acc = {"L1": 0.0, "L2": 0.0, "L3": 0.0}
    tot = 0.0
    for cat in _CAT_KEYS:
        for cls, row in (wl.get(cat, {}) or {}).items():
            eff = float(row.get("count", 0) or 0) * float(row.get("minutes", 0) or 0)
            if eff <= 0:
                continue
            l1, l2, l3, _ = recommend_routing(cat, cls, active)
            acc["L1"] += l1 * eff; acc["L2"] += l2 * eff; acc["L3"] += l3 * eff
            tot += eff
    data_driven = tot > 0
    if not data_driven:                      # no volume yet → unweighted taxonomy average
        for cat in _CAT_KEYS:
            for cls in MS_CLASSIFICATIONS.get(cat, []):
                l1, l2, l3, _ = recommend_routing(cat, cls, active)
                acc["L1"] += l1; acc["L2"] += l2; acc["L3"] += l3; tot += 1
    if tot <= 0:
        return None, False
    pyr = {k: round(v / tot) for k, v in acc.items()}
    act = [l for l in _LEVELS if l in active] or list(_LEVELS)
    pyr[max(act, key=lambda l: pyr[l])] += 100 - (pyr["L1"] + pyr["L2"] + pyr["L3"])  # → exactly 100
    return pyr, data_driven


def recommend_architect(skill: dict) -> tuple:
    """Suggested Architect % from the skill's archetype (name keywords, then rate family).
    Returns (pct, rationale). Deterministic; the user overrides."""
    name = (skill.get("name") or "").lower()
    for keys, pct in _ARCH_RULES:
        if any(k in name for k in keys):
            return pct, f"“{skill.get('name')}” looks like {keys[0].strip()}-type work → ~{pct}% architect"
    genus = skill.get("genus_category", "") or ""
    pct = 20 if genus == "CloudOps" else _ARCH_DEFAULT
    return pct, f"no specific archetype matched — {genus or 'default'} baseline ~{pct}%"
