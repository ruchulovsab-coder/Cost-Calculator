"""
Multi-skill Excel export — a multi-sheet workbook built from the multi-skill engine.

State-driven (no session reads), so it's unit-testable: pass a `state` dict (the same
shape `_build_multi_state()` produces) or let it read the live one. The numbers are
written straight from `compute_multi_skill_model`, so the workbook equals the engine
(a faithful values report, not a live-formula spreadsheet).

Sheets: Executive Summary · Skills · Effort Build-up · Team (FTE) · Rates ·
Optimization · Workload Detail · Inputs.
Styling helpers are reused from the single-mode exporter so the look matches.
"""
import io
from datetime import date

import openpyxl

from config.settings import APP_NAME, hx
from modules.calculations.engine import compute_multi_skill_model, calc_patching_effort
from modules.outputs.excel_export import (
    _hrow, _drow, _title, _add_logo, NAVY, BLUE, LB, ACCENT,
    F_INR, F_NUM1, F_FTE, F_RAW, F_PCT,
)

LEVELS4 = ["L1", "L2", "L3", "Architect"]


def _sum_role_hours(ps):
    return sum(ps["role_hours"].get(l, 0.0) for l in LEVELS4)


# ── Sheets ───────────────────────────────────────────────────────────────────
def _exec(wb, model, baseline, state):
    ws = wb.create_sheet("Executive Summary")
    _add_logo(ws)
    _title(ws, f"{APP_NAME} — Multi-skill Executive Summary")
    cr, pr = model["cost_result"], model["price_result"]
    staffed = sum(_sum_role_hours(ps) for ps in model["per_skill"].values())
    _hrow(ws, 5, ["Metric", "Value", "Unit"], [40, 22, 14])
    rows = [
        ("Skills in scope", len(model["per_skill"]), ""),
        ("Delivery location",
         (state.get("delivery_country") or "—") +
         (f" / {state.get('delivery_location')}" if state.get("delivery_location") else ""), ""),
        ("TOTAL STAFFED EFFORT (L1–Architect)", round(staffed, 1), "Hrs/Month"),
        ("SDM hours", round(model["sdm_hours"], 1), "Hrs/Month"),
        ("TOTAL FTE", round(model["total_fte"], 1), "FTE"),
        ("Resource cost", cr.get("resource_cost", 0), "INR"),
        ("Delivery cost", cr.get("total_delivery_cost", 0), "INR"),
        ("Gross margin", pr.get("margin_pct", 0), "%"),
        ("MONTHLY SELLING PRICE", pr.get("selling_price", 0), "INR"),
        ("Gross profit", pr.get("gross_profit", 0), "INR"),
    ]
    saved = baseline["total_fte"] - model["total_fte"]
    if saved > 1e-9:
        rows += [
            ("— Optimisation applied —", "", ""),
            ("Baseline team (no sharing)", round(baseline["total_fte"], 1), "FTE"),
            ("FTE saved by sharing", round(saved, 1), "FTE"),
            ("Cost saved", baseline["total_resource_cost"] - model["total_resource_cost"], "INR"),
        ]
    fmt = {"": None, "Hrs/Month": F_NUM1, "FTE": F_FTE, "INR": F_INR, "%": F_PCT}
    for i, (m, v, u) in enumerate(rows, 6):
        _drow(ws, i, [m, v, u], total=str(m).isupper(), fmts=[None, fmt.get(u), None])


def _skills(wb, model, names):
    ws = wb.create_sheet("Skills")
    _title(ws, "Per-skill Effort, FTE & Cost")
    _hrow(ws, 5, ["Skill", "Family", "Coverage", "L1 hrs", "L2 hrs", "L3 hrs", "Arch hrs",
                  "Staffed hrs", "Monthly Cost"],
          [22, 12, 10, 10, 10, 10, 10, 12, 16])
    fmts = [None, None, None, F_NUM1, F_NUM1, F_NUM1, F_NUM1, F_NUM1, F_INR]
    r = 6
    tot = {l: 0.0 for l in LEVELS4}
    tcost = tstaff = 0.0
    for sid, ps in model["per_skill"].items():
        rh = ps["role_hours"]
        staffed = _sum_role_hours(ps)
        for l in LEVELS4:
            tot[l] += rh.get(l, 0.0)
        tstaff += staffed
        tcost += ps.get("cost", 0.0)
        _drow(ws, r, [names.get(sid, sid), ps["genus_category"], ps["coverage_model"],
                      round(rh["L1"], 1), round(rh["L2"], 1), round(rh["L3"], 1),
                      round(rh["Architect"], 1), round(staffed, 1), round(ps.get("cost", 0.0))], fmts=fmts)
        r += 1
    _drow(ws, r, ["TOTAL", "", ""] + [round(tot[l], 1) for l in LEVELS4] +
          [round(tstaff, 1), round(tcost)], total=True, fmts=fmts)


def _buildup(wb, model, names):
    ws = wb.create_sheet("Effort Build-up")
    _title(ws, "Raw → Buffered → Final (per skill × level)")
    _hrow(ws, 5, ["Skill", "Level", "Raw hrs", "Buffer %", "Buffered hrs", "Final hrs",
                  "Raw FTE", "Final FTE"], [22, 10, 11, 9, 12, 11, 10, 10])
    fmts = [None, None, F_NUM1, F_PCT, F_NUM1, F_NUM1, F_RAW, F_FTE]
    r = 6
    for sid, ps in model["per_skill"].items():
        for lvl in LEVELS4:
            d = ps["breakdown"][lvl]
            if d["raw"] <= 1e-9 and d["final"] <= 1e-9:
                continue
            _drow(ws, r, [names.get(sid, sid), lvl, round(d["raw"], 1), round(d["buffer_pct"], 0),
                          round(d["buffered"], 1), round(d["final"], 1),
                          round(d["fte_raw"], 3), round(d["fte_staffed"], 1)], fmts=fmts)
            r += 1


def _team(wb, model, names):
    ws = wb.create_sheet("Team (FTE)")
    _title(ws, "Team composition — Raw vs Final FTE by skill × level")
    sdm = next((x for x in model["resources"] if x["level"] == "SDM"), None)
    sdm_raw = float(sdm["raw_fte"]) if sdm else 0.0
    sdm_fin = float(sdm["fte"]) if sdm else 0.0

    def block(row0, title, kind, sdm_val):
        ws.cell(row0, 1, title).font = openpyxl.styles.Font(name="Calibri", bold=True, color=NAVY, size=11)
        _hrow(ws, row0 + 1, ["Skill", "L1", "L2", "L3", "Architect", "Total"],
              [22, 10, 10, 10, 12, 10])
        fmts = [None, F_FTE, F_FTE, F_FTE, F_FTE, F_FTE]
        r = row0 + 2
        col_tot = {l: 0.0 for l in LEVELS4}
        grand = 0.0
        for sid, ps in model["per_skill"].items():
            vals = []
            rt = 0.0
            for l in LEVELS4:
                v = ps["breakdown"][l]["fte_raw"] if kind == "raw" else ps["fte_by_level"][l]
                col_tot[l] += v
                rt += v
                vals.append(round(v, 2))
            grand += rt
            _drow(ws, r, [names.get(sid, sid)] + vals + [round(rt, 2)], fmts=fmts)
            r += 1
        if sdm_val > 1e-9:
            _drow(ws, r, ["SDM (engagement)", "", "", "", "", round(sdm_val, 2)], fmts=fmts)
            r += 1
        _drow(ws, r, ["GRAND TOTAL"] + [round(col_tot[l], 2) for l in LEVELS4] +
              [round(grand + sdm_val, 2)], total=True, fmts=fmts)
        return r + 2

    nxt = block(5, "Raw FTE (exact, pre-pooling)", "raw", sdm_raw)
    block(nxt, "Final FTE (delivered, pooled-aware)", "final", sdm_fin)


def _rates(wb, state):
    ws = wb.create_sheet("Rates")
    _title(ws, "Resolved hourly rates (INR)")
    rbc = state.get("rates_by_category", {}) or {}
    _hrow(ws, 5, ["Family", "L1 /hr", "L2 /hr", "L3 /hr", "Architect /hr"], [16, 12, 12, 12, 14])
    fmts = [None, F_INR, F_INR, F_INR, F_INR]
    r = 6
    for fam in ("InfraOps", "CloudOps"):
        band = rbc.get(fam, {}) or {}
        _drow(ws, r, [fam] + [round(float(band.get(l, 0) or 0)) for l in LEVELS4], fmts=fmts)
        r += 1
    _drow(ws, r, ["SDM (engagement)", round(float(state.get("sdm_rate_inr", 0) or 0)), "", "", ""],
          fmts=fmts)


def _optimization(wb, baseline, current, opt, names):
    ws = wb.create_sheet("Optimization")
    _title(ws, "AI Team Optimizer — savings & recommended moves")
    _hrow(ws, 5, ["Metric", "Baseline (no sharing)", "Applied", "Saving"], [26, 20, 18, 16])
    fmts = [None, F_FTE, F_FTE, F_FTE]
    _drow(ws, 6, ["Total FTE", round(baseline["total_fte"], 1), round(current["total_fte"], 1),
                  round(baseline["total_fte"] - current["total_fte"], 1)], fmts=fmts)
    cfmts = [None, F_INR, F_INR, F_INR]
    _drow(ws, 7, ["Resource cost / mo", round(baseline["total_resource_cost"]),
                  round(current["total_resource_cost"]),
                  round(baseline["total_resource_cost"] - current["total_resource_cost"])], fmts=cfmts)
    _drow(ws, 8, ["Selling price / mo", round(baseline["price_result"]["selling_price"]),
                  round(current["price_result"]["selling_price"]),
                  round(baseline["price_result"]["selling_price"] - current["price_result"]["selling_price"])],
          fmts=cfmts)

    _title_row = 10
    ws.cell(_title_row, 1, "Recommended moves (advisory)").font = openpyxl.styles.Font(
        name="Calibri", bold=True, color=NAVY, size=11)
    _hrow(ws, _title_row + 1, ["Skills", "Level", "Coverage", "FTE saved", "Cost saved",
                               "Cross-family", "Key-person risk"], [30, 10, 10, 11, 14, 12, 14])
    mfmts = [None, None, None, F_FTE, F_INR, None, None]
    r = _title_row + 2
    for s in opt.get("suggestions", []):
        _drow(ws, r, [" + ".join(s["skill_names"]), s["level"], s["coverage_model"],
                      round(s["fte_saved"], 1), round(s.get("cost_saved", 0)),
                      "Yes" if s.get("cross_family") else "", "Yes" if s["key_person_risk"] else ""],
              fmts=mfmts)
        r += 1
    if not opt.get("suggestions"):
        ws.cell(r, 1, "No cross-skill sharing opportunities found for the current setup.")


def _workload(wb, state, names):
    ws = wb.create_sheet("Workload Detail")
    _title(ws, "Inputs — Tickets, Patching & Additional Activities")
    skills = state.get("skills", [])
    row = 5
    # Tickets
    ws.cell(row, 1, "Tickets").font = openpyxl.styles.Font(name="Calibri", bold=True, color=NAVY, size=11)
    _hrow(ws, row + 1, ["Skill", "Category", "Count", "Min/Ticket", "L1 %", "L2 %", "L3 %"],
          [22, 18, 10, 11, 8, 8, 8])
    tf = [None, None, F_INR, F_NUM1, F_PCT, F_PCT, F_PCT]
    r = row + 2
    cats = [("alerts", "Monitoring Alerts"), ("service_requests", "Service Requests"),
            ("incidents", "Incidents"), ("changes", "Change Requests")]
    for sk in skills:
        wl = sk.get("workload", {}) or {}
        for ck, cl in cats:
            rw = (wl.get(ck, {}) or {}).get("All", {})
            if not rw or (rw.get("count", 0) or 0) <= 0:
                continue
            _drow(ws, r, [sk.get("name"), cl, int(rw.get("count", 0) or 0), float(rw.get("minutes", 0) or 0),
                          float(rw.get("L1_pct", 0) or 0), float(rw.get("L2_pct", 0) or 0),
                          float(rw.get("L3_pct", 0) or 0)], fmts=tf)
            r += 1
    # Patching
    r += 1
    ws.cell(r, 1, "Patching").font = openpyxl.styles.Font(name="Calibri", bold=True, color=NAVY, size=11)
    _hrow(ws, r + 1, ["Skill", "Servers", "Method", "Handled by", "Hrs/Month"], [22, 10, 12, 12, 12])
    pf = [None, F_INR, None, None, F_NUM1]
    r += 2
    for sk in skills:
        p = sk.get("patching") or {}
        if not p.get("included"):
            continue
        res = calc_patching_effort(True, p.get("num_servers", 0) or 0, p.get("method") or "Manual",
                                   p.get("manual_effort_per_server", 45) or 45,
                                   p.get("auto_effort_per_server", 30) or 30,
                                   error_rate_pct=p.get("error_rate_pct", 0) or 0)
        _drow(ws, r, [sk.get("name"), int(p.get("num_servers", 0) or 0), p.get("method"),
                      p.get("patching_role"), round(res["hours"], 1)], fmts=pf)
        r += 1
    # Activities
    r += 1
    ws.cell(r, 1, "Additional Activities").font = openpyxl.styles.Font(name="Calibri", bold=True, color=NAVY, size=11)
    _hrow(ws, r + 1, ["Skill", "Activity", "Auto", "Hrs/Month", "L1 %", "L2 %", "L3 %", "Arch %"],
          [22, 24, 7, 11, 8, 8, 8, 8])
    af = [None, None, None, F_NUM1, F_PCT, F_PCT, F_PCT, F_PCT]
    r += 2
    for sk in skills:
        for a in (sk.get("activities") or []):
            d = a.get("dist", {}) or {}
            _drow(ws, r, [sk.get("name"), a.get("name"), "Yes" if a.get("auto") else "",
                          float(a.get("hours", 0) or 0)] +
                  [float(d.get(l, 0) or 0) for l in LEVELS4], fmts=af)
            r += 1


def _inputs(wb, state):
    ws = wb.create_sheet("Inputs")
    _title(ws, "Engagement inputs")
    _hrow(ws, 5, ["Input", "Value", "Unit"], [34, 20, 12])
    rows = [
        ("Monthly working hours / FTE", state.get("monthly_working_hours"), "Hrs"),
        ("Productive utilisation", state.get("productive_utilisation"), "%"),
        ("Contingency", state.get("contingency_pct"), "%"),
        ("SDM overhead", state.get("sdm_overhead_pct"), "%"),
        ("Target margin", state.get("target_margin_pct"), "%"),
        ("Context-switch penalty", state.get("context_switch_pct"), "%"),
        ("Enforce 24×7 shift minimums", "Yes" if state.get("enforce_min_shift") else "No", ""),
        ("FTE basis", state.get("fte_basis"), ""),
        ("Delivery country", state.get("delivery_country"), ""),
        ("Delivery location", state.get("delivery_location") or "—", ""),
    ]
    fmt = {"": None, "Hrs": F_NUM1, "%": F_PCT}
    for i, (k, v, u) in enumerate(rows, 6):
        _drow(ws, i, [k, v, u], fmts=[None, fmt.get(u), None])


def generate_multi_excel_report(state=None) -> bytes:
    """Build the multi-skill workbook and return .xlsx bytes. `state` defaults to the
    live `build_multi_model_state()`; pass a dict to render without the UI (tests)."""
    if state is None:
        from modules.state.multi_state import build_multi_model_state
        state = build_multi_model_state()
    model = compute_multi_skill_model(state)
    baseline = compute_multi_skill_model({**state, "resource_sharing": []})
    try:
        from modules.optimize.team_optimizer import optimize_team
        opt = optimize_team({**state, "resource_sharing": []})
    except Exception:
        opt = {"suggestions": []}
    names = {s["id"]: (s.get("name") or s["id"]) for s in state.get("skills", [])}

    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    _exec(wb, model, baseline, state)
    _skills(wb, model, names)
    _buildup(wb, model, names)
    _team(wb, model, names)
    _rates(wb, state)
    _optimization(wb, baseline, model, opt, names)
    _workload(wb, state, names)
    _inputs(wb, state)

    colors = [NAVY, hx("teal_dark"), BLUE, ACCENT, hx("success"), hx("primary"), hx("text_muted"), NAVY]
    for i, ws in enumerate(wb.worksheets):
        ws.sheet_properties.tabColor = colors[i % len(colors)]
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.getvalue()
