# UX / UI Improvement Plan

Constraint: keep the existing **mint/teal + navy** theme. Applies to the in-app
screens, exported reports (Excel ×2, PDF), approval emails, and saved configs/imports.

## What already works (keep)
- Linear stepper (1→9) with status icons; pure calc pipeline behind it.
- Reusable callouts, metric cards, styled tables, validation pills.
- Cloud saves, approval flow, scale-to-zero hosting.

## Critical issues (prioritized)
- [ ] **Step 2 mega-table** (14 columns) — too dense, hard to fill.
- [ ] **Step 8 overload** — entry + dashboard + approval + what-if + exports on one page.
- [ ] **Two competing save systems** — cloud "Saved Calculations" vs file "Scenarios".
- [ ] **Jargon without guidance** — Genus, FTE, L1/L2/L3, Contingency, Buffer, Overhead, SLA.
- [ ] **Output inconsistency** — app / Excel / Editable Excel / PDF / email look different.
- [ ] **Weak validity feedback** — stepper shows position, not completeness; no pre-export review.
- [ ] **Fragile theming/contrast** — blanket sidebar white-text rule caused white-on-white.
- [ ] **No onboarding / empty states**.
- [ ] **Inconsistent input ergonomics** — units, alignment, headers vary.

## Workstreams
- **A. IA & flow:** split Step 8 → Costing inputs / Results & Export; move Compare out;
  sidebar grouping; plain step names + sub-captions; "Step X of 9".
- **B. Inputs:** Step 2/4 redesign (buffers behind a toggle; data-editor); units in labels;
  tooltips + glossary.
- **C. Visual system:** documented palette/spacing/type/components; CSS refactor for contrast (WCAG AA).
- **D. Feedback:** per-step validity badges; "Review & finalize" panel; real empty states.
- **E. Outputs:** shared report header + section order across app/Excel/PDF/email; PDF cover;
  branded email template; Excel cover + formatting + clearer names.
- **F. Saved configs:** richer list (project·version·date·author·price·status); load confirmation;
  JSON framed as secondary "share as file".
- **G. Language:** plain labels + expert terms in tooltips; glossary; sentence case.

## Phased roadmap
- [ ] **Phase 1 — Quick wins:** language/labels + tooltips + glossary; button/contrast
      consistency; sidebar grouping + clarify Saved-vs-file; section/metric polish.
- [ ] **Phase 2 — Flow:** split Step 8; move Compare out; stepper validity badges; review panel.
- [ ] **Phase 3 — Inputs:** Step 2 & Step 4 table redesign.
- [ ] **Phase 4 — Outputs:** shared header/section order; PDF cover; email HTML template; Excel polish.
- [ ] **Phase 5 — Design system:** documented tokens/components + CSS refactor.

Each phase ships as a tested, deployable increment.
