"""
Editable Excel model — exports the calculation as a workbook of **live formulas**
(not static values), so Excel-first users can change the headline drivers and see
results recalculate in Excel.

Yellow cells = editable inputs. White cells = formulas mirroring the app's engine.
A faint "App value" column echoes the app's computed result so users can confirm the
Excel recalculation matches. Currency is INR (the app's base).
"""
import io
from datetime import date

import openpyxl
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
from openpyxl.utils import get_column_letter
import streamlit as st

from config.settings import ALL_ROLES, COVERAGE_APPLICABLE_ROLES, CATEGORY_SUBLABELS, APP_NAME
from modules.state.session_manager import run_model

NAVY = "1F3864"; YEL = "FFF2CC"; LB = "D5E8F0"; GREY = "767676"
_thin = Side(style="thin", color="CCCCCC")
BORDER = Border(left=_thin, right=_thin, top=_thin, bottom=_thin)

def _fill(c): return PatternFill("solid", fgColor=c)
def _hdr(c, text):
    c.value = text; c.fill = _fill(NAVY); c.font = Font(color="FFFFFF", bold=True, size=10)
    c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True); c.border = BORDER
def _edit(c, value, fmt="#,##0"):
    c.value = value; c.fill = _fill(YEL); c.number_format = fmt; c.border = BORDER
def _calc(c, formula, fmt="#,##0.0"):
    c.value = formula; c.number_format = fmt; c.border = BORDER
def _lbl(c, text, bold=False):
    c.value = text; c.font = Font(bold=bold, size=10)


CAT_DISPLAY = [("alerts", "Monitoring Alerts"), ("service_requests", "Service Requests"),
               ("incidents", "Incidents"), ("changes", "Change Requests")]


def generate_excel_model() -> bytes:
    model = st.session_state.get("_model") or run_model()
    ss = st.session_state

    monthly = float(ss.get("monthly_working_hours", 160) or 160)
    util = float(ss.get("productive_utilisation", 75) or 75)
    cov = float(model.get("coverage_multiplier", 1.0) or 1.0)
    cont = float(ss.get("contingency_pct", 0) or 0)
    ovh = ss.get("overhead_pcts", {}) or {}
    servers = int(ss.get("num_servers", 0) or 0)
    method = ss.get("patching_method") or "Manual"
    patch_min = float(ss.get("manual_effort_per_server", 45) if method == "Manual"
                      else ss.get("auto_effort_per_server", 30) or 0)
    patch_included = ss.get("patching_included") == "Yes"
    patch_role = ss.get("patching_role", "L2") or "L2"
    expenses = float(model["cost_result"].get("additional_expenses", 0) or 0)
    sla = float(ss.get("sla_provision_pct", 0) or 0) if ss.get("sla_provision_included") == "Yes" else 0.0
    margin = float(model["price_result"].get("margin_pct", 0) or 0)
    rates = {r: float(model["resource_costs"].get(r, {}).get("rate_inr", 0) or 0) for r in ALL_ROLES}

    add_dist = {r: 0.0 for r in ALL_ROLES}
    for act in ss.get("additional_activities", []) or []:
        h = float(act.get("hours", 0) or 0); dist = act.get("dist", {}) or {}
        for r in ALL_ROLES:
            add_dist[r] += h * float(dist.get(r, 0) or 0) / 100.0

    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Editable Model"
    ws.column_dimensions["A"].width = 22
    for col in "BCDEFGHIJKLMN":
        ws.column_dimensions[col].width = 12

    ws["A1"] = APP_NAME; ws["A1"].font = Font(bold=True, size=13, color=NAVY)
    ws["A2"] = "Editable model — yellow cells are inputs; white cells are live formulas. Currency: INR."
    ws["A2"].font = Font(italic=True, size=9, color=GREY)
    ws["A3"] = f"Generated {date.today()}"; ws["A3"].font = Font(size=9, color=GREY)

    r = 5
    # ── Assumptions ──────────────────────────────────────────────
    ws.cell(r, 1, "ASSUMPTIONS").font = Font(bold=True, color=NAVY); r += 1
    A = {}  # name -> cell coordinate
    def assume(label, value, fmt="#,##0.0"):
        nonlocal r
        _lbl(ws.cell(r, 1), label)
        _edit(ws.cell(r, 2), value, fmt)
        coord = ws.cell(r, 2).coordinate; r += 1
        return coord
    A["monthly"] = assume("Monthly working hrs / FTE", monthly, "#,##0")
    A["util"] = assume("Productive utilisation %", util, "#,##0")
    A["cov"] = assume("Coverage multiplier (L1/L2)", cov, "#,##0.00")
    A["cont"] = assume("Contingency %", cont, "#,##0")
    A["ovhArch"] = assume("Overhead % — Architect", float(ovh.get("Architect", 0) or 0), "#,##0")
    A["ovhSDM"] = assume("Overhead % — SDM", float(ovh.get("SDM", 0) or 0), "#,##0")
    A["ovhSSDM"] = assume("Overhead % — SSDM", float(ovh.get("SSDM", 0) or 0), "#,##0")
    A["servers"] = assume("Patching — servers", servers if patch_included else 0, "#,##0")
    A["patchmin"] = assume("Patching — min/server", patch_min, "#,##0")
    _lbl(ws.cell(r, 1), "Patching effort (hrs)")
    _calc(ws.cell(r, 2), f"={A['servers']}*{A['patchmin']}/60"); A["patchhrs"] = ws.cell(r, 2).coordinate; r += 1
    _lbl(ws.cell(r, 1), f"Patching assigned to"); ws.cell(r, 2, patch_role); r += 1
    A["expenses"] = assume("Additional expenses (INR)", expenses, "#,##0")
    A["sla"] = assume("SLA provision %", sla, "#,##0")
    A["margin"] = assume("Target gross margin %", margin, "#,##0")
    r += 1

    # ── Per-role rates + additional hours ────────────────────────
    ws.cell(r, 1, "PER-ROLE RATES & ADDITIONAL HOURS").font = Font(bold=True, color=NAVY); r += 1
    _hdr(ws.cell(r, 1), "Role"); _hdr(ws.cell(r, 2), "Rate (INR/hr)"); _hdr(ws.cell(r, 3), "Additional hrs")
    r += 1
    rate_cell = {}; add_cell = {}
    for role in ALL_ROLES:
        _lbl(ws.cell(r, 1), role)
        _edit(ws.cell(r, 2), round(rates[role], 2), "#,##0")
        rate_cell[role] = ws.cell(r, 2).coordinate
        _edit(ws.cell(r, 3), round(add_dist[role], 2), "#,##0.0")
        add_cell[role] = ws.cell(r, 3).coordinate
        r += 1
    r += 1

    # ── Ticket workload table (the core, buffered role hours) ────
    ws.cell(r, 1, "TICKET WORKLOAD → ROLE HOURS (incl. buffer)").font = Font(bold=True, color=NAVY); r += 1
    headers = ["Category", "Severity/Type", "Count", "Min", "L1 %", "L1 Buf%",
               "L2 %", "L2 Buf%", "L3 %", "L3 Buf%", "L1 Hrs", "L2 Hrs", "L3 Hrs"]
    for i, h in enumerate(headers, 1):
        _hdr(ws.cell(r, i), h)
    r += 1
    ticket_first = r
    from config.settings import DEFAULT_ROLE_BUFFER_PCT
    for cat_key, cat_label in CAT_DISPLAY:
        cat = ss.get(cat_key, {}) or {}
        for label in CATEGORY_SUBLABELS[cat_key]:
            row = cat.get(label, {})
            _lbl(ws.cell(r, 1), cat_label); _lbl(ws.cell(r, 2), label)
            _edit(ws.cell(r, 3), int(row.get("count", 0) or 0), "#,##0")
            _edit(ws.cell(r, 4), float(row.get("minutes", 0) or 0), "#,##0")
            _edit(ws.cell(r, 5), float(row.get("L1_pct", 0) or 0), "#,##0")
            _edit(ws.cell(r, 6), float(row.get("L1_buffer", DEFAULT_ROLE_BUFFER_PCT)), "#,##0")
            _edit(ws.cell(r, 7), float(row.get("L2_pct", 0) or 0), "#,##0")
            _edit(ws.cell(r, 8), float(row.get("L2_buffer", DEFAULT_ROLE_BUFFER_PCT)), "#,##0")
            _edit(ws.cell(r, 9), float(row.get("L3_pct", 0) or 0), "#,##0")
            _edit(ws.cell(r, 10), float(row.get("L3_buffer", DEFAULT_ROLE_BUFFER_PCT)), "#,##0")
            # role hours = count*min/60 * pct/100 * (1+buf/100)
            _calc(ws.cell(r, 11), f"=C{r}*D{r}/60*E{r}/100*(1+F{r}/100)")
            _calc(ws.cell(r, 12), f"=C{r}*D{r}/60*G{r}/100*(1+H{r}/100)")
            _calc(ws.cell(r, 13), f"=C{r}*D{r}/60*I{r}/100*(1+J{r}/100)")
            r += 1
    ticket_last = r - 1
    # totals row
    _lbl(ws.cell(r, 1), "TOTAL", bold=True)
    _calc(ws.cell(r, 3), f"=SUM(C{ticket_first}:C{ticket_last})", "#,##0")
    for col in (11, 12, 13):
        L = get_column_letter(col)
        _calc(ws.cell(r, col), f"=SUM({L}{ticket_first}:{L}{ticket_last})")
    tick = {"L1": f"K{r}", "L2": f"L{r}", "L3": f"M{r}"}
    # non-buffered category hours (for overhead/contingency base)
    nobuf_total = f"SUMPRODUCT(C{ticket_first}:C{ticket_last},D{ticket_first}:D{ticket_last})/60"
    r += 2

    # ── Derived: effort, FTE, cost, price ────────────────────────
    ws.cell(r, 1, "RESULTS (formulas)").font = Font(bold=True, color=NAVY); r += 1
    _hdr(ws.cell(r, 1), "Metric"); _hdr(ws.cell(r, 2), "Formula result"); _hdr(ws.cell(r, 3), "App value")
    r += 1

    def result(label, formula, app_value, fmt="#,##0.0"):
        nonlocal r
        _lbl(ws.cell(r, 1), label)
        _calc(ws.cell(r, 2), formula, fmt)
        coord = ws.cell(r, 2).coordinate
        ws.cell(r, 3, round(app_value, 2)); ws.cell(r, 3).number_format = fmt
        ws.cell(r, 3).font = Font(color=GREY)
        r += 1
        return coord

    total_ops = result("Total operational effort (pre-buffer)",
                        f"={nobuf_total}+{A['patchhrs']}+SUM({add_cell['L1']},{add_cell['L2']},{add_cell['L3']},{add_cell['Architect']},{add_cell['SDM']},{add_cell['SSDM']})",
                        model["base_effort"])
    total_eff = result("Total effort incl. contingency",
                       f"={total_ops}*(1+{A['cont']}/100)", model["total_effort"])
    prod = result("Productive hrs / FTE",
                  f"={A['monthly']}*{A['util']}/100", model["productive_hours"], "#,##0.0")

    # Per-role assembled hours, FTE, cost
    r += 1
    ws.cell(r, 1, "Per role").font = Font(bold=True)
    _hdr(ws.cell(r, 2), "Hours"); _hdr(ws.cell(r, 3), "FTE"); _hdr(ws.cell(r, 4), "Cost (INR)")
    _hdr(ws.cell(r, 5), "App FTE"); _hdr(ws.cell(r, 6), "App Cost"); r += 1
    fte_cells = {}; cost_cells = {}
    OVH = {"Architect": A["ovhArch"], "SDM": A["ovhSDM"], "SSDM": A["ovhSSDM"]}
    raw_basis = model.get("fte_basis") == "raw"
    fte_key = "raw_fte" if raw_basis else "final_fte"
    for role in ALL_ROLES:
        _lbl(ws.cell(r, 1), role)
        # base ops for the role: ticket (L1/L2/L3) + additional + patching (if assigned)
        base = []
        if role in tick:
            base.append(tick[role])
        base.append(add_cell[role])
        patch_term = f'+IF("{patch_role}"="{role}",{A["patchhrs"]},0)'
        base_expr = "+".join(base) if base else "0"
        ovh_term = f"+{OVH[role]}/100*{total_eff}" if role in OVH else ""
        hours_formula = f"=({base_expr}{patch_term})*(1+{A['cont']}/100){ovh_term}"
        _calc(ws.cell(r, 2), hours_formula); hcell = ws.cell(r, 2).coordinate
        # FTE: coverage multiplier for L1/L2 only. Rounded basis = CEILING to 0.5 with
        # a 0.5 minimum; Raw basis = exact adjusted FTE (matches the app's FTE toggle).
        covf = f"*{A['cov']}" if role in COVERAGE_APPLICABLE_ROLES else ""
        if raw_basis:
            fte_formula = f"=IF({hcell}>0,{hcell}/{prod}{covf},0)"
        else:
            fte_formula = f"=IF({hcell}>0,MAX(CEILING({hcell}/{prod}{covf},0.5),0.5),0)"
        _calc(ws.cell(r, 3), fte_formula, "#,##0.00"); fte_cells[role] = ws.cell(r, 3).coordinate
        _calc(ws.cell(r, 4), f"={fte_cells[role]}*{A['monthly']}*{rate_cell[role]}", "#,##0")
        cost_cells[role] = ws.cell(r, 4).coordinate
        ws.cell(r, 5, round(model["fte_result"].get(role, {}).get(fte_key, 0), 2)).font = Font(color=GREY)
        ws.cell(r, 6, round(model["resource_costs"].get(role, {}).get("cost_inr", 0), 0)).font = Font(color=GREY)
        ws.cell(r, 5).number_format = "#,##0.00"; ws.cell(r, 6).number_format = "#,##0"
        r += 1
    # cost/price chain
    r += 1
    res_cost = result("Total resource cost (INR)",
                      "=" + "+".join(cost_cells[r_] for r_ in ALL_ROLES),
                      model["total_resource_cost"], "#,##0")
    deliver = result("Delivery cost (INR)",
                     f"=({res_cost}+{A['expenses']})*(1+{A['sla']}/100)",
                     model["cost_result"]["total_delivery_cost"], "#,##0")
    result("Selling price (INR)",
           f"={deliver}/(1-{A['margin']}/100)",
           model["price_result"]["selling_price"], "#,##0")
    total_fte = result("Total FTE",
                       "=" + "+".join(fte_cells[r_] for r_ in ALL_ROLES),
                       model["total_fte"], "#,##0.00")

    r += 1
    ws.cell(r, 1, "Edit any yellow cell and Excel recalculates. 'App value' columns show the "
                  "tool's result for cross-checking.").font = Font(italic=True, size=9, color=GREY)

    buf = io.BytesIO(); wb.save(buf); buf.seek(0)
    return buf.getvalue()
