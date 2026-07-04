"""Excel export for the Transition Strategy — themed, proposal-ready appendix.

Sheets: Timeline (phase Gantt-style bands + milestones), Phase Activities, Skill-wise Plan, RACI,
Deliverables. Presentation values (not a recalc model), app theme, no logo (parity with the other
formula-driven exports)."""
from __future__ import annotations

import io
from datetime import date
from typing import Any, Dict, List

import openpyxl
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from config.settings import hx

NAVY = hx("navy"); TEAL = hx("teal_dark"); TINT = hx("tint"); MUTED = hx("text_muted")
ACCENT = hx("accent_light"); AMBER = "FBEED9"
_thin = Side(style="thin", color="CCCCCC")
BORDER = Border(left=_thin, right=_thin, top=_thin, bottom=_thin)
RACI_FILL = {"R": "D6F0ED", "A": ACCENT, "C": "EAF3F4", "I": "F4F6F7"}


def _fill(c):
    return PatternFill("solid", fgColor=c)


def _title(ws, r, text, size=13):
    ws.cell(r, 1, text).font = Font(bold=True, color=NAVY, size=size)


def _hdr(ws, r, headers, c0=1):
    for j, h in enumerate(headers, start=c0):
        c = ws.cell(r, j, h); c.fill = _fill(NAVY); c.border = BORDER
        c.font = Font(color="FFFFFF", bold=True, size=10)
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)


def _cell(ws, r, j, val, bold=False, wrap=False, fill=None, center=False):
    c = ws.cell(r, j, val); c.border = BORDER
    c.font = Font(size=10, bold=bold)
    c.alignment = Alignment(horizontal="center" if center else "left",
                            vertical="top", wrap_text=wrap)
    if fill:
        c.fill = _fill(fill)


def _bullets(items: List[str]) -> str:
    return "\n".join("• " + str(i) for i in (items or [])) or "—"


def build_transition_workbook(plan: Dict[str, Any], project: str = "") -> bytes:
    wb = openpyxl.Workbook()

    # ── Timeline ──
    ws = wb.active; ws.title = "Timeline"; ws.sheet_view.showGridLines = False
    r = 1
    _title(ws, r, f"Transition Strategy{(' — ' + project) if project else ''}"); r += 2
    ws.cell(r, 1, f"Start {plan['start'].isoformat()} · span {plan['span_weeks']:g} weeks · "
                  f"customer TZ {plan.get('customer_tz','')}").font = Font(size=10, color=MUTED); r += 1
    ws.cell(r, 1, "Foundation: " + plan.get("foundation", "")).font = Font(size=10, italic=True,
                                                                           color=MUTED); r += 2
    _hdr(ws, r, ["Phase", "ITIL Band", "Start", "End", "Weeks", "Milestone / Gate"]); r += 1
    ms_by_phase = {m["phase"]: m for m in plan.get("milestones", [])}
    for row in plan.get("timeline", []):
        ms = ms_by_phase.get(row["name"])
        _cell(ws, r, 1, row["name"], bold=True)
        _cell(ws, r, 2, row["band"])
        _cell(ws, r, 3, row["start"].isoformat(), center=True)
        _cell(ws, r, 4, row["end"].isoformat(), center=True)
        _cell(ws, r, 5, f"{row['duration_weeks']:g}", center=True)
        _cell(ws, r, 6, (f"{ms['id']}: {ms['gate']}" if ms else ""), wrap=True,
              fill=AMBER if ms else None)
        r += 1
    for j, w in enumerate([34, 18, 12, 12, 7, 46], start=1):
        ws.column_dimensions[get_column_letter(j)].width = w

    # ── Phase Activities ──
    ws = wb.create_sheet("Phase Activities"); ws.sheet_view.showGridLines = False
    r = 1; _title(ws, r, "Phase Activities"); r += 1
    _hdr(ws, r, ["Phase", "Objectives", "Deliverables", "Entry", "Exit", "Risks",
                 "Dependencies", "Customer", "Nagarro"]); r += 1
    for p in plan.get("phase_activities", []):
        _cell(ws, r, 1, p["name"], bold=True, wrap=True)
        for j, k in enumerate(["objectives", "deliverables", "entry", "exit", "risks",
                               "dependencies", "customer_resp", "nagarro_resp"], start=2):
            _cell(ws, r, j, _bullets(p.get(k, [])), wrap=True)
        r += 1
    ws.column_dimensions["A"].width = 22
    for j in range(2, 10):
        ws.column_dimensions[get_column_letter(j)].width = 30

    # ── Skill-wise Plan ──
    ws = wb.create_sheet("Skill-wise Plan"); ws.sheet_view.showGridLines = False
    r = 1; _title(ws, r, "Skill-wise Transition Plan"); r += 1
    _hdr(ws, r, ["Skill", "Levels", "Knowledge Transition", "Shadow", "Reverse Shadow",
                 "Stabilization", "Exit Criteria", "Sign-off Criteria"]); r += 1
    for sp in plan.get("skill_plans", []):
        _cell(ws, r, 1, sp["skill"], bold=True, wrap=True)
        _cell(ws, r, 2, ", ".join(sp["levels"]) or "—", wrap=True)
        for j, k in enumerate(["knowledge_transition", "shadow", "reverse_shadow", "stabilization",
                               "exit_criteria", "signoff_criteria"], start=3):
            _cell(ws, r, j, _bullets(sp.get(k, [])), wrap=True)
        r += 1
    ws.column_dimensions["A"].width = 22; ws.column_dimensions["B"].width = 14
    for j in range(3, 9):
        ws.column_dimensions[get_column_letter(j)].width = 32

    # ── RACI ──
    ws = wb.create_sheet("RACI"); ws.sheet_view.showGridLines = False
    r = 1; _title(ws, r, "RACI Matrix (R = Responsible · A = Accountable · C = Consulted · I = Informed)")
    r += 1
    roles = plan.get("roles_customer", []) + plan.get("roles_nagarro", [])
    _hdr(ws, r, ["Activity"] + roles); r += 1
    for row in plan.get("raci", []):
        _cell(ws, r, 1, row["activity"], wrap=True)
        for j, role in enumerate(roles, start=2):
            v = row["raci"].get(role, "")
            _cell(ws, r, j, v, center=True, bold=(v == "A"), fill=RACI_FILL.get(v))
        r += 1
    ws.column_dimensions["A"].width = 40
    for j in range(2, len(roles) + 2):
        ws.column_dimensions[get_column_letter(j)].width = 10

    # ── Deliverables ──
    ws = wb.create_sheet("Deliverables"); ws.sheet_view.showGridLines = False
    r = 1; _title(ws, r, "Deliverables, Gates & Best-practice Artifacts"); r += 1
    _hdr(ws, r, ["Phase", "Key Deliverables", "Exit / Quality Gate", "Milestone"]); r += 1
    for d in plan.get("deliverables", []):
        _cell(ws, r, 1, d["phase"], bold=True, wrap=True)
        _cell(ws, r, 2, _bullets(d.get("deliverables", [])), wrap=True)
        _cell(ws, r, 3, _bullets(d.get("exit", [])), wrap=True)
        _cell(ws, r, 4, d.get("milestone") or "", center=True, fill=AMBER if d.get("milestone") else None)
        r += 1
    r += 1
    _title(ws, r, "Best-practice artifacts", 11); r += 1
    for a in plan.get("best_practice_artifacts", []):
        ws.cell(r, 1, "• " + a).font = Font(size=10); r += 1
    for j, w in enumerate([22, 44, 40, 12], start=1):
        ws.column_dimensions[get_column_letter(j)].width = w

    # ── Advisories (if any) appended to Timeline sheet ──
    if plan.get("advisories"):
        ws = wb["Timeline"]; rr = ws.max_row + 2
        _title(ws, rr, "Advisories (informational — do not affect commercials)", 11); rr += 1
        for a in plan["advisories"]:
            c = ws.cell(rr, 1, "⚠  " + a); c.fill = _fill(AMBER)
            c.font = Font(size=10); c.alignment = Alignment(wrap_text=True, vertical="center")
            ws.merge_cells(start_row=rr, start_column=1, end_row=rr, end_column=6); rr += 1

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
