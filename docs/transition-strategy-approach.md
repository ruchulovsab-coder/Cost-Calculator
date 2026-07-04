# Transition Strategy — approach

A proposal-ready, ITIL-aligned **Transition Strategy** derived from the estimate and a small set
of date inputs. Estimation/proposal artifact only — **not** a transition PM/tracking tool.

## Baseline
Encodes `assets/transition framework.png` ("Operational Establishment & Stabilization") as **data**
in `modules/transition/catalog.py` — 7 ITIL-aligned phases, milestones M1–M4 + Go-Live, per-phase
detail, Customer/Nagarro RACI, per-skill activity templates, and the continuous "Knowledge
Management, Tools & Processes" foundation. Aligns to the framework; does not invent a new one.

## Phases (7, peer, per the framework)
Assessment & Discovery · Initiation & Planning (M1) · Knowledge Transition (M2) · Shadow Support
(M3) · Reverse Shadow Support (Go-Live sign-off) · Stabilization (M4) · Steady State & CSI.
SLA/penalty ramp: no SLA in Shadow/Reverse-Shadow → KPIs/SLAs measured, penalties waived in
Stabilization → full SLA + penalties at Steady State.

## Core principles (same as the Shift Plan)
1. **Read-only projection** of `compute_multi_skill_model` output; never writes back; regenerates on
   change. One-way dependency enforced by `test_engine_does_not_import_transition`.
2. **Deterministic-first, LLM-optional.** The timeline solver + catalog own everything factual
   (dates, activities, deliverables, gates, RACI). No LLM in this cut. A future LLM layer may only
   enrich prose on a validated plan (deliverables/gates/RACI/dates immutable).
3. **Timeline reconciliation** is the crux: per-phase durations + sequencing (Sequential/Overlap) +
   overall duration + Go-Live can conflict → solver resolves the timeline from durations and surfaces
   conflicts as **advisories** (never silently corrects). RACI validity (exactly one Accountable per
   activity) is enforced and tested.

## Inputs (few)
Transition start, overall duration (weeks), Go-Live, customer TZ, sequencing (Sequential/Overlap),
incumbent-present toggle, and a per-phase duration/include/overlap editor (seeded from the framework
defaults). Everything else — skills, level mix, coverage — is pulled from the estimate.

## Architecture
```
modules/transition/catalog.py   # the framework AS DATA (phases, RACI, activity templates, gates)
modules/transition/timeline.py  # PURE solver: dates, overlap, milestones, Go-Live gate, validation
modules/transition/builder.py   # build_transition_plan(model, config) -> TransitionPlan (composes)
modules/outputs/transition_excel.py  # Timeline/Phase Activities/Skill-wise/RACI/Deliverables sheets
modules/inputs/multi_skill.py   # tab "7 · Transition" -> _render_transition() (Gantt + sections)
tests/test_transition.py        # solver, RACI validity, determinism, no-mutation, dependency guard
```

## Output (in the tab + Excel)
Dynamic Gantt (phases + M1–M4 + Go-Live, band-coloured, recomputes on input change) · Phase
Activities (objectives/deliverables/entry/exit/risks/dependencies/responsibilities) · Skill-wise
Plan (KT/Shadow/Reverse-Shadow/Stabilization + exit/sign-off per estimated skill) · RACI (Customer +
Nagarro) · Deliverables & Quality Gates · Best-practice artifacts · Advisories.

## Phased roadmap
- **P0+P1 (done, this cut)** — timeline solver + framework catalog + tab (Gantt, phase activities,
  skill-wise plan, RACI, deliverables, advisories) + Excel appendix. No LLM.
- **P2** — richer per-skill detail, readiness checklists/quality gates, RAID register & comms/
  governance artifacts; refine content per real RFPs.
- **P3** — PowerPoint proposal appendix.
- **P4** — optional LLM prose enrichment (validator-gated).
- **P5 (no redesign)** — transition costing (separate priced line, never perturbs run-rate),
  wave-based transition, holiday/blackout calendars.

Note: this is a **first cut** to build on — content and structure will be fine-tuned iteratively.
