# Multi-Skill Estimation — Strategy & Design Record

> Status: **DESIGN APPROVED, NOT STARTED.** Captured 2026-06-30 from a multi-round
> discussion. This is the blueprint to build against. No code written yet.

## 1. Objective
Today the tool models **one tower**: a single pool of work split only by **level
(L1/L2/L3)** + shared overhead. Real support deals need **multiple skills** (Security,
Cloud, DevOps, Monitoring, Database, …), each with its own volumes, level mix, coverage and
effort. This feature adds a **Skill dimension**, so the unit of estimation becomes
**(skill × level)**, while keeping the existing single-tower flow intact.

## 2. Mental model
"**Skill" is an outer loop over today's engine.** For each skill we compute the current
model (ticket effort → role hours → FTE → cost), then **aggregate** across skills — with a
small set of **engagement-level** inputs shared across all skills, a **resource-sharing**
layer that pools staffing across skills, and a **hide** layer for A/B versions.
**Single-skill = exactly one skill** ("General"), so the existing app is the N=1 case.

## 3. Locked decisions (from the discussion)
| Topic | Decision |
|---|---|
| **Mode** | **Single (default)** vs **Multi-skill**. Chosen on **Manual → Start afresh**. **Chat stays unchanged** (single-tower) for now; Chat multi-skill is a later phase. |
| **Rates** | **Two genus families: InfraOps & CloudOps**, same bands, different rates. Each **skill is tagged** InfraOps or CloudOps; level→band→rate resolves from that family. Not a rate per skill. |
| **Skill setup screen** | Captures **name + genus + active levels (L1/L2/L3 any combo) + coverage model + whether it has an Architect**, all up front. |
| **Overhead** | **Architect = per skill**; **SDM = one, engagement-level**. (SSDM removed entirely in v1.34.) |
| **Coverage** | **Per skill** (e.g. Monitoring 24×7, DevOps 8×5, Security 16×5). |
| **Contingency / SLA / margin / monthly hrs / utilisation** | **Engagement-level** (applied on the aggregate). |
| **Patching & additional activities** | **Per skill** (a skill may have activities but no patching). |
| **Volumetrics** | Per skill, **direct** (enter per skill) or **allocate** (enter overall total per category, split across skills by % or count; severity split then happens inside each skill). |
| **Resource sharing** | **L2 / L3 / Architect** can be **shared** across user-defined skill groups (free-form, e.g. Server Mgmt + VMware share one L3 + one Architect). **L1 is always per-skill.** Sharing **pools hours before FTE** so per-skill min-0.5 rounding doesn't over-staff. |
| **Hide / show** | Non-destructive include toggle at **skill** and **(skill, level/Architect)** granularity; hidden items drop out of totals; **export/save** the post-hide estimate as its own version → hold **A/B versions** for RFP comparison; unhide restores. |
| **Backward compatibility** | The existing single-tower flow must be **untouched**; single = "1 skill". |
| **Editing** | Skills can be added / removed / re-tagged mid-estimate. |

## 4. Two open questions — recommended defaults (confirm when building)
1. **Coverage for a shared resource** (a pooled L2/L3/Architect spans skills that may have
   different coverage). **Recommendation:** a sharing group must share **one coverage model**
   (validated at group creation); if skills differ, they can't be pooled. Simple, unambiguous.
   *(Fallback option: pooled resource takes the group's **highest** coverage.)*
2. **Genus consistency in a sharing group.** **Recommendation:** a sharing group must be
   **within one genus family** (InfraOps *or* CloudOps) — you wouldn't pool an InfraOps and a
   CloudOps person (different rate family). Enforced at group creation.

## 5. Data model (session schema)
```
estimation_mode: "single" | "multi"           # default "single"

skills: [                                       # multi mode only
  {
    id, name,
    genus_category: "InfraOps" | "CloudOps",
    active_levels: subset of ["L1","L2","L3"],
    has_architect: bool,
    coverage_model: "8×5" | "24×7" | "16×5" | "Custom" | ...,
    visible: bool,                              # hide whole skill
    level_visible: {L1,L2,L3,Architect: bool},  # hide a level within a skill
    architect_pct: float,                       # per-skill architect overhead %
    workload: { alerts|service_requests|incidents|changes:
                  { sublabel: {count, minutes, L1_pct, L2_pct, L3_pct, L*_buffer} } },
    patching: { included, num_servers, method, ... } | null,
    activities: [ {name, hours, dist{level}} ],
  }, ...
]

volume_allocation: {                            # used when not entering per-skill directly
  mode: "direct" | "allocate",
  totals: { category: total },
  split:  { category: { skill_id: pct_or_count } },
}

resource_sharing: [                             # pooling groups (L2/L3/Architect only)
  { id, level, skill_ids: [...], genus_category, coverage_model }
]

# Engagement-level (largely as today): contingency_pct, sla_*, target_margin_pct,
# monthly_working_hours, productive_utilisation, sdm_overhead_pct, reporting_currency, fx
```
Single mode reuses today's flat keys unchanged; multi mode uses `skills[]`. The engine
adapts a single-mode estimate to a one-element skill list internally.

## 6. Engine changes (`compute_full_model`)
Generalise to multi-skill (single = 1 skill):
1. **Per visible skill, per visible level:** ticket effort (count×min/60 × level% × buffer)
   + patching (if any) + activities; apply **engagement contingency**; per-skill **Architect**
   hours = `architect_pct × skill operational effort`. Keep **per-skill, per-level hours** for
   visibility.
2. **Engagement total effort** = Σ visible skills. **SDM** hours = `sdm% × engagement total`.
3. **Pool** hours by `resource_sharing` group for **L2/L3/Architect** (dedicated = group of
   one); **L1** per skill; **SDM** = one engagement resource.
4. **FTE per pooled resource** = `ceil0.5(pooled_hours / productive_hours × coverage)` where
   coverage = the group's model; min-0.5 applies to the **pool**, not per skill.
5. **Cost per pooled resource** = `FTE × monthly_hours × rate(genus family, band)`.
6. **Aggregate** → delivery cost → **engagement** SLA/margin → price. **Hidden** skills/levels
   contribute 0.
Returns per-skill / per-level breakdowns **and** the engagement roll-up.

## 7. Rates (Step 7)
- Rate card gains a **CloudOps** family beside the existing **InfraOps** one (same bands,
  different rates).
- Per skill, its **genus family** is set at setup; per active level the **band** resolves the
  rate from that family. A "Cloud L2" prices off CloudOps 2.3; a "Security L2" off InfraOps 2.3.

## 8. Entry / UI flow
```
Email gate → Mode gate: Chat | Manual
  Chat → unchanged (single-tower)
  Manual → Resume modal (unchanged)
     Resume draft → loads saved mode (single or multi)
     Start afresh → chooser: [ Single / default ] | [ Multi-skill ]
        Single → today's Step 1+ flow, untouched
        Multi  → Skill-setup screen (add skills; per skill: name, genus InfraOps/CloudOps,
                 active levels, coverage, has-Architect) → per-skill input steps →
                 resource-sharing setup → engagement costing → dashboard
```
- Multi adds a **skill-setup screen** + per-skill steps + a **resource-sharing** screen.
- Engagement-level steps (contingency, SLA, margin, SDM, monthly hrs) are the same in both modes.
- **Hide/show** controls live on the per-skill/level views and the dashboard; mode + skills +
  hide-state are saved with the draft/version.

## 9. Outputs
- **Dashboard:** per-skill breakdown (L1/L2/L3 effort, FTE, cost) + engagement roll-up; only
  **visible** elements counted. A/B compare view for hidden-vs-full versions.
- **Excel workbook:** gains a **skill dimension** (per-skill sections + totals), hide-aware,
  still recalc-verified to the engine.
- **Transition:** per-skill resources by **(skill, level/Architect)** per phase/week, priced at
  the skill's family rate; SDM a single engagement resource.

## 10. Backward compatibility
- `estimation_mode` defaults to **single**; the existing flow, engine path, drafts, versions,
  exports and tests are unchanged for single mode.
- Multi is additive; single is the N=1 specialisation of the same engine.

## 11. Phased build sequence
1. **Engine + data model**: multi-skill loop, per-skill effort/FTE/cost, **single = 1 skill**
   backward-compat; unit tests. (No UI yet.)
2. **Mode toggle + skill-setup screen + per-skill workload** (direct + allocate) + per-skill
   coverage / patching / activities / Architect.
3. **InfraOps/CloudOps rate families** in Step 7 + rate card.
4. **Resource sharing** (pooling groups, L2/L3/Architect) + the two validation rules (§4).
5. **Hide/show** + A/B export/compare.
6. **Per-skill transition**.
7. **Dashboard + Excel** per-skill (extend the existing recalc-verified workbook).

## 12. Risks / notes
- **Largest change to date** — touches data model, the pure engine, every input step,
  outputs, transition, and the Excel replica. Mitigated by the unified-engine approach and
  phasing.
- Keep the **engine pure and recalc-verifiable** so the Excel replica stays 100% accurate.
- Watch FTE rounding semantics: min-0.5 must apply to the **pooled** resource, not per skill
  (that's the whole point of sharing).
- Allocation UX: keep "overall → per-skill split" simple (per-category, % or count).

## 13. Next step
On go-ahead, start **Phase 1 (engine + data model, single = 1 skill)** behind the mode flag,
with tests, then proceed phase by phase. Confirm the two §4 defaults at that point.
