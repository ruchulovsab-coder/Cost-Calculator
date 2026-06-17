# Cloud & Infrastructure Practices — Ops Effort Estimation Tool

**Nagarro | Cloud & Infrastructure Practices · End-to-End Delivery Model**

[![Deploy to Azure Container Apps](https://github.com/ruchulovsab-coder/Cost-Calculator/actions/workflows/azure-deploy.yml/badge.svg)](https://github.com/ruchulovsab-coder/Cost-Calculator/actions/workflows/azure-deploy.yml)

🔗 **Live app:** https://nagarro-ops-estimator.graystone-62d2702b.centralindia.azurecontainerapps.io/
*(Azure Container Apps, scale-to-zero — first load after idle wakes in a few seconds.)*

---

## Quick Start (local)

```bash
pip install -r requirements.txt
streamlit run main.py
```

Opens at `http://localhost:8501`

## Deploying

Push-to-deploy to Azure via GitHub Actions (OIDC, no stored secrets). See **[DEPLOY.md](DEPLOY.md)**.

---

## Step Flow

The flow is an **11-step** linear stepper (sidebar). Steps 1–8 collect inputs;
9–11 are outputs.

| Step | Name | Purpose |
|------|------|---------|
| 1 | Workload Volumetrics | Estimate details (Customer/RFP name, prepared by) · **Support Coverage Model** · **rate-card source** (collapsible grades table) · **Delivery Location** (country/location) · monthly alert/ticket volumes |
| 2 | Resolution Split | L1/L2/L3 % + severity distribution + effort minutes. One **L1/L2/L3 buffer %** per category, set at the category heading (default 20%) |
| 3 | Patching | Server count + method. **Manual** = min/server × servers; **Tool-Based** = (servers × error-rate %) failed servers × min/failed-server. Plus the patching role assignment |
| 4 | Additional Activities | Auto-derived (per-row Auto toggle) + custom monthly operational hours |
| 5 | Effort Summary | Contingency buffer + **Overhead Role Effort** (Architect/SDM/SSDM %) + role-hours preview |
| 6 | Coverage & FTE | Shift multiplier (from the Step 1 coverage model), working hours, productive utilisation, FTE |
| 7 | Grade Mapping | Map each role to a Genus grade from the loaded rate card |
| 8 | Costing Inputs | Transition, expenses, SLA provision, target margin, reporting currency + FX, Raw/Rounded FTE toggle, plus a compact estimate headline |
| 9 | Results Dashboard | Resource Cost, Executive Summary, Effort breakdown + charts, Resolution detail, FTE Summary, Cost Waterfall, Financial Summary |
| 10 | Approve & Export | Approval workflow (request / approve / reject), What-If sliders, downloads (Excel report, Editable Excel, PDF) |
| 11 | Compare | Compare saved/uploaded scenarios side by side |

> **History note:** through v1.1 this was a **9-step** flow with the rate card,
> coverage model and delivery location on later pages, and a single combined
> "Cost, Pricing & Dashboard" Step 8. v1.2 relocated those inputs to Step 1 and
> split the old Step 8 into Steps 8–11.

---

## Key Design Decisions

### Workload → Role Hours (the core calculation)

1. User enters volumes and avg minutes for Alerts, SRs, Incidents, Changes
2. User defines resolution split: "X% of Alerts resolved by L1, Y% by L2, Z% by L3" — must sum to 100% per category
3. System calculates: `L1 hours = Σ (category_hours × L1_pct)` for all categories
4. Architect/SDM/SSDM hours = user-defined % of total operational effort (additive overhead)
5. Patching hours added to the designated role (user-selectable, default L2)

### FTE Rounding
- `Final FTE = CEILING(Raw FTE, 0.5)`
- Minimum 0.5 FTE for any role with hours > 0
- Coverage multiplier (L1/L2 only): `FTE = Raw FTE × (weekly_coverage_hours ÷ 40)`
- Step 8 has a **Raw vs Rounded FTE** toggle: costing/Executive Summary can be
  shown on the exact (raw) FTE or the rounded delivery FTE.

### Cost → Price
```
Role Cost     = Billed Hours × Hourly Rate (INR)   # Billed Hours = FTE × monthly working hours
Delivery Cost = Σ Role Costs + Additional Expenses + SLA Provision
Selling Price = Delivery Cost ÷ (1 − Margin%)
```
Transition / onboarding cost is **one-time** and reported separately — it is **not**
included in the monthly delivery cost.

---

## Effort Defaults & Auto-Derivation

All defaults are **editable recommendations**.

**Patching** (Step 3), default **20 servers**:
- **Manual** = min/server × servers (default **45 min/server**) — every server is patched by hand.
- **Tool-Based** = `round(servers × error-rate %)` failed servers × min/failed-server
  (default **30 min/failed server**, **10%** error rate). Only the servers the tool
  fails on need manual effort; e.g. 100 servers × 15% = 15 failed × 30 min = 7.5 hrs/month.

**Auto-derived additional activities** (Step 4) — each has an **Auto** toggle (on by
default) and a tooltip/expander showing its formula. Monthly hours = (Σ terms) ÷ 60:
- **Scheduled Maintenance** = 30 min × servers
- **RCA** = 360 min × incidents
- **Problem Management** = 600 min × incidents
- **Documentation & KB** = 30 min × servers + 120 × incidents + 15 × service requests + 120 × changes

Switch **Auto** off on any row to enter your own value. Coefficients live in
`config.settings.ACTIVITY_FORMULAS` / `PATCHING_EFFORT_DEFAULTS`.

## Rate Card Format

Excel (.xlsx) with columns: **Country, Location, Genus, Hourly Rate, Rate Currency**

Sample rate card included: `sample_rate_card.xlsx`

**Step 1** lets you load the card and pick any **country / location** present in it
(defaults to India); **Step 7** maps each role to a Genus grade. Rates quoted in a
non-INR currency are converted to INR using the exchange rates you enter on Step 8.

## Multi-Currency Reporting

All internal calculations are in INR. On Step 8 you can choose a **reporting
currency** (default INR) and the output dashboard, Excel report and PDF proposal
display the final figures in that currency, using `1 <CUR> = X INR` rates you
provide.

## Outputs

- **Excel report** — multi-sheet workbook (exec summary, effort, FTE, costs, audit)
- **PDF proposal** — client-facing branded quote
- **Scenario comparison** — save scenarios in-session and compare effort / FTE /
  cost / price side by side (or import/export as JSON)
- **What-If analysis** — live sliders (Step 10) for volume, margin, contingency
  and coverage; never mutate your saved inputs
- **Approval workflow** (Step 10) — request approval by email; reviewer approves /
  rejects via a tokened link; preparer sees status only
- **Saved Calculations** — versioned, timestamped saves keyed by Customer/RFP name
  (Azure Blob), reloadable across sessions

## Architecture

`modules/calculations/engine.py::compute_full_model(state)` is the single pure
pipeline (effort → role hours → FTE → cost → price). The dashboard, exports,
scenario comparison and tests all call it, so displayed and exported numbers
cannot drift apart.

## Testing

```bash
pip install -r requirements-dev.txt
pytest
```

---

## Extending

All configuration in `config/settings.py`:
- App/brand name → `APP_NAME`, `ORG_NAME`
- New roles → `ALL_ROLES` + `GRADE_ELIGIBILITY`
- New coverage models → `COVERAGE_MODELS`
- Reporting currencies + symbols → `REPORTING_CURRENCIES`, `CURRENCY_SYMBOLS`
- Patching defaults → `PATCHING_EFFORT_DEFAULTS`, `DEFAULT_NUM_SERVERS`
- Auto-derived activity formulas → `ACTIVITY_FORMULAS`
