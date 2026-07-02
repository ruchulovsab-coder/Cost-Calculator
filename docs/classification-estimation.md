# Classification-driven estimation (multi mode)

Goal: **more accurate, less manual**. Instead of hand-entering the L1/L2/L3 split per category,
the user enters a **monthly total** per category; the estimator seeds the **classification mix**,
**handling time (AHT)** and the **recommended L1/L2/L3 routing pyramid** from industry defaults,
which the user can adjust. The engine uses the **user-approved** values. Deterministic and
explainable — **not** an LLM. Single mode is unaffected.

## Taxonomy (config/settings.py — `MS_CLASSIFICATIONS`)
| Category | Classifications |
|---|---|
| Alerts | Critical / High / Medium / Low / **Informational** |
| Incidents | **P1 / P2 / P3 / P4** |
| Service Requests | Standard / Normal / Complex |
| Changes | Standard / Normal / **Emergency** (ITIL change types) |

Notes: incidents use **priority P1–P4**; changes use ITIL types (not "Major", which is a high-risk
Normal change); **Informational alerts default to 0 effort** (noise/suppressed events, not work).

## Defaults (⚠️ TUNE these — they are industry seeds, one place to edit)
- `MS_DEFAULT_DIST` — volume % per classification (each category sums to 100).
- `MS_DEFAULT_AHT` — minutes/ticket per classification (P1=180 … P4=20; Informational=0).
- `MS_DEFAULT_ROUTING` — recommended L1/L2/L3 split per classification (P1→L2/L3 heavy; routine→L1).

Changing a default only changes the **starting point** for new input — it never alters a saved
estimate (approved values are stored on the estimate).

## Data model
`skill.workload = { category: { classification: {count, minutes, L1_pct, L2_pct, L3_pct} } }`
(per-class count = category total × share%). The engine already sums multiple sub-rows per category
(single mode's severities work the same way), so **no engine-logic change** — the active-levels
renormalization still applies per row.

## Migration (safe / numerically neutral)
Legacy `{ "All": {...} }` rows (and demo-seed data) are split across classifications by
`MS_DEFAULT_DIST`, **keeping the same AHT and L1/L2/L3 split**, so total effort and per-level hours
are unchanged (rounding remainder absorbed into the first class). `ensure_ms_workload()` runs in
`multi_state` (compute + compare) and in the Workload UI, and is idempotent. Saved estimates
(e.g. TataMotor) self-heal on next open with identical numbers; users then refine per-class AHT/mix.
Test: `test_classification_migration_is_neutral`.

## Touchpoints changed
`config/settings.py` (defaults) · `modules/state/multi_state.py` (migration + `skill_volumes` sums
classes) · `modules/inputs/multi_skill.py::_render_skill_tickets` (total + classification-mix UI) ·
`modules/outputs/multi_excel_export.py` (Workload sheet adds a Classification column).

## Status & roadmap
- **Step 1 (this):** classification input + per-class AHT + **default** routing (recommended pyramid
  as deterministic seed) + Informational=0 + safe migration.
- **Step 2 (next):** context-aware **routing recommender** (vary by support window / AHT band) with an
  explainability line; **Architect recommender** (skill archetype + complexity); "reset to recommended".
- **Step 3:** estimate-level **Lock** (read-only toggle).
- **Deferred:** generic recommendation framework (rule-of-three); "enter total → auto-distribute" is
  already the input model here.
Deterministic throughout; LLM reserved for optional narration only.
