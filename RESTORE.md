# Restoring to a Stable Version

This repository is tagged at each stable release. A git tag is an immutable pointer
to that exact snapshot, so you can always return to it no matter what changes later.

## Stable versions (latest first)
- **`v1.41`** — *current stable.* **⚠️ TEMPORARY testing aid — sample-data seeding.** On startup,
  `modules/demo_seed.py::seed_demo_data()` (gated by `config.settings.DEMO_SEED_DATA`) pre-fills a
  representative **multi-skill AMS scenario** into **empty** session fields so testers skip manual
  entry after each deploy: 4 skills — **Monitoring** (InfraOps, L1, 24×7), **Cloud Operations**
  (CloudOps, L2/L3, 16×5, 25% architect), **DevOps** (CloudOps, L2/L3, 24×7, 25% arch), **Linux
  Administration** (InfraOps, L2/L3, 24×7, 25% arch) — each with realistic workload (level splits
  sum to 100%), plus `delivery_location="Noida"`. Seeds empty fields only (never overwrites user
  input), once per session, and does **not** change the estimation mode (user still picks
  Single/Multi). **MUST BE REVERTED BEFORE PRODUCTION** — set `DEMO_SEED_DATA = False`, or delete
  the flag + `modules/demo_seed.py` + the call in `main.py`. No behaviour change to the engine or
  single/Chat modes. 100 tests pass.
- **`v1.40`** — **Multi-skill — Phase 3: InfraOps/CloudOps rate families →
  cost & price.** New **4 · Rates & Cost** tab: loads the rate card (reusing the Step-1/7 loader +
  delivery-location selector + FX), then a **family × band genus-grade mapping** matrix
  (InfraOps/CloudOps × L1/L2/L3/Architect, + one engagement **SDM** grade). Each cell resolves to
  an **INR hourly rate** via `resolve_role_rates` (currency-converted). A skill prices off its
  family's bands; **CloudOps defaults to the same INFRAOPS grades** until a rate card carries
  `CLOUDOPS` grades (the sample/blob cards currently don't). Resolved `rates_by_category` +
  `sdm_rate_inr` feed `_build_multi_state` (was `{}`/0), so the engine now returns **per-skill
  monthly cost, engagement resource/delivery cost, target-margin selling price & gross profit** —
  all surfaced on the tab. UI-only wiring; **no engine change** (engine already consumed these).
  Single mode / Chat untouched. 100 tests pass. Next: allocate-mode volumes · per-skill patching/
  activities · resource-sharing UI · hide→export A/B · multi Excel.
- **`v1.39`** — **Multi-skill — Effort & FTE page restructured for calculation
  transparency.** The page now reads top-to-bottom: **① engagement inputs → ② Per-Level Effort
  Buffer** (skill × level matrix) **→ ③ Step-by-Step Build-up** (per-skill expanders: Raw → after
  Buffer → Final, hours + FTE + variance) **→ ④ Summary** (`Skill · Family · L1 · L2 · L3 ·
  Architect · Raw Hours · Final Hours`; per-level cols are Final and sum to Final Hours) **→ ⑤
  Overall Comparison** (engagement Raw → After-Buffer → Final with absolute + % variance per stage)
  **→ ⑥ Overall Team Summary** (two FTE matrices by skill × level — **Raw FTE exact** and **Final
  FTE staffed headcount** — each with an SDM row and grand totals; totals surfaced as Total Raw
  FTE / Total Final FTE exact / Total Final FTE headcount). UI-only reshape — no engine change; the
  team-matrix headcount grand total reconciles exactly to the engine's `total_fte`. Single mode /
  Chat untouched. 100 tests pass.
- **`v1.38`** — **Multi-skill — buffer moved to Effort & FTE tab (per skill ×
  per level, incl. Architect) + step-by-step effort/FTE build-up with variance.** The per-level
  buffer now lives on the **Effort & FTE** tab as a **skill × level matrix** (L1/L2/L3/Architect,
  each independently editable; the Workload tab is back to raw volume/split only). A new
  **Raw → Buffered → Final** build-up (per skill, in expanders) shows, for every level: Raw
  effort/FTE (no adjustments) → after the configured **Buffer** → **Final** after **Contingency**,
  plus **variance** (buffer impact, contingency impact, combined). Engine: `_skill_role_hours`
  now applies an **Architect buffer** (default 0, so single-skill parity with `compute_full_model`
  holds) and returns a per-level `breakdown` (raw/buffered/final hours + per-stage FTE) consumed by
  `compute_multi_skill_model`. Display/engine-additive only — single mode / Chat untouched. 100
  tests pass (2 new). Blueprint: `docs/multi-skill-strategy.md`.
- **`v1.37`** — **Multi-skill — per-level effort buffer made explicit +
  consistent effort dashboard.** The previously hidden 20% per-role buffer is now three editable
  inputs (**L1 / L2 / L3 buffer %**, default 20) on the multi-skill **Workload** tab, applied
  across all categories for that skill. The **Effort & FTE** table now adds up across its own row:
  the total column is **Staffed hrs** (= L1+L2+L3+Arch, what FTE is built from) with **Effort
  (pre-buffer)** shown alongside (raw tickets + contingency), so "total" no longer reads smaller
  than a level. Display/transparency change only — the engine (`compute_multi_skill_model`) is
  untouched and single mode / Chat are unaffected. 98 tests pass.
- **`v1.36`** — **Multi-skill — Phase 2 (first UI slice).** After **Manual →
  Start afresh** a **mode chooser** appears: **Single** (the classic stepper, unchanged & default)
  or **Multi-skill**. Multi opens a self-contained page (`modules/inputs/multi_skill.py`) with
  tabs: **Skills** (add/remove; per skill set name, InfraOps/CloudOps family, active levels,
  coverage model, Architect + %), **Workload** (per-skill volume / minutes / L1-L2-L3 split per
  category), and **Effort & FTE** (per-skill L1/L2/L3/Architect hours + FTE + engagement totals,
  via `compute_multi_skill_model`). Single mode and Chat are **untouched**. **Cost/price
  (InfraOps/CloudOps rate families) is Phase 3** — this slice shows effort + FTE. Resumed drafts
  keep their saved mode. 98 tests pass. Blueprint: `docs/multi-skill-strategy.md`.
- **`v1.35`** — **Multi-skill estimation — Phase 1 (engine + data model only,
  no UI, no behaviour change).** Adds the pure `engine.compute_multi_skill_model(state)` that
  estimates per **(skill × level)** and aggregates: per-skill effort/FTE/cost, **Architect per
  skill**, one engagement **SDM**, **per-skill coverage**, **InfraOps/CloudOps** band rates,
  **resource sharing** (L2/L3/Architect pool hours before FTE; L1 always per-skill), and
  **hide** (skill or level) excluded from totals. Verified that **a single skill reproduces the
  single-tower `compute_full_model`** (backward-compatible). Data-model defaults added
  (`estimation_mode="single"`, `skills`, `resource_sharing`) — inert until the Phase 2 UI. 98
  tests pass. Blueprint: `docs/multi-skill-strategy.md`.
- **`v1.34`** — **SSDM removed from the application at every level** — the role
  is dropped from `ALL_ROLES`, `OVERHEAD_ROLES`, grade eligibility, the Step-5 overhead inputs
  (now Architect/SDM only), activity role-splits, the Excel workbook, and the docs. The engine
  now **filters overhead to recognised roles**, so an older saved estimate carrying an SSDM
  overhead % no longer leaks SSDM into role hours / FTE / cost (it's ignored cleanly). Excel
  recalc still matches the engine 100%; 92 tests pass.
- **`v1.33`** — Fixes the **Step 10 version-note auto-summary when resuming a
  draft**: the draft-resume path (`_resume_draft_now`) loaded the inputs but never recorded a
  baseline, so the change-diff had nothing to compare against and showed "Initial version". It
  now calls `mark_saved_baseline()` on resume (capturing `_saved_inputs_snapshot`), and the note
  field **keeps refreshing with the live change summary** as you edit — until you type your own
  note (then it stops overriding). 92 tests pass.
- **`v1.32`** — The **Transition & Onboarding Planner** inputs (shown when
  "Include Transition" = Yes) now use the same single-entry behaviour as the rest of the app:
  the **phases**, **resource roster** and **weekly utilisation** grids were `st.data_editor`s
  (commit-on-blur) and are now **individual widgets** — text/number inputs for phases (name,
  weeks), role selectbox + count per resource, and a utilisation selectbox (0/25/50/100%) per
  resource-week — each id-keyed with write-back, plus add/remove buttons. Values register in one
  interaction. Engine/Excel untouched; 92 tests pass.
- **`v1.31`** — **Uniform single-entry input behaviour** across the app:
  every editable field now follows the Step-1 *Monitoring Alerts* pattern — a distinct widget
  key (`…_w`) + concrete `value=` + explicit write-back — so a typed value registers in one go.
  Fixes the Step 8 fields that still used the canonical key directly (SLA include/%, target
  margin, reporting currency) and **converts the Step 2 resolution grid and Step 4 activities
  grid from `st.data_editor` to individual `number_input`s** (Step 4 keeps add/remove via
  buttons). Also: **Step 10 Version Notes auto-populates** from a diff of what changed since the
  last saved version (e.g. "Margin 20%→25%; Alerts 300→400; activities 5→6") — editable. 92
  tests pass; engine/Excel untouched.
- **`v1.30`** — Input/UX fixes on the app form: **single-entry number fields**
  on Step 8 (the nullable `value=… else None` widgets that needed two entries are now concrete —
  people, days, cost/shift, additional cost, SLA %, margin %, FX). **Shift Allowance** and
  **On-Call Allowance** each get their own **on/off switch** (like patching); the middle field is
  renamed **"Monthly Days per Person"** (default **22**) and the calc is people × days ×
  cost/shift, with default cost/shift **₹440** (shift) and **₹550** (on-call). **SSDM overhead**
  now defaults to **0%** (still a user field like SDM/Architect). Default **transition duration =
  4 weeks**, and the **"Process Understanding"** phase is removed from the defaults. Additional
  activities now ship with **fixed default hours** instead of auto-derivation: Scheduled
  Maintenance 0, RCA 40, Problem Management 80, Documentation 16, Service Review Prep 16 (all
  manual). Engine/Excel untouched; 92 tests pass.
- **`v1.29`** — The **Excel Workbook** is restructured so **every application
  input lives on one editable `Inputs` sheet** — the only yellow/unlocked cells in the workbook
  (213 of them); every other sheet is 100% locked, formula-only, and references Inputs. This
  closes the gap where the **monthly workload volumetrics**, **coverage model**, custom
  hours/days and **project identity** were missing from or derived on the input view. The
  coverage multiplier is now a derived formula (not a free input), grade→genus mapping and the
  scoped rate card moved onto Inputs, and the full transition plan (phases, weekly utilisation
  grid, treatment) is there too. So you can change any application input in Excel and the whole
  model recalculates. Re-verified **100%** against the engine across all treatments. 92 tests pass.
- **`v1.28`** — The **Excel Workbook** export is reworked into a single,
  fully **formula-driven replica of the whole app** and is now both the on-screen download and
  the approval-email attachment (the old static "Excel Report" is retired). Adds a client-facing
  **Summary/cover sheet** (branded, headline price in INR + reporting currency, blended margin,
  key assumptions) and a full **Transition sheet** (phases, weekly utilisation grid with a
  0/.25/.5/1 dropdown, per-phase cost, commercial treatment) that flows into the Costing and
  dynamic **Dashboard** monthly price. Formula cells are protected (yellow inputs stay editable).
  **Accuracy:** every formula was recalculated with the `formulas` engine and matches the app
  **100%** across all transition treatments; a new `tests/test_excel_model.py` regression guard
  recalculates the workbook in CI. **Bug fix:** a v1.26 cross-sheet `SUMPRODUCT` was missing its
  sheet qualifier and self-referenced the Effort sheet, so role-hours/FTE/cost/price were wrong
  whenever an additional activity existed — now fixed. 92 tests pass.
- **`v1.27`** — New **Transition & Onboarding Planner** (a section inside
  Step 8 Costing): a fully dynamic phase/week resource grid that auto-calculates the transition
  cost from the existing Genus hourly rates, then lets the user choose the commercial treatment.
  Pick a **total duration** (auto-generates week columns), configure **dynamic phases**
  (rename/add/delete/reorder, weeks must sum to the duration), staff a **resource roster**
  (role × count), and set **per-week utilisation** (0/.25/.5/1.0) in per-phase grids.
  `weekly cost = count × utilisation × 40 hrs × hourly rate`. Commercial treatment:
  **Recurring** (÷ configurable months, added to the monthly price **post-margin**),
  **One-time fee** (separate line), or **Absorb** (discount → net charged ₹0). New pure
  `engine.calc_transition_cost`; nothing hardcoded (weeks/phases/roles). Backward compatible —
  old estimates load with the planner off and the legacy one-time transition figure intact.
  90 tests pass. *(Export theming for the new treatment is a follow-up.)*
- **`v1.26`** — The **Editable Excel (formulas)** download is rebuilt as a
  **fully formula-driven workbook that mirrors the app page by page** (`generate_excel_model`):
  sheets for Inputs, Rate Cards, 1-2 Workload, 3 Patching, 4 Activities, 5 Effort, 6 FTE,
  7 Rates, 8 Costing and a live Dashboard. Yellow cells are editable inputs; white cells are
  live formulas mirroring `engine.compute_full_model`, so an Excel-first user can change any
  driver and watch every page + the Dashboard recalculate **without the app**. Grey "App value"
  cells echo the tool's computed result for cross-checking. No new dependency (openpyxl only);
  calculation engine untouched; same `generate_excel_model()` signature (download button +
  approval-email attachment unchanged).
- **`v1.25`** — The approval **email now carries the estimate in it**: an
  **Executive + Financial summary rendered in the body** (inline HTML, reliable across
  clients) and the **editable Excel formula workbook attached** (`generate_excel_model`).
  Applies to both the initial request and **Resend**. Built from the current estimate
  session at send time. No new dependency (ACS attachments + Pillow already present;
  no server-side screenshot/kaleido).
- **`v1.24`** — Approval/versioning hardening + gate & contrast fixes on
  top of v1.10 (no new infrastructure or config — same Groq chat, Blob store, ACS email).
  Highlights: branded, readable sign-in / mode / chat gates with the Nagarro logo;
  **re-version + re-approval when an approved estimate changes** (downloads/approval blocked
  until saved as a new draft); **save-then-approve** guidance + inline save; chat estimates
  get a real **Customer/RFP name**; **save a what-if as a new version**; the approval **email
  shows headline figures** and the **reviewer landing page** shows the same summary; the
  review link is no longer exposed to the requester (**Resend approval email** instead);
  Resume screen has readable draft names + **per-draft delete**. (covers v1.11–v1.24)
- **`v1.10`** — Chat AI provider switched from Google Gemini to **Groq**
  (free tier, OpenAI-compatible) — Gemini's free tier returned `limit: 0` for the user's
  account. Model `llama-3.3-70b-versatile` (override with `GROQ_MODEL`), via `GROQ_API_KEY`;
  `groq` dependency; workflow injects `GROQ_API_KEY` (Secret/Var) + `GROQ_MODEL`. Same guarded
  chat + JSON `{action,message,inputs}` contract + India-rates cook-it flow; degrades gracefully
  when the key is unset. 80 passing tests.
- **`v1.9`** — Bug-fix on v1.8: the Chat reply loop is rebuilt to the
  standard Streamlit pattern — the assistant's question/answer (and, crucially, any **error**
  such as a Gemini rate-limit or auth failure) now renders **inline and stays visible** instead
  of being wiped by an immediate rerun (which made it look like "nothing happened" after the
  first message). Only a successful "cook it" reruns (to show the dashboard). No engine/provider
  change. 80 passing tests.
- **`v1.8`** — Builds on v1.7: **conversational "Chat to estimate" (Phase 2,
  Google Gemini — free tier)**. In Chat mode a guarded assistant (model `gemini-2.0-flash`, via
  `GEMINI_API_KEY`) takes a plain-language brief, refuses off-topic / PII input, asks for
  anything missing, then "cooks it" — applying the inputs with **India delivery rates**
  (auto-loaded rate card + auto role→genus mapping) and landing on the Results Dashboard with
  an assumptions banner; every field stays editable. Degrades gracefully when the key is unset
  (Chat says "not configured", Manual unchanged). New `modules/llm/chat_assist.py` +
  `modules/inputs/chat_page.py`; `google-genai` dependency; workflow injects `GEMINI_API_KEY`
  (Secret) / `GEMINI_MODEL` (Var). Calculation engine untouched. 77 passing tests.
- **`v1.7`** — Builds on v1.6: **Chat/Manual mode chooser (Phase 1)**.
  After the email gate the user picks how to build the estimate — **Manual** opens the
  existing app unchanged; **Chat** is a placeholder ("coming soon") carrying the PII /
  scope note (the full conversational flow + Azure OpenAI land in Phase 2). The chooser
  is shown every session and is switchable from either side (sidebar **Switch to Chat**;
  in-chat **Switch to manual**); the resume-draft modal is now scoped to Manual mode.
  Pure routing — no AI, calculation engine untouched. Token-link visitors bypass it.
  71 passing tests.
- **`v1.6`** — Builds on v1.5: **email identity gate + blocking resume
  modal**. The app is gated behind a **Nagarro email** (`@nagarro.com`, auto-lowercased) —
  nothing else renders until a valid one is entered, so all fields/buttons/nav stay
  locked. That email becomes the owner key for the user's drafts and saved versions and
  pre-fills "Prepared By" (the editable Prepared-By field is removed from Step 1). The
  "Resume a draft" sidebar list is replaced by a **non-dismissible full-screen modal**
  (shown only when that email has drafts) offering *Resume* (lists the user's own drafts
  with details) or *Start afresh*. Token-link visitors (approval reviewer / orphan
  deletion) bypass the gate. Calculation contract unchanged. 71 passing tests.
- **`v1.5`** — Builds on v1.4: **draft autosave + orphan recovery**.
  Work-in-progress is silently saved per Customer/RFP on every page navigation
  (`__drafts__/<slug>.json`); naming a project with an existing draft prompts to
  resume or start afresh, and a sidebar lists resumable drafts. Abandoned drafts
  (declined, or untouched > 30 days) become **orphans** (`__orphans__/…`), cleaned up
  via a token-gated, emailed deletion link (same pattern as the approval workflow) —
  never deleted directly on screen. **Prepared By** is now required on Step 1, and a
  browser warn-on-close guards unsaved in-page edits. Calculation contract unchanged.
  69 passing tests.
- **`v1.4`** — Builds on v1.3: **Step 4 (Additional Activities)**
  rebuilt with `st.data_editor` (dynamic add/delete rows, Auto/derived hours + role-%
  split, read-only validation table) — completing the input-grid redesign begun with
  Step 2. Calculation contract unchanged. 55 passing tests.
- **`v1.3`** — Builds on v1.2 with the full **UX/design-system pass**:
  a central **design-token** layer (`config.settings.THEME` + CSS `:root`) shared by the
  web app, PDF and Excel so all three share one brand palette; the **Step 2** resolution
  grid rebuilt with `st.data_editor`; **PDF** page numbers + repeating header + zebra
  rows; **Excel** number/percent/date formatting + logo; the approval **email** as a
  branded inline button (extracted template); the **Nagarro logo** asset; a **sidebar
  gradient** background that blends with the logo; and spacing fixes so dividers/borders
  never clip text, boxes or inputs. 55 passing tests.
- **`v1.2`** — **11-step** flow (split the old combined Step 8 into
  **8 Costing Inputs / 9 Results Dashboard / 10 Approve & Export / 11 Compare**) and
  relocated rate card, coverage model and delivery location onto Step 1. Adds the
  **Tool-Based patching error-rate** model, **Saved Calculations** (versioned Blob
  saves keyed by Customer/RFP), the **email approval workflow** (token-gated, Azure
  Communication Services), the **editable Excel formula workbook**, per-category
  L1/L2/L3 buffers at the heading, and the UX Phase 1+2 polish (Nagarro branding,
  select-all-on-focus, scroll-to-top, per-page reset, tighter density). 55 passing tests.
- **`v1.1`** — adds Step 2 per-role buffer % (default 20%) + the missing L3 Hrs column,
  and loads the rate card from **Azure Blob Storage** (managed identity) instead of a
  local upload. Builds on v1.0. (9-step flow.)
- **`v1.0`** — first production-ready release. (9-step flow.)

> In the commands below, replace `v1.0` with the version you want (e.g. `v1.4`).

## What `v1.29` contains (current stable)
Everything in v1.28, plus the **single editable Inputs sheet** restructure of the Excel
Workbook (`modules/outputs/excel_model.py`):
- **One input register** — `Inputs` is the only editable sheet and holds *every* application
  input: engagement/identity, coverage model (+ custom hrs/days), monthly working hrs,
  utilisation, FTE basis, contingency, overheads, the full **monthly workload volumetrics grid**
  (per category × severity: count / minutes / L1·L2·L3 % / buffers), patching, additional
  activities, grade→genus mapping, the scoped rate card, costing (margin, SLA, FX, expenses) and
  the full transition plan (phases, weekly utilisation grid, treatment, amortisation).
- **Everything else is locked formulas** — Workload / Patching / Activities / Effort / FTE /
  Rates / Transition / Costing / Dashboard contain no editable cells; they mirror their inputs
  from `Inputs` and compute live. The coverage **multiplier** is a derived formula (was a
  free-typed input). Audit: Inputs = 213 unlocked cells, every other sheet = 0.
- **Verified** 100% formula-vs-engine across recurring/one-time/absorb/off; 92 tests pass.

## What `v1.28` contains
Everything in v1.27, plus the **Excel Workbook rework** (`modules/outputs/excel_model.py`):
- **One canonical workbook** — a live formula-driven replica of the app, used for both the
  dashboard download and the approval-email attachment. The old static value-dump report
  (`excel_export.py`) is no longer surfaced.
- **Summary / cover sheet** (first tab) — branded, client-facing: engagement, headline price
  (INR + reporting currency), gross + blended margin, transition treatment, key assumptions.
- **Transition sheet** — phases (with week-range mapping), a weekly utilisation grid (per-cell
  0/.25/.5/1 dropdown), per-phase cost via `SUMPRODUCT`, and the commercial-treatment block
  (recurring ÷ months / one-time / absorb). Feeds the Costing + Dashboard monthly price.
- **Dashboard** — adds Monthly Price incl. Transition and a live Transition summary.
- **Cell protection** — formula cells locked, yellow input cells editable (no password).
- **Verified 100% accurate** — every formula recalculated with the `formulas` engine matches
  `compute_full_model` across recurring/one-time/absorb/off; guarded by `tests/test_excel_model.py`.
- **Fixed** a v1.26 bug: the Effort activity-split `SUMPRODUCT` lacked its `'4 Activities'!`
  qualifier and self-referenced the Effort sheet, corrupting role-hours → FTE → cost → price for
  any estimate with an additional activity.

## What `v1.27` contains
Everything in v1.26, plus the **Transition & Onboarding Planner**
(`modules/inputs/transition_planner.py`, surfaced as a section at the top of Step 8 Costing):
- **Dynamic duration** — pick the total transition weeks (presets 4/8/12/16/24, or any value);
  week columns generate automatically. Reducing the duration warns before dropping weeks that
  hold utilisation data.
- **Dynamic phases** — default set (Assessment & Discovery / Initiation & Planning / Knowledge
  Transition / Process Understanding / Stabilization) is fully editable (rename/add/delete/
  reorder/redurate). Validation blocks until **Σ phase weeks = total duration** (shows
  Allocated / Remaining / Exceeded).
- **Resource roster + weekly grids** — roster is role × count (roles from `ALL_ROLES`,
  extensible); each phase gets a mini-grid whose week columns group under a phase band, with a
  per-cell utilisation picker (0 / 25% / 50% / 100%).
- **Cost** — `weekly cost = count × utilisation × 40 hrs × Genus hourly rate`; reuses the
  existing rate-card resolution. Live per-resource cost table + total.
- **Commercial treatment** — Recurring (÷ configurable months → added to the monthly selling
  price, post-margin), One-time fee (separate line), or Absorb (Transition ₹X / Absorbed −₹X /
  Net charged ₹0).
- **Engine/state** — pure `calc_transition_cost` + `transition_week_phase_map`; wired into
  `compute_full_model` after margin; `transition_planner` persists in drafts/versions/scenarios.
  Legacy `transition_cost` key retained so existing exports keep working. Nothing hardcoded.

## What `v1.26` contains
Everything in v1.25, plus the **Editable Excel (formulas)** export rebuilt from a single
"Editable Model" sheet into a **page-by-page, fully formula-driven workbook**
(`modules/outputs/excel_model.py` → `generate_excel_model`):
- **Sheets:** `Inputs` (all scalar inputs + FX table + additional cost items),
  `Rate Cards` (scoped lookup table the rates sheet VLOOKUPs against, plus the full uploaded
  card for reference), `1-2 Workload`, `3 Patching`, `4 Activities`, `5 Effort`, `6 FTE`,
  `7 Rates`, `8 Costing`, and a live `Dashboard`.
- **Live recalculation:** yellow cells are editable inputs; white cells are Excel formulas that
  mirror `engine.compute_full_model` (buffered role hours, patching manual/tool, auto-activity
  formulas, contingency + overhead assembly, FTE with coverage + ⌈0.5⌉ rounding, genus→rate
  VLOOKUP × FX → INR, delivery → selling price). Change any input and every page + the
  Dashboard recomputes **without the app**.
- **Cross-check:** grey "App value" cells echo the tool's computed result next to the Excel
  formula so users can confirm the recalculation matches.
- No new dependency (openpyxl only); engine untouched; the public `generate_excel_model()`
  signature is unchanged, so the dashboard download button and the approval-email attachment
  keep working as-is.

## What `v1.25` contains
Everything in v1.24, plus **the estimate travels with the approval email**:
- **Body:** an inline-styled **Executive Summary + Financial Summary** (total effort, FTE,
  delivery cost, gross margin %, selling price; resource cost / expenses / SLA / gross
  profit / transition). Inline HTML so it renders in Outlook/Gmail — not a screenshot
  (server-side screenshots aren't possible on this scale-to-zero container, and image
  embeds are unreliable in email).
- **Attachment:** the **editable Excel formula workbook** (`generate_excel_model`) with the
  full working model.
- Applies to the initial **request** and the **Resend approval email** button; figures,
  body summary and the workbook are all generated from the same current-session model at
  send time (= the just-saved version in the normal flow). Best-effort: if the workbook
  can't be built the email still sends with the summary. No new dependency.

## What `v1.24` contains
Everything in v1.10, plus approval/versioning hardening and gate/contrast fixes — no new
infrastructure or config (same Groq chat, Blob store and ACS email):

**Gate & contrast (v1.11–v1.15, v1.23)**
- Branded navy→teal sign-in / mode / chat gates with the **Nagarro logo** and readable
  light text on the dark backdrop. Root cause of the earlier dark-on-dark labels: the
  "white card" CSS targeted `stVerticalBlockBorderWrapper`, which does **not** exist in
  Streamlit 1.58 — fixed by colouring the real elements (`stWidgetLabel` /
  `stCaptionContainer`), all verified against the installed bundle.
- Chat transcript made legible; the Approve page lost a duplicate "Approval" header;
  Step 7 / approval stray leading dividers removed; Resume-screen draft names readable.

**Approval & versioning (v1.16–v1.22)**
- **Re-version + re-approval on change:** editing an **approved** estimate blocks downloads
  and new approval requests until it is **saved as a new draft version** (change detected by
  a fingerprint of the model inputs; navigation never counts). Reviewer (token) mode is never
  blocked.
- **Save-then-approve** guidance with an inline "Save this version" on the Approve page;
  chat estimates are no longer auto-named "Chat estimate" — the user names them on the
  Results page (kept out of the chat/LLM for PII).
- **Save a what-if as a new version** — bakes the moved drivers (volume, margin, contingency,
  coverage) into a fresh draft, with the drivers recorded in the version note.
- **Approval email** carries the headline figures (selling price, gross margin %, delivery
  cost, FTE) read from the saved version; the **reviewer landing page** shows the same summary
  above Approve/Reject.
- The tokened review link is **no longer shown to the requester** (they could self-approve);
  a **Resend approval email** button (to the reviewer on record) covers "didn't receive it".
  The link is only shown as a fallback when no email channel is configured.

**Drafts (v1.24)**
- The Resume-a-draft screen gains a **per-draft delete** (two-step confirm).

> Intermediate versions v1.11–v1.23 were shipped as commits; **v1.24** is the rolled-up
> stable tag. Tooling/contrast work is documented inline above.

## What `v1.8` contains
- Everything in v1.7 (below), plus the **conversational "Chat to estimate" flow (Phase 2)**:
  - **Provider:** **Google Gemini** free tier (`modules/llm/chat_assist.py`), model
    `gemini-2.0-flash` (override with `GEMINI_MODEL`); needs the `GEMINI_API_KEY` Secret (free
    key from aistudio.google.com — no card). The assistant replies with a strict JSON
    `{action, message, inputs}` contract (no provider function-calling). Added the
    `google-genai` dependency and wired the env vars into the deploy workflow.
  - **Guarded chat** (`modules/inputs/chat_page.py`): a `st.chat_input` conversation that is
    scope-locked to managed-services estimation, refuses off-topic questions, and never
    requests/echoes PII (on-screen note + system-prompt rule).
  - **Extraction → cook:** the assistant gathers the headline drivers (volumes, servers,
    coverage, contingency, margin), lists its assumptions, then emits them via a
    `submit_estimate` tool. The app applies them with **India delivery rates** (auto-loads the
    cloud rate card, auto-maps role→genus from `GRADE_ELIGIBILITY`), and lands on the **Results
    Dashboard** (Step 9) in Manual mode with a one-time assumptions + "India rates" banner.
  - **Graceful degradation:** with no `ANTHROPIC_API_KEY`, Chat shows "not configured" and
    points to Manual; Manual is entirely unchanged. The calculation engine is untouched.

## What `v1.7` contains
- Everything in v1.6 (below), plus the **Chat/Manual mode chooser (Phase 1)**:
  - After the email gate, a blocking **"How would you like to build this estimate?"**
    screen (`modules/inputs/mode_gate.py`) offering **💬 Chat** or **✍️ Manual**.
  - **Manual** routes to the existing app **verbatim** — no feature/function change.
  - **Chat** is a **Phase-1 placeholder** ("coming soon") with the PII / scope note; the
    conversational flow + **Azure OpenAI** (India delivery rates) arrive in Phase 2.
  - Shown **every session**; switchable both ways; the resume-draft modal is scoped to
    Manual mode; token-link visitors (approval / orphan) bypass the chooser.

## What `v1.6` contains
- Everything in v1.5 (below), plus the **email identity gate + blocking resume modal**:
  - **Gate** (`modules/inputs/identity_gate.py`) — a valid `@nagarro.com` email (auto
    lower-cased, regex-validated) is required before anything else renders; the screen
    halts via `st.stop()` so every field, button and the step nav stay locked.
  - **Owner key** — that email is stored on each draft (`prepared_by`) and used to scope
    "Resume a draft" to the current user; it also pre-fills approval emails. The editable
    Prepared-By text field is removed from Step 1 (shown read-only instead).
  - **Resume modal** — replaces the sidebar "Resume a draft" list with a full-screen,
    non-dismissible modal shown only when the email has drafts; offers *Resume* (lists the
    user's own drafts with details) or *Start afresh* (drafts are kept, not orphaned).
  - **Token bypass** — approval-reviewer and orphan-deletion token links skip the gate.

## What `v1.5` contains
- Everything in v1.4 (below), plus **per-project draft autosave + orphan recovery**:
  - **Autosave** — WIP is saved to `__drafts__/<slug>.json` on every page navigation
    (centralised through `goto_step()`); silent, keyed by the Customer/RFP slug.
  - **Restore** — naming a project that has a resumable draft (≤ 30 days, not created
    this session) prompts *Continue previous* / *Start afresh*; a sidebar lists all
    resumable drafts as a backstop.
  - **Orphans** — declined or > 30-day-old drafts surface as orphans
    (`__orphans__/<slug>__<ts>.json`); the 30-day clock is evaluated lazily on read
    (no background job — the app is scale-to-zero).
  - **Token-gated cleanup** — the "🧹 Clean up drafts" indicator opens a review page
    to email a recipient a `?orphan=<token>` link; deletion is confirmed by the
    recipient on a scoped page (reuses the approval email + tokened-link pattern).
    Nothing is deleted directly on screen.
  - **Prepared By** is required on Step 1; a browser **warn-on-close** guards unsaved
    in-page edits. New modules: `modules/state/draft_store.py`,
    `modules/state/orphan_review.py`, `modules/outputs/orphan_admin.py`.
    `config.DRAFT_ORPHAN_DAYS = 30`. Calculation contract unchanged.

## What `v1.4` contains
- Everything in v1.3 (below), plus: **Step 4 (Additional Activities)** rebuilt with
  `st.data_editor` — dynamic add/delete rows, an Auto toggle that derives hours from
  servers/volumes, the six role-% split columns, and a read-only validation table.
  This completes the input-grid redesign started with Step 2; the calculation contract
  (`name / auto / custom / hours / dist`) is unchanged.

## What `v1.3` contains
- Everything in v1.2 (below), plus the complete UX/design-system pass:
  - **Design tokens** — `config.settings.THEME` + CSS `:root` variables drive the web app,
    PDF (reportlab) and Excel (openpyxl) from one palette; `kind=` button selectors
    migrated to the Streamlit 1.58 `stBaseButton-*` testids + a native `[theme]` block.
  - **Step 2** resolution grid rebuilt with `st.data_editor` (read-only computed results
    table; calculation contract unchanged).
  - **PDF**: `Page n of N` + brand footer, repeating table headers, zebra rows, logo.
  - **Excel**: number/percent formats, real Date cell, Exec-sheet logo.
  - **Email**: branded inline-button approval template (`modules/notify/email_templates.py`).
  - **Branding**: `assets/nagarro_logo.png` + a `assets/sidebar_bg.png` gradient sidebar.
  - **Layout**: spacing fixes so dividers/section underlines/alert boxes never clip
    adjacent text, inputs or boxes.

## What `v1.2` contains
- Full Streamlit app: **11-step** Ops effort/cost/pricing flow (see the table in README).
  - Inputs 1–8; outputs 9 Results / 10 Approve & Export / 11 Compare.
  - Step 1 carries the rate-card source, coverage model and delivery location.
- Patching: Manual (min/server × servers) **and** Tool-Based (failed servers = servers ×
  error-rate %, × min/failed-server). Auto-derived activities (Scheduled Maintenance,
  RCA, Problem Management, Documentation & KB).
- Multi-location rate cards + multi-currency reporting (default India / INR).
- Outputs: dashboard, multi-sheet Excel report, **editable Excel formula workbook**,
  branded PDF, scenario comparison, what-if sliders, Raw/Rounded FTE toggle.
- **Saved Calculations** — versioned, timestamped Blob saves keyed by Customer/RFP name.
- **Email approval workflow** — token-gated review link via Azure Communication Services
  (reviewer approves/rejects; preparer sees status only). Entra ID sign-in deferred.
- Single pure pipeline `engine.compute_full_model` (no display/export drift).
- Azure deploy: GitHub Actions OIDC → Container Apps (scale-to-zero); Blob via managed identity.
- 55 passing tests.

> Tip: `git show v1.2` shows the tagged commit; `git tag -n` lists tags with messages.

---

## First, make sure you have the tag locally
```bash
git fetch --tags
git tag                 # should list: v1.0
```

## Option A — Just look at v1.0 (read-only, non-destructive)
```bash
git checkout v1.0       # detached HEAD — browse the exact files
git checkout main       # go back to the latest
```

## Option B — Branch off v1.0 (recommended for testing a rollback)
```bash
git checkout -b restore-v1 v1.0
# experiment / run / compare here; main is untouched
```

## Option C — Bring v1.0 files back as a NEW commit (safe rollback, keeps history)
Best when you want `main` to behave like v1.0 again **without** rewriting history:
```bash
git checkout main
git checkout v1.0 -- .          # overwrite working tree with v1.0 contents
git commit -m "Revert to stable v1.0"
git push                        # this also redeploys v1.0 to Azure
```

## Option D — Hard reset main to v1.0 (DESTRUCTIVE — discards newer commits)
Only if you truly want to erase everything after v1.0:
```bash
git checkout main
git reset --hard v1.0
git push --force origin main    # rewrites remote history; also redeploys v1.0
```

---

## Redeploying v1.0 to Azure
Deployment runs automatically on push to `main`, so **Option C or D pushes v1.0 and
redeploys it**. To deploy v1.0 *without* changing `main`, use Option B then run the
workflow from the `restore-v1` branch (GitHub → Actions → Run workflow → pick the branch).

---

## (Maintainers) how this tag was created / how to cut the next one
```bash
# create + push an annotated tag
git tag -a v1.0 -m "Stable Version 1"
git push origin v1.0

# next stable releases
git tag -a v1.1 -m "Stable Version 1.1"
git push origin v1.1

git tag -a v1.2 -m "Stable Version 1.2 — 11-step flow, error-rate patching, saved calcs, approvals"
git push origin v1.2

git tag -a v1.3 -m "Stable Version 1.3 — UX/design-system pass: tokens, Step 2 data-editor, export polish, branding"
git push origin v1.3

git tag -a v1.4 -m "Stable Version 1.4 — Step 4 Additional Activities rebuilt with st.data_editor"
git push origin v1.4

git tag -a v1.5 -m "Stable Version 1.5 — draft autosave + orphan recovery (token-gated cleanup)"
git push origin v1.5

git tag -a v1.6 -m "Stable Version 1.6 — Nagarro email identity gate + blocking resume modal"
git push origin v1.6

git tag -a v1.7 -m "Stable Version 1.7 — Chat/Manual mode chooser (Phase 1; Chat placeholder)"
git push origin v1.7

git tag -a v1.8 -m "Stable Version 1.8 — conversational Chat to estimate (Google Gemini, India rates)"
git push origin v1.8

git tag -a v1.9 -m "Stable Version 1.9 — fix Chat reply/error rendering (inline, persistent)"
git push origin v1.9

git tag -a v1.10 -m "Stable Version 1.10 — Chat AI provider switched to Groq (free tier)"
git push origin v1.10

git tag -a v1.24 -m "Stable Version 1.24 — approval/versioning hardening + gate & contrast fixes"
git push origin v1.24

git tag -a v1.25 -m "Stable Version 1.25 — approval email carries estimate summary (body) + editable Excel attachment"
git push origin v1.25

git tag -a v1.26 -m "Stable Version 1.26 — Editable Excel rebuilt as page-by-page formula-driven workbook"
git push origin v1.26

git tag -a v1.27 -m "Stable Version 1.27 — Transition & Onboarding Planner (dynamic phase/week resource grid + commercial treatment)"
git push origin v1.27

git tag -a v1.28 -m "Stable Version 1.28 — Excel Workbook reworked as a 100%-verified formula replica incl. Transition + Summary"
git push origin v1.28

git tag -a v1.29 -m "Stable Version 1.29 — Excel Workbook: all inputs on one editable Inputs sheet, every other sheet locked formulas"
git push origin v1.29

git tag -a v1.30 -m "Stable Version 1.30 — single-entry Step 8 fields, shift/on-call on-off switches, default tweaks (SSDM 0, transition 4wk, activity hours)"
git push origin v1.30

git tag -a v1.31 -m "Stable Version 1.31 — uniform single-entry inputs (grids to number_inputs), Step 10 auto version notes"
git push origin v1.31

git tag -a v1.32 -m "Stable Version 1.32 — transition planner inputs converted to single-entry widgets"
git push origin v1.32

git tag -a v1.33 -m "Stable Version 1.33 — fix Step 10 version-note auto-summary on draft resume (baseline + live refresh)"
git push origin v1.33

git tag -a v1.34 -m "Stable Version 1.34 — remove SSDM role from the application at every level"
git push origin v1.34

git tag -a v1.35 -m "Stable Version 1.35 — multi-skill estimation Phase 1 (engine + data model, single = 1 skill, no UI)"
git push origin v1.35

git tag -a v1.36 -m "Stable Version 1.36 — multi-skill Phase 2 (mode chooser + skill setup + per-skill workload + effort/FTE)"
git push origin v1.36
```
Optionally turn a tag into a downloadable GitHub Release:
GitHub repo → **Releases** → **Draft a new release** → choose tag `v1.0` → Publish.
