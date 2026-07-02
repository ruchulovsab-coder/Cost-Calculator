"""
Deterministic, explainable recommendations for the multi-skill estimator.

NOT AI — these are transparent rules that produce a *seed* value plus a plain-language
rationale. The engine always uses the user-approved values, never the recommendation
directly. Reproducible (same inputs → same output) so estimates stay defensible.
See docs/classification-estimation.md.
"""
from config.settings import MS_DEFAULT_ROUTING

_LEVELS = ("L1", "L2", "L3")


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
