# Cloud & Infrastructure Practices — Ops Effort Estimation Tool

**Nagarro | Cloud & Infrastructure Practices · End-to-End Delivery Model**

[![Deploy to Azure Container Apps](https://github.com/ruchulovsab-coder/Cost-Calculator/actions/workflows/azure-deploy.yml/badge.svg)](https://github.com/ruchulovsab-coder/Cost-Calculator/actions/workflows/azure-deploy.yml)

A Streamlit application that turns AMS / managed-services workload volumetrics into a
defensible **effort → FTE → cost → price** estimate, plus the delivery artifacts a
proposal needs: transition plan, transition cost, shift roster, approval trail and
client-ready Excel/PDF exports.

**Current version: `1.65`** (`config.settings.APP_VERSION` is the source of truth).

| Environment | Branch | Container App | URL |
|---|---|---|---|
| **Production** | `main` | `nagarro-ops-estimator` | https://nagarro-ops-estimator.graystone-62d2702b.centralindia.azurecontainerapps.io/ |
| **Staging** | `testing` | `nagarro-ops-estimator-test` | `https://nagarro-ops-estimator-test.<env-suffix>.centralindia.azurecontainerapps.io/` |

> Both scale to zero — the first load after idle takes a few seconds.
> ⚠️ The Azure resource group was repointed during the in-progress migration
> (`AB-ms-cost-estimator`). If a URL above does not resolve, take the authoritative FQDN
> from the deploy job's `App URL:` line in GitHub Actions. See **[HANDOVER.md](HANDOVER.md)**.

---

## 🧭 New to this project? Read these in order

| # | Document | What it gives you |
|---|---|---|
| 1 | **[HANDOVER.md](HANDOVER.md)** | Ownership & access checklist, environment map, known open items, landmines. **Start here.** |
| 2 | This README | What the app does and how a user moves through it. |
| 3 | **[docs/architecture.md](docs/architecture.md)** | Module map, the engine contract, session-state & persistence rules, test map. |
| 4 | **[DEPLOY.md](DEPLOY.md)** | Azure setup, environment variables, staging, CI/CD. |
| 5 | **[RESTORE.md](RESTORE.md)** | Release changelog (v1.0 → v1.65) + how to roll back to any tag. |
| 6 | **[docs/](docs/README.md)** | Per-feature design records, each marked shipped / parked / proposal. |
| 7 | **[COSTS.md](COSTS.md)** · **[UX_PLAN.md](UX_PLAN.md)** | Running Azure cost estimate; UX design-system notes. |

## Quick Start (local)

```bash
pip install -r requirements.txt
streamlit run main.py
```

Opens at `http://localhost:8501`.

```bash
pip install -r requirements-dev.txt
pytest          # 208 tests
```

Deployment is push-to-deploy via GitHub Actions (OIDC, no stored secrets) — see
**[DEPLOY.md](DEPLOY.md)**.

---

## How a session flows

`main.py` is the router. Every visitor passes through a short chain of gates:

```
Email gate  →  Chat / Manual  →  Resume a draft?  →  Single-skill  or  Multi-skill
(@nagarro.com)   (mode_gate)      (blocking modal)     (11 steps)      (10 tabs)
```

**Token deep-links bypass the email gate entirely** — an approval reviewer (`?rev=…`), a
share recipient (`?sh=&v=&k=`) or an orphan-cleanup recipient is identified by their
token, so external recipients can open the link without a login.

**The email gate is not access control.** The `@nagarro.com` address is *self-declared*
(no SSO). It is a *"find my work"* key: it becomes **Prepared By** and owns your drafts
and saved versions. Real sign-in would be Azure Container Apps Authentication (see
DEPLOY.md Step 7).

---

## Multi-skill mode — the primary flow

Estimates a portfolio of skills (Monitoring, Cloud Operations, DevOps, Linux
Administration, …), each with its own levels, coverage, workload and rates. The estimate
is built per **(skill × classification × level)**: volume → AHT → effort → FTE → cost → price.

Ten tabs, in proposal-journey order:

| Tab | Name | Purpose |
|---|---|---|
| 1 | **Skills** | Define skills: family (InfraOps / CloudOps), active levels (L1/L2/L3/Architect), coverage model, architect %, patching. |
| 2 | **Workload** | Per category (Alerts / SRs / Incidents / Changes): monthly total → **classification mix** (incidents P1–P4, alert severities, ITIL change types) → per-class **AHT** → recommended **L1/L2/L3 routing**. All defaults editable. |
| 3 | **Effort & FTE** | Effort build-up and FTE per skill × level, with **Raw → +Buffer & Contingency → Rounded** transparency and a basis selector. |
| 4 | **Rates & Cost** | Genus grade mapping per skill × level, rates, cost and selling price. |
| 5 | **Optimize (AI)** | Deterministic team optimizer — pools adjacent skills to cut the Raw→Rounded rounding loss. Optional LLM narration only. |
| 6 | **Transition** | ITIL-aligned **Transition Strategy**: dates → Gantt, per-skill family-aware plan, woven ITIL process coverage, RACI, exit/sign-off gates, RAID register, governance & comms. |
| 7 | **Transition Cost** | One-time cost: per skill, levels × pre-Go-Live phases, each cell a **fractional resource** capped by the steady-state team, plus a shared SDM row. Never perturbs the monthly run-rate. |
| 8 | **Approve & Export** | Basis tables, approval request/approve/reject by email, Excel + PDF downloads. Sits **after** Transition Cost so approval captures run-rate **and** one-time cost. |
| 9 | **Versions & Compare** | Saved versions (Blob) and side-by-side comparison. |
| 10 | **Shift Plan** | Deterministic coverage/shift roster: ⌈FTE⌉ seats, person × weekday rotational calendar, dual-clock (customer + delivery tz). Read-only appendix. |

Above the tabs: an at-a-glance **KPI overview band**, a global **💾 Save** and **🔗 Share**,
an estimate-level **Lock**, and a **💬 Feedback** control on every tab.

**Skills with zero workload are excluded** from Transition, Transition Cost and the
Roster (`engine.split_skills_by_workload`) — each tab shows an "excluded — no workload"
note. The estimate itself still keeps every skill.

## Single-skill mode — the classic stepper

An 11-step linear stepper (sidebar). Steps 1–8 collect inputs; 9–11 are outputs.

| Step | Name | Purpose |
|------|------|---------|
| 1 | Workload Volumetrics | Estimate details (Customer/RFP name; prepared-by = your Nagarro email) · **Support Coverage Model** · **rate-card source** · **Delivery Location** · monthly alert/ticket volumes |
| 2 | Resolution Split | L1/L2/L3 % + severity distribution + effort minutes. One **L1/L2/L3 buffer %** per category (default 20%) |
| 3 | Patching | Server count + method. **Manual** = min/server × servers; **Tool-Based** = (servers × error-rate %) failed servers × min/failed-server. Plus the patching role assignment |
| 4 | Additional Activities | Auto-derived (per-row Auto toggle) + custom monthly operational hours |
| 5 | Effort Summary | Contingency buffer + **Overhead Role Effort** (Architect/SDM %) + role-hours preview |
| 6 | Coverage & FTE | Shift multiplier (from the Step 1 coverage model), working hours, productive utilisation, FTE |
| 7 | Grade Mapping | Map each role to a Genus grade from the loaded rate card |
| 8 | Costing Inputs | Transition & onboarding planner, expenses, SLA provision, target margin, reporting currency + FX, Raw/Rounded FTE toggle |
| 9 | Results Dashboard | Resource Cost, Executive Summary, Effort breakdown + charts, Resolution detail, FTE Summary, Cost Waterfall, Financial Summary |
| 10 | Approve & Export | Approval workflow; reviewer sees an estimate summary; changing an **approved** estimate is blocked until saved as a new version; What-If sliders; Excel + PDF downloads |
| 11 | Compare | Compare saved/uploaded scenarios side by side |

> Single mode is **feature-frozen but supported**. New work happens in multi mode; the
> guardrail is that single mode must keep working untouched.

---

## Identity, Drafts & Recovery

**Autosave + resume.** Work in progress is silently saved per Customer/RFP on every page
navigation (`__drafts__/<slug>.json`). Immediately after the email gate, if you have
unsaved drafts, a **blocking modal** offers **Resume**, **🗑️ Delete** (two-step confirm)
or **Start afresh**. A browser warn-on-close guards unsaved in-page edits.

**Orphan cleanup.** Abandoned drafts (declined, or untouched > `DRAFT_ORPHAN_DAYS` = 30)
become orphans (`__orphans__/…`). The **🧹 Clean up drafts** indicator opens a review page
that emails a recipient a **tokened link**; deletion is confirmed by the recipient on a
scoped page — never deleted directly on screen.

**Share.** A saved version can be shared with named recipients, each **read-only** or
**editor**, via a per-recipient capability link (`?sh=<slug>&v=<version>&k=<token>`).
Read-only opens the estimate **locked** (exports still work); editor can edit and save a
**new** version — the original is never overwritten. Tokens are individually revocable and
role-changeable from a "People with access" panel.

> Drafts, versions, approvals, shares and feedback all require the **estimates** Blob store;
> emails require **Azure Communication Services + `APP_BASE_URL`**. Without them the app
> degrades gracefully (a copyable link instead of an email). The email gate always runs.

---

## Key Design Decisions

### Workload → Role Hours (the core calculation)

1. Volumes and average minutes per category (Alerts, SRs, Incidents, Changes)
2. Resolution split — "X% of Alerts resolved by L1, Y% by L2, Z% by L3" — must sum to 100% per category
3. `L1 hours = Σ (category_hours × L1_pct)` across categories
4. Architect/SDM hours are additive overhead (see SDM note below)
5. Patching hours added to the designated role (user-selectable, default L2)

In multi mode this runs per skill, and `active_levels` is **authoritative** — the engine
renormalizes routing onto the levels a skill actually staffs. Levels are *not* cascade-gated
(an L2/L3-only or L1-only skill is valid). **Architect is gated on L3** being active.

### FTE Rounding
- `Final FTE = CEILING(Raw FTE, 0.5)`, minimum 0.5 FTE for any role with hours > 0
- Coverage multiplier applies to **L1/L2 only**: `FTE = Raw FTE × (weekly_coverage_hours ÷ 40)`
- **Raw vs Rounded** is a first-class toggle (multi defaults to **Raw**); both bases are
  always shown for leadership. A large Raw→Rounded gap means many small cells each hitting
  the 0.5 minimum — the fix is **pooling** (Optimize tab), not billing raw.
- **SDM (Option A):** SDM% is a fixed fraction of *one* SDM FTE, unrounded — not a
  percentage of total effort.

### Cost → Price
```
Role Cost     = Billed Hours × Hourly Rate (INR)   # Billed Hours = FTE × monthly working hours
Delivery Cost = Σ Role Costs + Additional Expenses + SLA Provision
Selling Price = Delivery Cost ÷ (1 − Margin%)
```
Transition / onboarding cost is **one-time** and reported separately — it is **not**
included in the monthly delivery cost. Transition selling price = `cost ÷ (1 − margin)`.

---

## Effort Defaults & Auto-Derivation

All defaults are **editable recommendations**, and every recommender is a **deterministic
rule, not an LLM** — so estimates are reproducible and defensible in front of a client.

**Patching** (default **20 servers**):
- **Manual** = min/server × servers (default **45 min/server**)
- **Tool-Based** = `round(servers × error-rate %)` failed servers × min/failed-server
  (default **30 min/failed server**, **10%** error rate)

**Auto-derived additional activities** — each has an **Auto** toggle (on by default) and a
tooltip showing its formula. Monthly hours = (Σ terms) ÷ 60:
- **Scheduled Maintenance** = 30 min × servers
- **RCA** = 360 min × incidents
- **Problem Management** = 600 min × incidents
- **Documentation & KB** = 30 min × servers + 120 × incidents + 15 × service requests + 120 × changes

Coefficients live in `config.settings.ACTIVITY_FORMULAS` / `PATCHING_EFFORT_DEFAULTS`.
Classification defaults live in `MS_CLASSIFICATIONS` / `MS_DEFAULT_DIST` / `MS_DEFAULT_AHT` /
`MS_DEFAULT_ROUTING` — all tunable.

## Rate Card Format

Excel (.xlsx) with columns: **Country, Location, Genus, Hourly Rate, Rate Currency**

- `sample_rate_card.xlsx` (tracked) — non-sensitive sample.
- `genus_rate_card.xlsx` — the **real** card. **Gitignored**; it lives in Azure Blob and
  auto-loads at runtime via `RATECARD_BLOB`. Never commit it.

Step 1 (single) / the Skills tab (multi) lets you pick any **country / location** in the
card; grade mapping picks a **Genus** grade per role. CloudOps skills price off
`CLOUD-INFRASTRUCTURE` genus rows via `config.grade_eligibility(band, family)`, with a
graceful fallback if the card has no cloud rows. Non-INR rates convert to INR using the
exchange rates you enter.

## Multi-Currency Reporting

All internal calculations are in INR. You choose a **reporting currency** (default INR);
the dashboard, Excel and PDF display final figures in it using `1 <CUR> = X INR` rates you
provide.

## Outputs

- **Excel Workbook (formulas)** — a fully formula-driven replica of the app, also attached to
  the approval email. **Every input lives on one editable `Inputs` sheet** (the only unlocked
  cells); a client-facing Summary tab, a page per step, and a live Dashboard are **locked
  formulas** referencing `Inputs`. Change an input and everything recalculates **without the
  app**. Grey "App value" cells cross-check the tool — formulas are recalc-verified to match
  the engine to the rupee.
- **Multi-skill workbook** — includes a **Live Model** sheet with editable inputs and live
  formulas reproducing the engine per skill × level (pooling is a static note, not live).
- **Transition workbook** and **Roster workbook** for the respective tabs.
- **PDF proposal** — client-facing branded quote.
- **Scenario comparison** — save scenarios in-session and compare effort / FTE / cost / price
  (or import/export as JSON).
- **What-If analysis** (single mode) — live sliders for volume, margin, contingency and
  coverage; never mutate saved inputs. Save a what-if as a new version to bake the drivers in.
- **Approval workflow** — the email carries an estimate summary in the body plus the editable
  Excel workbook as an attachment; the reviewer approves/rejects via a tokened link. The
  preparer never sees the link (a **Resend** button covers "didn't receive it"). Changing an
  **approved** estimate blocks downloads/approval until it is saved as a new draft version.
- **Saved versions** — versioned, timestamped, keyed by Customer/RFP name (Azure Blob),
  reloadable across sessions. A multi version's summary also carries the one-time transition
  cost and the roster's deployable headcount.
- **Feedback capture** — a 💬 popover on every page writes to Blob (`__feedback__/`), with an
  admin viewer and CSV export.

## Architecture

`modules/calculations/engine.py` holds the two pure pipelines —
`compute_full_model(state)` (single) and `compute_multi_skill_model(state)` (multi).
The dashboards, exports, scenario comparison, transition, roster and tests all call them,
so displayed and exported numbers cannot drift apart.

Full module map, the session-state/persistence contract and the test map are in
**[docs/architecture.md](docs/architecture.md)**.

## Extending

Nearly all configuration lives in `config/settings.py`:

| Change | Knob |
|---|---|
| App/brand name | `APP_NAME`, `APP_NAME_SHORT`, `ORG_NAME` |
| Version stamp | `APP_VERSION` (bump on each promotion to prod) |
| Colours (app, Excel, PDF, charts) | `THEME` — mirrored in `assets/styles.css :root` |
| New roles | `ALL_ROLES` + `GRADE_ELIGIBILITY` |
| Coverage models | `COVERAGE_MODELS` |
| Currencies | `REPORTING_CURRENCIES`, `CURRENCY_SYMBOLS` |
| Patching defaults | `PATCHING_EFFORT_DEFAULTS`, `DEFAULT_NUM_SERVERS` |
| Auto-derived activities | `ACTIVITY_FORMULAS` |
| Classification model | `MS_CLASSIFICATIONS`, `MS_DEFAULT_DIST`, `MS_DEFAULT_AHT`, `MS_DEFAULT_ROUTING` |
| Transition phases & cost | `DEFAULT_TRANSITION_PHASES`, `TRANSITION_PARTICIPATION`, `TRANSITION_PHASE_UTILISATION` |
| Draft orphan age | `DRAFT_ORPHAN_DAYS` |

> ⚠️ `DEMO_SEED_DATA = True` is currently set — the app pre-fills a demo multi-skill
> scenario. **This must be turned off before real client use.** See
> **[HANDOVER.md](HANDOVER.md) → Open items**.
