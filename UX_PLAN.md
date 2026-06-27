# UX / UI Improvement Plan

Constraint: keep the existing **mint/teal + navy** theme. Applies to the in-app
screens, exported reports (Excel ×2, PDF), approval emails, and saved configs/imports.

## What already works (keep)
- Linear stepper (1→11) with status icons; pure calc pipeline behind it.
- Reusable callouts, metric cards, styled tables, validation pills.
- Cloud saves, approval flow, scale-to-zero hosting.
- **Email gate + per-user drafts** (v1.5–v1.6): autosave/resume, orphan cleanup, and a
  Nagarro-email sign-in that owns a user's drafts/versions (see below).

## Recently shipped (post design-system)
- **v1.5** — per-Customer/RFP **draft autosave + resume**; **orphan cleanup** via a
  token-gated email link; warn-on-close; "Prepared By" required.
- **v1.6** — **Nagarro email gate** unlocks the app and becomes the owner key for
  drafts/versions; the resume flow became a **blocking modal** (the sidebar list was
  removed); Prepared-By is the gate email (read-only on Step 1).
- **v1.7–v1.10** — Chat/Manual chooser, then conversational **Chat to estimate** (now on
  **Groq**, India rates).
- **v1.11–v1.24** — gate/contrast pass (branded, readable sign-in / mode / chat gates +
  logo; fixed dark-on-dark labels by using real Streamlit-1.58 testids); **re-version +
  re-approval when an approved estimate changes** (commits blocked until saved as a new
  draft); **save-then-approve** guidance + inline save; chat estimates get a real
  Customer/RFP name; **save a what-if as a new version**; approval **email figures** +
  **reviewer landing summary**; review link hidden from the requester (**resend** instead);
  Resume screen readable names + **per-draft delete**.

## Critical issues (prioritized)
- [x] **Step 2 mega-table** — replaced the faked 11-column grid with an
  `st.data_editor` (inputs) + read-only computed results table; buffers stay at the
  category heading; calculation contract unchanged.
- [ ] **Step 8 overload** — entry + dashboard + approval + what-if + exports on one page.
- [ ] **Two competing save systems** — cloud "Saved Calculations" vs file "Scenarios".
- [ ] **Jargon without guidance** — Genus, FTE, L1/L2/L3, Contingency, Buffer, Overhead, SLA.
- [ ] **Output inconsistency** — app / Excel / Editable Excel / PDF / email look different.
- [~] **Weak validity feedback** — stepper shows position, not completeness. A pre-decision
  **reviewer summary** now exists (v1.21); a full per-step completeness view is still open.
- [x] **Fragile theming/contrast** — blanket sidebar white-text rule caused white-on-white.
  Fixed in the v1.11–v1.24 gate/contrast pass (real Streamlit-1.58 testids; verified).
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
- **Phase 2 — Input ease + layout** (in progress):
  - [x] Select-all on focus (single click to overwrite any field)
  - [x] Hide +/- number steppers; right-align numeric values
  - [x] Scroll to top on page change
  - [x] Per-page **Reset this page** with confirmation dialog
  - [x] Step 2: single L1/L2/L3 buffer per category at the heading (replaces per-row buffer columns); 20% default
  - [x] Move rate card + coverage + delivery location to Step 1; rate-card grades as a collapsible table
  - [x] Split **Step 8 → 8 Costing inputs / 9 Results / 10 Approve & Export** (+ 11 Compare)
  - [ ] Units in every label; reduce mid-edit reruns; live running totals; reset-to-defaults per category
- **Phase 3 — Inputs:** [x] Step 2 → `st.data_editor`; [x] Step 4 → `st.data_editor`
  (dynamic add/delete rows; Auto/derived hours + role-% split; read-only validation table).
- [ ] **Phase 4 — Outputs:** shared header/section order; PDF cover; email HTML template; Excel polish.
- [ ] **Phase 5 — Design system:** documented tokens/components + CSS refactor.

Each phase ships as a tested, deployable increment.
