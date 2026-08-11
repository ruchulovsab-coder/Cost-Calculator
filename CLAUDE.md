# Working in this repository

Conventions for anyone — human or AI assistant — making changes to the Ops Effort
Estimation Tool. Orientation: [README.md](README.md) · [HANDOVER.md](HANDOVER.md) ·
[docs/architecture.md](docs/architecture.md).

## What this is

A Streamlit app that produces AMS effort/cost estimates. Two flows: **single-skill** (an
11-step stepper, feature-frozen but supported) and **multi-skill** (10 tabs — where all new
work happens). Deployed to Azure Container Apps by push-to-deploy.

## Release flow

- New work goes on **`testing`** → auto-deploys to **staging**. `main` → **production**.
- `pytest` must pass before pushing; CI blocks deploy on failure.
- **Verify on the staging URL** before promoting. The Streamlit UI is not meaningfully
  testable locally — don't claim UI behaviour is verified from a local run.
- Promote = merge `testing` → `main`, push, tag `vX.Y`, bump `APP_VERSION` in
  `config/settings.py`, add a `RESTORE.md` entry. Keep `main` and `testing` content-identical.
- A tag push does **not** deploy; only a branch push does.
- Commits: `feat|fix|refactor|chore|docs(scope): summary`.

## Guardrails — do not break these

1. **The engine stays pure.** `modules/calculations/engine.py` takes state, returns a model.
   No Streamlit, no I/O. Every surface calls it; nothing recomputes independently.
2. **Excel must equal the engine**, to the rupee. Change a calculation → change the workbook
   formulas → update the parity tests (`test_excel_model.py`, `test_multi_excel.py`).
3. **Recommenders are deterministic rules, never an LLM.** Estimates must be reproducible and
   defensible to a client. LLM is optional narration only, and must degrade cleanly when no
   API key is configured.
4. **Single mode and Chat mode stay untouched** unless explicitly in scope.
5. **Changes are additive; saved estimates self-heal on load.** An estimate saved by an older
   version must still open — use the `ensure_*` / `reconcile_*` migration pattern, and keep
   migrations numerically neutral.
6. **Register persistent session keys in `session_manager._get_initial_state()`.**
   `serialize_inputs()` persists *only* keys found there; anything else is silently dropped
   on Save / Share / resume. If the key is bound to widgets, clear the stale widget keys on
   load. This exact omission caused P0 bugs in v1.64 (transition) and v1.65 (roster) — add a
   persistence regression test with any new persisted feature.
7. **Zero-workload skills must not leak** into Transition, Transition Cost or the Roster —
   use `engine.split_skills_by_workload(model)`.
8. **Never commit `genus_rate_card.xlsx`** (the real rate card). It is gitignored and lives in
   Azure Blob. `sample_rate_card.xlsx` is the tracked, non-sensitive sample.
9. **Don't remove the resource tags** (`Owner`, `Project`, `Purpose`, `Criticality`) from the
   deploy workflow — subscription policy denies untagged resources.

## Conventions

- Configuration goes in `config/settings.py`, not inline. Colours live in `THEME` and are
  mirrored in `assets/styles.css :root` (CSS can't read Python).
- Streamlit CSS selectors: verify `data-testid` values against the installed Streamlit
  version before relying on them — several plausible-sounding testids don't exist.
- Prefer pure functions in `modules/**` with the Streamlit layer kept thin, so logic stays
  testable without a UI runtime.
- Match the surrounding file's style: these modules are heavily commented with *why*, not
  *what*. Keep that.

## Before you finish

- `pytest` passes (208 tests at v1.65).
- New behaviour has a test; new persisted state has a persistence test.
- Docs updated if user-visible: `README.md` for flow/features, `RESTORE.md` for a release,
  `HANDOVER.md` for open items or ownership, `docs/architecture.md` for structure.
- ⚠️ Note the standing open item: `DEMO_SEED_DATA = True` in `config/settings.py` must be
  turned off before real client use (HANDOVER §6.2).
