# Shift Plan / Roster Designer — approach

A proposal-ready **coverage & shift plan** derived from the final multi-skill estimate. It
demonstrates *how* the proposed team delivers the required coverage. It is **not** a workforce
management / HR / scheduling / attendance / payroll system.

## Core principles
1. **Read-only projection.** The roster consumes `compute_multi_skill_model(...)` output and
   never writes back. No circular dependency: the engine/`multi_state` must not import
   `modules.roster` (enforced by `tests/test_roster.py::test_engine_does_not_import_roster`).
   If the estimate changes, the roster simply regenerates.
2. **Deterministic-first, AI-optional.** The core is a rule-based scheduler (same model+config →
   identical plan). No LLM in v1. A future AI layer may only *narrate/label/rank* a plan the
   deterministic validator has already accepted — it must never compute feasibility. This
   matches the product guardrail (recommenders are deterministic, not LLM).
3. **Reconciliation, not re-inflation.** The engine already multiplies L1/L2 FTE by the
   coverage multiplier (24×7 = 4.20) — that multiplier **is** the relief factor. So the roster
   does **not** add a second relief factor. Deployable whole heads = **⌈delivered FTE⌉** per
   skill×level; the delta (seats − billed FTE) is shown transparently and never changes price.

## Shift model (v1, "Balanced")
- **L1/L2** are coverage roles → seats spread across the daily coverage window, split into
  ~shift-length blocks (24h → 3, 16h → 2, 8h → 1). Window placement for non-24×7 skills follows
  the per-skill preference (Business / Non-Business / Custom).
- **L3/Architect** are not coverage-inflated by the engine → business hours + on-call/escalation
  outside it (not spread across nights).
- Every shift renders in **both** customer-local and delivery-local time (dual clock).
- **Advisories** (informational, never affect commercials): flag when seats < shift blocks, and
  when a 24×7 desk has < 5 seats for sustainable rotation.

## Inputs (few, on the tab)
Customer TZ, delivery/offshore TZ, business hours (customer local), shift length, and a per-skill
coverage preference (with Business-Hours default; override only exceptions). Everything else is
pulled from the estimate (skills, active levels, coverage model, FTE).

## Time zones
v1 uses **fixed UTC offsets** for preset zones (EST/CST/MST/PST/GMT/CET/EET/IST/SGT/AEST). Shift
windows are abstract time-of-day ranges, not dated instants, so a fixed offset is predictable and
defensible. **DST / IANA calendars are a documented future extension.**

## Architecture
```
modules/roster/scheduler.py    # PURE: build_roster(model, config) -> RosterPlan. No Streamlit/LLM.
modules/outputs/roster_excel.py# RosterPlan -> themed Excel appendix (values, not a recalc model).
modules/inputs/multi_skill.py  # tab "6 · Shift Plan" -> _render_roster() (config + tables + export).
tests/test_roster.py           # determinism, reconciliation, dependency guard, window placement.
```

## Data model
- **RosterConfig** (session_state, `roster_*` keys, self-healing defaults): strategy, customer_tz,
  delivery_tz, business_start/end, shift_length_h, coverage_prefs `{skill_id: {mode, start?, end?}}`.
- **RosterPlan** (returned by `build_roster`): strategy, customer_tz, delivery_tz, business_hours,
  `shifts[]` (skill, level, shift, customer/delivery window, days, seats, on_call, note),
  `reconciliation[]` (skill, level, coverage, fte, seats, delta), `advisories[]`, `totals{}`.
- Seats are **anonymous personas**, never named people (keeps it out of WFM scope). Named
  resources, holidays, labour rules, multi-location, follow-the-sun are additive later.

## Phased roadmap
- **P0 (done)** — FTE→seats reconciliation principle (⌈FTE⌉, delta shown; no double-count).
- **P1 (done, on `testing`)** — deterministic Balanced scheduler + Shift Plan tab (dual-clock grid,
  reconciliation, advisories) + Excel appendix export. No AI.
- **P2** — Cost-Optimized & Max-Coverage strategies; PowerPoint proposal appendix; richer manual
  override with live re-validation.
- **P3** — optional AI *narration* layer (labels/explains/ranks accepted plans; deterministic
  validator gates anything it touches).
- **P4 (no redesign)** — holidays/regional calendars, labour rules, named resources, multi-location,
  follow-the-sun.
