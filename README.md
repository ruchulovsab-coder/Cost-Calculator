# IT Managed Services Calculator v2

**Shared Managed Services | End-to-End Delivery Model**

---

## Quick Start

```bash
pip install -r requirements.txt
streamlit run main.py
```

Opens at `http://localhost:8501`

---

## 8-Step Flow

| Step | Name | Purpose |
|------|------|---------|
| 1 | Workload Volumetrics | Monthly alert/ticket volumes + avg effort minutes |
| 2 | Resolution Split | L1/L2/L3 % per ticket category + overhead roles + patching role |
| 3 | Patching | Server patching scope and method |
| 4 | Additional Activities | Other monthly operational hours |
| 5 | Effort Summary | Contingency buffer + role hours preview |
| 6 | Coverage & FTE | Coverage model, shift multiplier, FTE calculation |
| 7 | Rate Card & Mapping | Upload Genus rate card, select location, map roles |
| 8 | Cost, Pricing & Dashboard | Full cost model + output dashboard + export |

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

### Cost → Price
```
Role Cost     = Hours × Hourly Rate (converted to INR)
Delivery Cost = Σ Role Costs + Transition Cost + Expenses + SLA Provision
Selling Price = Delivery Cost ÷ (1 − Margin%)
```

---

## Rate Card Format

Excel (.xlsx) with columns: **Country, Location, Genus, Hourly Rate, Rate Currency**

Sample rate card included: `sample_rate_card.xlsx`

Step 7 lets you pick any **country / location** present in the card (defaults to
India). Rates quoted in a non-INR currency are converted to INR using the
exchange rates you enter on Step 8.

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
- **What-If analysis** — live sliders on the dashboard for volume, margin,
  contingency and coverage

## Architecture

`modules/calculations/engine.py::compute_full_model(state)` is the single pure
pipeline (effort → role hours → FTE → cost → price). The dashboard, exports,
scenario comparison and tests all call it, so displayed and exported numbers
cannot drift apart.

## Testing

```bash
pip install -r requirements.txt
pytest
```

---

## Extending

All configuration in `config/settings.py`:
- New roles → `ALL_ROLES` + `GRADE_ELIGIBILITY`
- New coverage models → `COVERAGE_MODELS`
- New currencies → `DEFAULT_CURRENCIES`
