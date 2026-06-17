# Restoring to a Stable Version

This repository is tagged at each stable release. A git tag is an immutable pointer
to that exact snapshot, so you can always return to it no matter what changes later.

## Stable versions (latest first)
- **`v1.4`** — *current stable.* Builds on v1.3: **Step 4 (Additional Activities)**
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

## What `v1.4` contains (current stable)
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
```
Optionally turn a tag into a downloadable GitHub Release:
GitHub repo → **Releases** → **Draft a new release** → choose tag `v1.0` → Publish.
