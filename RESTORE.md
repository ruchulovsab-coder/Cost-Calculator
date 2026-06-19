# Restoring to a Stable Version

This repository is tagged at each stable release. A git tag is an immutable pointer
to that exact snapshot, so you can always return to it no matter what changes later.

## Stable versions (latest first)
- **`v1.8`** — *current stable.* Builds on v1.7: **conversational "Chat to estimate" (Phase 2,
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

## What `v1.8` contains (current stable)
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
```
Optionally turn a tag into a downloadable GitHub Release:
GitHub repo → **Releases** → **Draft a new release** → choose tag `v1.0` → Publish.
