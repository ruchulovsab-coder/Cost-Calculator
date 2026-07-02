# Multi-skill → default-mode lifecycle parity

Multi-skill (the `estimation_mode == "multi"` flow) is a strong estimation **core** — engine,
rates, buffer transparency, AI optimizer, Excel export — but was never wired into the app's
estimate **lifecycle**. This doc tracks closing that gap to full parity with single mode.

## Parity gaps (audited 2026-07-01)

| Capability | Single | Multi (before) |
|---|---|---|
| Name the estimate (Customer/RFP) | ✅ Step 1 (`steps_1_2.py`) | ❌ none |
| Autosave draft | ✅ on nav (`_autosave_draft` via `goto_step`) | ❌ never fires (tabs don't navigate; no name) |
| Resume draft | ✅ | ⚠️ modal shows but nothing to resume; `ms_*` keys not restorable |
| Orphan recovery | ✅ | ❌ (depends on drafts existing) |
| Approval + email | ✅ Step 10 | ❌ none |
| What-if / compare | ✅ | ❌ none |
| End-of-journey dashboard | ✅ Step 10 | ⚠️ Tab 3 = effort/FTE + Excel button only |

## Phases

- **P1 — naming + autosave/draft/resume** (fixes data-loss). ← *shipped v1.52*
- **P2 — orphan recovery** (mostly free once P1 writes real drafts). ← *implemented*
- **P3 — end-of-journey dashboard** (approval/what-if/compare/downloads; reuse `dashboard.py`/`approval.py`).
- **P4 — RFP narrative / A-B exports** (deferred behind the lifecycle).

## P1 design decisions

### 1. Persist multi-skill state so drafts round-trip
`serialize_inputs()` and `load_scenario()` both iterate **only over `_get_initial_state()` keys**.
So a key is snapshot-able **and** restore-able iff it's in the initial state. `_build_multi_state()`
reads these keys that were **missing** from initial state — added now (all are plain, non-widget
state keys, so no Streamlit "value set via Session State" warnings):

| Key | Default | Why that default |
|---|---|---|
| `ms_family_grades` | `{}` | input: family×band → grade map |
| `ms_sdm_grade` | `None` | input: engagement SDM grade |
| `ms_rates_by_category` | `{}` | derived rates; persisted so a resumed session that jumps straight to dashboard/export still has them |
| `ms_sdm_rate_inr` | `0.0` | derived SDM rate |
| `ms_context_switch_pct` | `10.0` | matches the Optimize-tab UI default; **no-op until `resource_sharing` is non-empty** (penalty only applies to a pooled resource spanning >1 skill), so it does not change un-optimized numbers |
| `ms_enforce_min_shift` | `False` | off by default (matches UI); only default False keeps engine parity |

**Not persisted:** the Optimize tab's advisory tuning widgets (`ms_opt_objective`, `ms_opt_levels`,
`ms_opt_crossfam`, `ms_opt_context`, `ms_opt_ai_text`). They're widget keys (adding them to initial
state would trigger Streamlit warnings) and only shape *which suggestions are shown* — the **applied**
outcome already persists in `resource_sharing` (in initial state). Acceptable loss on resume.

### 2. Autosave on a tabbed page (no navigation events)
Single mode autosaves via `goto_step()`. Multi uses `st.tabs`, which has no navigation hook. So
`main.py` calls `_autosave_draft()` **once per rerun, after `render_multi_skill_app()` returns**
(all widget writes have landed by then). To avoid chatty cloud writes on every interaction,
`_autosave_draft()` now skips the write when the serialized inputs are unchanged since the last save
(`_autosave_sig` signature guard) — a harmless improvement for single mode too.

### 3. Name field
Top of `render_multi_skill_app()`, mirroring Step 1's "Customer / RFP Name *" (widget key
`ms_project_name_w` → `project_name`). `prepared_by` is already set at the email gate, so drafts are
owned correctly and surface in the resume modal. Autosave no-ops until a name exists.

### Resume routing (already correct once P1 lands)
`estimation_mode` is in initial state → restored by `load_scenario`; `_resume_draft_now` sets
`_ms_mode_resolved=True`, so a resumed multi draft routes straight to `render_multi_skill_app()`.

## P2 design decisions (orphan recovery)
The orphan pipeline (`draft_store`, `orphan_review`, `orphan_admin`) is **entirely metadata-driven**
(slug/project/prepared_by/age) — it never computes a model — so detection, listing, the review-email
flow, and the recipient token-delete page (`?orphan=`, bypasses via `_token_mode`) already cover
multi drafts once P1 wrote them into the same `__drafts__/` store. Orphans arise only from the 30-day
lazy stale clock (no explicit `orphan_draft` caller); that too is mode-agnostic.

**One real gap:** multi mode `st.stop()`s before the sidebar renders, and the "🧹 Clean up drafts"
entry point lived only in the sidebar → a multi preparer couldn't reach it. Fix:
- `main.py`: factored the full-page orphan-admin view into `_render_orphan_admin_page(back_key)`
  (single-mode sidebar site unchanged); added a `_show_orphan_admin` check inside the multi block so
  the page renders before the multi app stops.
- `multi_skill.py`: header now shows "🧹 Clean up drafts (N)" (via `orphan_count_cached()`) when N>0,
  setting `_show_orphan_admin` + rerun. "← Back to estimate" returns to multi (estimation_mode intact).

Note: multi still lacks the *rest* of the sidebar (Compare, saved versions, Reset) — that's P3 scope.

## Constraints
Engine stays pure + recalc-verifiable (Excel must stay 100%); single mode + Chat untouched;
verify on Azure after merge (no local UI testing).
