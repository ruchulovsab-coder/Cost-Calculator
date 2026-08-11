# Architecture

How the app is put together, the contracts you must not break, and where to find things.
Current as of **v1.65**. Companion docs: [README.md](../README.md) (what it does),
[HANDOVER.md](../HANDOVER.md) (who owns it, what's open).

---

## 1. The shape of the system

A single Streamlit process. No database, no server-side session store, no login.

```
                    ┌─────────────────────────────────────────┐
   browser  ───────▶│  main.py — router & gate chain          │
                    │  email → chat/manual → resume → mode    │
                    └───────────────┬─────────────────────────┘
                                    │
             ┌──────────────────────┼──────────────────────┐
             ▼                      ▼                      ▼
     modules/inputs/*         modules/outputs/*      token deep-links
     (collect state)          (render & export)      (review / share / orphan)
             │                      │                      │
             └──────────┬───────────┘                      │
                        ▼                                  │
        modules/calculations/engine.py  ◀──────────────────┘
        compute_full_model(state)  ·  compute_multi_skill_model(state)
                        │
             ┌──────────┴───────────┬─────────────┬──────────────┐
             ▼                      ▼             ▼              ▼
      transition/            roster/       optimize/       state/  → Azure Blob
      (plan · cost)          (shift plan)  (pooling)       (persistence)
```

**The single most important rule:** every number the user sees — dashboard, Excel, PDF,
transition, roster, comparison, tests — comes from the engine. Nothing recomputes on its own.

---

## 2. Entry point: `main.py`

`main.py` (588 lines) is the router. In order:

1. **Page config, CSS injection**, auto-select and close-warning JS helpers.
2. `init_session_state()` then `seed_demo_data()` *(temporary — see HANDOVER §6.2)*.
3. **Token deep-link handlers**, each of which may take over the session:
   - `_maybe_load_review()` — approval reviewer
   - `_maybe_load_share()` — shared estimate, role-aware (viewer / editor)
   - `_maybe_load_orphan_review()` — draft-cleanup recipient
4. **Gate chain** (skipped entirely in token mode):
   `identity_gate` → `mode_gate` (Chat / Manual) → `chat_page` (if chat) → resume modal →
   `render_mode_chooser` (Single / Multi).
5. **Multi mode** → `render_multi_skill_app()` then `_autosave_draft()`, and `st.stop()`.
   The tabbed page has no navigation hook, so autosave runs after render.
6. **Single mode** → falls through to the sidebar + the `RENDERERS` step dispatch table
   (steps 1–11), with `_autosave_draft()` on every `goto_step()`.

**Why token visitors bypass the email gate:** the token *is* the credential. `_token_mode`
is set when any of the three handlers matched, and the whole `@nagarro.com` gate is skipped
so external reviewers/recipients can open their link. A shared session also never autosaves
over the owner's draft.

---

## 3. The calculation engine — `modules/calculations/engine.py`

1,098 lines, **pure**: no Streamlit import, no I/O, no globals. Two public pipelines:

| Function | Mode | Returns |
|---|---|---|
| `compute_full_model(state)` | Single | effort → role hours → FTE → cost → price |
| `compute_multi_skill_model(state)` | Multi | the same, per skill × level, plus `per_skill` |
| `split_skills_by_workload(model)` | Multi | `(active_ids, empty_names)` — who has real workload |

The pipeline, in the order the helpers compose:

```
calc_category_hours / calc_category_role_hours / calc_all_ticket_role_hours
        ↓  (+ calc_patching_effort, derive_activity_hours)
calc_base_effort → calc_contingency → calc_overhead_hours → assemble_role_hours
        ↓
calc_productive_hours · calc_coverage_multiplier · calc_fte   (ceil_half, min 0.5)
        ↓
resolve_role_rates → calc_resource_cost → calc_total_delivery_cost → calc_selling_price
        ↓
convert_to_currency / build_exchange_rates   (reporting currency)
```

Rules encoded in the engine that surprise people:

- **`active_levels` is authoritative.** Routing percentages are renormalized onto the levels
  a skill actually staffs. Levels are *not* cascade-gated — L1-only and L2/L3-only skills are
  both valid.
- **Architect is gated on L3** being active.
- **Coverage multiplier applies to L1/L2 only** (`COVERAGE_APPLICABLE_ROLES`).
- **FTE**: `Raw` (from workload) → `+buffer & contingency` (`fte_final`, unrounded) →
  `Rounded` = `max(ceil_half(x), 0.5)`. A big Raw→Rounded gap is many small cells each hitting
  the 0.5 floor; **pooling** is the remedy, not billing raw.
- **SDM (Option A)**: a fixed fraction of one SDM FTE, unrounded — not a % of total effort.
- **Activity hours distribute only across staffed roles.**
- **Transition cost is one-time** and never enters the monthly delivery cost.

### `split_skills_by_workload` — why it exists

All downstream surfaces derive skills from `model["per_skill"]`, which contains every
*visible* skill even one with no workload. Before v1.65 a placeholder skill appeared as a
phantom in the Transition plan (the "4 selected, 6 shown" bug). Now `transition/builder`,
`transition/costing` and `roster/scheduler` all drop zero-workload skills and surface an
"excluded — no workload" note. The estimate itself still keeps every skill.

---

## 4. Module map

### `modules/inputs/` — state collection (Streamlit)
| File | Role |
|---|---|
| `identity_gate.py` | `@nagarro.com` gate, resume modal, `drafts_for_email` |
| `mode_gate.py` | Chat vs Manual chooser |
| `chat_page.py` | Conversational estimation UI |
| `multi_skill.py` | **2,505 lines — the multi-skill app**: mode chooser, all 10 tabs, KPI band, Save/Share/Lock. The biggest file in the repo. |
| `steps_1_2.py`, `steps_3_5.py`, `steps_6_7.py` | Single-mode steps 1–7 (`callout` and other shared UI helpers live in `steps_1_2`) |
| `transition_planner.py` | Single-mode transition & onboarding planner (Step 8) |
| `rate_card_source.py` | Rate-card load (Blob or upload), country/location scoping |
| `feedback_widget.py` | 💬 popover rendered on every page/tab |

### `modules/outputs/` — rendering & exports
| File | Role |
|---|---|
| `dashboard.py` | Single-mode steps 8–10 |
| `excel_model.py` | **Single formula workbook** — one editable `Inputs` sheet, everything else locked formulas |
| `multi_excel_export.py` | Multi workbook, incl. the **Live Model** formula sheet |
| `excel_export.py`, `pdf_export.py` | Legacy value export; branded PDF proposal |
| `transition_excel.py`, `roster_excel.py` | Transition and shift-plan workbooks |
| `approval.py` | Approval request/decide UI + reviewer landing |
| `scenario_comparison.py` | Scenario save/compare, saved-calculation sidebar |
| `orphan_admin.py`, `feedback_admin.py` | Admin pages (draft cleanup; feedback viewer + CSV) |

### `modules/state/` — session & persistence
| File | Role |
|---|---|
| `session_manager.py` | **676 lines.** `_get_initial_state()`, `init_session_state()`, `run_model()`, `serialize_inputs()`, `load_scenario()`, fingerprinting, change summaries. See §5. |
| `multi_state.py` | Multi-skill state shaping: `ensure_ms_workload()` (legacy migration), `skill_volumes()`, `build_multi_model_state()` |
| `estimate_store.py` | Saved versions in Blob: `save_estimate`, `list_estimates`, `load_estimate`, `slugify`, `next_version_from_names` |
| `draft_store.py` | Autosave drafts + orphaning (`DRAFT_ORPHAN_DAYS` = 30) |
| `approval_store.py` | Approval records + tokened decisions |
| `share_store.py` | Per-recipient share tokens: `add_recipient`, `resolve`, `set_role`, `revoke`, `mark_opened` |
| `orphan_review.py` | Token-gated bulk deletion of orphaned drafts |
| `feedback_store.py` | Feedback capture + `to_csv` |

### The rest
| Path | Role |
|---|---|
| `modules/transition/builder.py` | `build_transition_plan(model, config)` — phases, per-skill family-aware detail, RACI, gates, RAID |
| `modules/transition/timeline.py` | `solve_timeline`, `fit_phases_to_go_live` — Gantt geometry, sequential vs overlap |
| `modules/transition/costing.py` | `steady_state_seats`, `default_allocation`, `reconcile_allocation`, `compute_transition_cost` |
| `modules/transition/catalog.py` | Static ITIL/family knowledge (428 lines of data, no logic) |
| `modules/roster/scheduler.py` | `build_roster(model, config)` — seats, shifts, person×weekday calendar, dual clock |
| `modules/optimize/team_optimizer.py` | `optimize_team` / `apply_optimization` — deterministic pooling of adjacent skills; `ai_narrative` is optional flavour |
| `modules/recommend.py` | `recommend_routing`, `recommend_skill_pyramid`, `recommend_architect` — **deterministic**, tested |
| `modules/notify/` | `email_sender.py` (ACS; `email_configured()`), `email_templates.py` (review / share / orphan bodies + figures blocks) |
| `modules/llm/chat_assist.py` | Groq client, `llm_configured()`, `run_chat_turn`, `parse_response` |
| `modules/demo_seed.py` | ⚠️ temporary demo data — see HANDOVER §6.2 |
| `config/settings.py` | 360 lines, all tunables. `THEME` is mirrored in `assets/styles.css :root`. |
| `utils/` | `formatters.py`, `validators.py` |

---

## 5. The session-state & persistence contract

**This is the contract that has broken twice. Read it before adding a feature.**

- `session_manager._get_initial_state()` defines **every key the app owns**.
- `serialize_inputs()` persists **only keys present in the initial state**. Anything else is
  silently dropped.
- `load_scenario(data)` restores those keys — and clears stale Streamlit **widget** keys so
  the UI doesn't hold on to the previous estimate's values
  (`_clear_transition_widget_state`, `_clear_roster_widget_state`).
- Dates are stored as ISO strings and re-coerced on load (`coerce_transition_date`).

**Therefore:** a session key that must survive Save / Share / draft-resume **must be
registered in `_get_initial_state()`**, and if the UI binds it to widgets you must clear
those widget keys on load.

Two P0 bugs came from skipping this:
- **v1.64** — `transition_start/go_live/customer_tz/sequencing/incumbent/phase_cfg` and
  `transition_alloc/sdm_alloc` were unregistered → saved/shared estimates reopened with the
  Transition tabs blank.
- **v1.65** — `roster_*` keys were unregistered → Save/Share/resume reset the Shift Plan to
  defaults. Same bug class, missed once.

Regression tests: `tests/test_transition_persistence.py`, `tests/test_roster_persistence.py`.

**Self-healing.** Saved estimates from older versions must still open. The pattern is a
`ensure_*` / `reconcile_*` function that fills in what a newer schema expects without
changing numbers (e.g. `multi_state.ensure_ms_workload()` migrates legacy `{'All'}` workload
rows into classifications, numerically neutral).

---

## 6. Token deep-links

Three features share one pattern: a random token stored in a Blob record, delivered by email,
resolved on load. No login involved.

| Feature | URL | Record | Resolution |
|---|---|---|---|
| Approval | `?rev=<token>` | `__approvals__/<slug>__v<n>.json` | `approval_store.decide()` |
| Share | `?sh=<slug>&v=<n>&k=<token>` | `__shares__/<slug>__v<n>.json` | `share_store.resolve()` → role |
| Orphan cleanup | tokened link | `__orphans__/…` + review record | `orphan_review.confirm_delete()` |

Properties worth preserving: tokens are **per recipient** (so each is individually revocable
and role-changeable), the **preparer never sees the reviewer's link** (a Resend button covers
"didn't receive it"), and destructive actions are always **confirmed by the recipient on a
scoped page**, never performed directly on the requester's screen.

If `APP_BASE_URL` is unset the app **refuses to send a relative link** and shows a copyable
one instead — an intentional fail-safe, not a bug.

---

## 7. Test map

`pytest` — **208 tests**, all pure (no Streamlit runtime, no network, no Azure).

| Test file | Covers |
|---|---|
| `test_engine.py`, `test_model.py` | Single-mode pipeline, FTE rounding, cost/price |
| `test_multi_skill.py` | Multi-skill engine, routing, levels, classifications |
| `test_excel_model.py`, `test_multi_excel.py` | **Formula-vs-engine parity** — the workbook must match to the rupee |
| `test_transition.py`, `test_transition_cost.py` | Transition plan, timeline, cost grid, zero-workload exclusion |
| `test_transition_persistence.py`, `test_roster_persistence.py` | The §5 contract |
| `test_roster.py` | Shift plan / coverage |
| `test_team_optimizer.py`, `test_recommend.py` | Deterministic pooling and recommenders |
| `test_estimate_store.py`, `test_draft_store.py`, `test_share_store.py`, `test_feedback_store.py`, `test_orphan_review.py` | Persistence records (pure functions, no Blob calls) |
| `test_approval.py`, `test_share_email.py`, `test_email_summary.py` | Approval decisions, email bodies/figures |
| `test_identity_gate.py`, `test_chat_assist.py` | Email validation, chat response parsing |

The store tests exercise the **pure** builders (`build_*`, `apply_*`, `resolve`) — the Blob
calls themselves are not mocked or tested. That is a deliberate cost/benefit line, not an
oversight: the Azure surface is thin and is validated on staging.

CI runs `pytest -q` as a **blocking** job before deploy.

---

## 8. Where to make common changes

| You want to… | Go to |
|---|---|
| Change a default, coefficient, colour, currency, role | `config/settings.py` (and `assets/styles.css` for colours) |
| Change how effort/FTE/cost is computed | `modules/calculations/engine.py` — **then update the Excel formulas and their parity tests** |
| Add a multi-skill UI element | `modules/inputs/multi_skill.py` — and register any persistent key per §5 |
| Add a transition phase or per-family content | `modules/transition/catalog.py` (data) before `builder.py` (logic) |
| Change an email | `modules/notify/email_templates.py` |
| Add an export | `modules/outputs/` — read from the engine model, never recompute |
| Add a new persisted feature | `_get_initial_state()` → UI → a persistence regression test |
