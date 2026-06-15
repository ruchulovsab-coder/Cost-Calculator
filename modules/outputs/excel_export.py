"""Excel export — multi-sheet workbook. Reads from the unified compute model."""
import io
from datetime import date
import openpyxl
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
from openpyxl.utils import get_column_letter
import streamlit as st
from config.settings import ALL_ROLES
from modules.state.session_manager import run_model

NAVY = "1F3864"; BLUE = "2E75B6"; LB = "D5E8F0"; ACCENT = "ED7D31"
LGRAY = "F2F2F2"; WHITE = "FFFFFF"

def _fill(c): return PatternFill("solid", fgColor=c)
def _font(c="000000", bold=False, sz=10): return Font(name="Calibri", color=c, bold=bold, size=sz)
def _border():
    s = Side(style="thin", color="CCCCCC")
    return Border(left=s, right=s, top=s, bottom=s)
def _cw(ws, col, w): ws.column_dimensions[get_column_letter(col)].width = w

def _hrow(ws, row, headers, widths=None):
    for i, h in enumerate(headers, 1):
        c = ws.cell(row=row, column=i, value=h)
        c.fill = _fill(NAVY); c.font = _font(WHITE, True)
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = _border()
        if widths and i <= len(widths): _cw(ws, i, widths[i-1])

def _drow(ws, row, vals, total=False):
    bg = _fill(LB) if total else None
    for i, v in enumerate(vals, 1):
        c = ws.cell(row=row, column=i, value=v)
        c.font = _font(bold=total)
        c.border = _border()
        c.alignment = Alignment(horizontal="right" if isinstance(v, (int, float)) else "left")
        if bg: c.fill = bg

def _title(ws, t, sub=""):
    ws.cell(1,1,t).font = Font("Calibri", bold=True, size=13, color=NAVY)
    if sub: ws.cell(2,1,sub).font = Font("Calibri", italic=True, size=10, color="767676")
    ws.cell(3,1,f"Generated: {date.today()}").font = Font("Calibri", size=9, color="767676")

def _build_exec(wb, model):
    ws = wb.create_sheet("Executive Summary")
    _title(ws, "IT Managed Services Calculator — Executive Summary")
    cost = model["cost_result"]; price = model["price_result"]
    te = model["total_effort"]; base = model["base_effort"]
    _hrow(ws, 5, ["Metric", "Value", "Unit"], [35, 22, 15])
    rows = [
        ("Base Operational Effort",   round(base, 1),  "Hrs/Month"),
        ("Contingency Hours",         round(te-base,1),"Hrs/Month"),
        ("Total Operational Effort",  round(te, 1),    "Hrs/Month"),
        ("Total FTE Required",        round(model["total_fte"],1),"FTE"),
        ("Coverage Model",            st.session_state.get("coverage_model","—"),""),
        ("Total Resource Cost (INR)", cost.get("resource_cost",0), "INR"),
        ("Additional Expenses (INR)", cost.get("additional_expenses",0),"INR"),
        ("Total Delivery Cost (INR)", cost.get("total_delivery_cost",0),"INR"),
        ("Gross Margin %",            price.get("margin_pct",0), "%"),
        ("Monthly Selling Price (INR)",price.get("selling_price",0),"INR"),
        ("One-Time Transition Cost (INR)", model["transition_cost"], "INR"),
        ("Reporting Currency",        model["reporting_currency"], ""),
        (f"Monthly Selling Price ({model['reporting_currency']})",
         round(model["selling_price_converted"], 2), model["reporting_currency"]),
    ]
    for i,(m,v,u) in enumerate(rows,6): _drow(ws,i,[m,v,u], total=(str(m).isupper()))

def _build_effort(wb, model):
    ws = wb.create_sheet("Effort Breakdown")
    _title(ws, "Effort Breakdown")
    rh = model["role_hours"]; te = model["total_effort"]
    _hrow(ws,5,["Role","Effort Hours","% of Total Effort"],[18,16,20])
    for i,role in enumerate(ALL_ROLES,6):
        h = rh.get(role,0); pct = h/te*100 if te>0 else 0
        _drow(ws,i,[role,round(h,1),round(pct,1)])
    _drow(ws,6+len(ALL_ROLES),["TOTAL",round(te,1),100.0],total=True)

def _build_resolution(wb, model):
    ws = wb.create_sheet("Resolution Detail")
    _title(ws, "Resolution Detail — Tickets, Minutes & Role Hours")
    _hrow(ws,5,[
        "Category","Severity/Type","Count","Min/Ticket",
        "Total Hrs","L1 %","L1 Hrs","L2 %","L2 Hrs","L3 %","L3 Hrs"
    ],[18,14,10,12,12,8,10,8,10,8,10])
    from config.settings import CATEGORY_SUBLABELS
    CATS = [
        ("alerts",           "Monitoring Alerts"),
        ("service_requests", "Service Requests"),
        ("incidents",        "Incidents"),
        ("changes",          "Change Requests"),
    ]
    row_num = 6
    for cat_key, cat_label in CATS:
        cat_data = st.session_state.get(cat_key, {})
        for label in CATEGORY_SUBLABELS[cat_key]:
            row = cat_data.get(label, {})
            cnt  = row.get("count", 0); mins = row.get("minutes", 0)
            l1p  = row.get("L1_pct", 0); l2p = row.get("L2_pct", 0); l3p = row.get("L3_pct", 0)
            total_h = (cnt * mins) / 60.0
            _drow(ws, row_num, [
                cat_label, label, cnt, round(mins,0), round(total_h,2),
                l1p, round(total_h*l1p/100,2), l2p, round(total_h*l2p/100,2),
                l3p, round(total_h*l3p/100,2),
            ])
            row_num += 1

def _build_fte(wb, model):
    ws = wb.create_sheet("FTE Summary")
    _title(ws, "FTE Summary")
    fte = model["fte_result"]
    _hrow(ws,5,["Role","Effort Hours","Raw FTE","Cov. Applied","Final FTE"],[14,14,12,16,12])
    for i,role in enumerate(ALL_ROLES,6):
        r = fte.get(role,{})
        _drow(ws,i,[role,round(r.get("hours",0),1),round(r.get("raw_fte",0),3),"Yes" if r.get("coverage_applied") else "No",round(r.get("final_fte",0),1)])
    _drow(ws,6+len(ALL_ROLES),["TOTAL","","","",round(model["total_fte"],1)],total=True)

def _build_costs(wb, model):
    ws = wb.create_sheet("Resource Costs")
    _title(ws,"Resource Cost Summary")
    rc = model["resource_costs"]
    _hrow(ws,5,["Role","Genus","Required FTE","Billed Hours","Rate (INR/hr)","Cost (INR)"],[12,22,14,14,16,18])
    for i,role in enumerate(ALL_ROLES,6):
        r = rc.get(role,{})
        _drow(ws,i,[role,r.get("genus","—"),round(r.get("fte",0),1),round(r.get("billed_hours",0),0),round(r.get("rate_inr",0),0),round(r.get("cost_inr",0),0)])
    _drow(ws,6+len(ALL_ROLES),["TOTAL","","","","",round(model["total_resource_cost"],0)],total=True)

def _build_financial(wb, model):
    ws = wb.create_sheet("Financial Model")
    _title(ws,"Financial Model")
    cost = model["cost_result"]; price = model["price_result"]
    _hrow(ws,5,["Component","Amount (INR)"],[38,20])
    rows = [
        ("Total Resource Cost",       cost.get("resource_cost",0),       False),
        ("Total Additional Expenses", cost.get("additional_expenses",0), False),
        ("SLA Penalty Provision",     cost.get("sla_provision",0),       False),
        ("TOTAL DELIVERY COST",       cost.get("total_delivery_cost",0), True),
        ("Gross Margin %",            price.get("margin_pct",0),         False),
        ("Gross Profit",              price.get("gross_profit",0),       False),
        ("MONTHLY SELLING PRICE",     price.get("selling_price",0),      True),
        ("ONE-TIME TRANSITION COST",  model["transition_cost"],          True),
    ]
    for i,(lbl,val,tot) in enumerate(rows,6): _drow(ws,i,[lbl,round(val,0)],total=tot)

def _build_audit(wb, model):
    ws = wb.create_sheet("Inputs Audit")
    _title(ws,"All User Inputs — Audit Trail")
    _hrow(ws,5,["Step","Input Field","Value","Unit"],[8,40,22,15])
    audit=[
        (3,"Patching Included",st.session_state.get("patching_included",""),""),
        (3,"Number of Servers",st.session_state.get("num_servers",0),""),
        (3,"Patching Method",st.session_state.get("patching_method",""),""),
        (5,"Contingency %",st.session_state.get("contingency_pct",0),"%"),
        (6,"Coverage Model",st.session_state.get("coverage_model",""),""),
        (6,"Monthly Working Hours",st.session_state.get("monthly_working_hours",0),"Hrs"),
        (6,"Productive Utilisation",st.session_state.get("productive_utilisation",0),"%"),
        (7,"Delivery Country",st.session_state.get("delivery_country","India"),""),
        (7,"Delivery Location",st.session_state.get("delivery_location","—") or "—",""),
        (8,"Reporting Currency",model["reporting_currency"],""),
        (8,"Target Gross Margin",st.session_state.get("target_margin_pct",0),"%"),
        (8,"Transition Included",st.session_state.get("transition_included",""),""),
        (8,"Transition Total Cost",st.session_state.get("transition_total_cost",0),"INR"),
        (8,"SLA Provision Included",st.session_state.get("sla_provision_included",""),""),
        (8,"SLA Provision %",st.session_state.get("sla_provision_pct",0),"%"),
    ]
    for role, pct in (st.session_state.get("overhead_pcts",{}) or {}).items():
        audit.append((2,f"Overhead % — {role}",pct,"%"))
    for i,row in enumerate(audit,6): _drow(ws,i,list(row))

def generate_excel_report() -> bytes:
    model = st.session_state.get("_model") or run_model()
    wb = openpyxl.Workbook(); wb.remove(wb.active)
    _build_exec(wb, model); _build_effort(wb, model); _build_resolution(wb, model)
    _build_fte(wb, model); _build_costs(wb, model); _build_financial(wb, model); _build_audit(wb, model)
    colors = [NAVY, BLUE, "2E75B6", "375623", "ED7D31", ACCENT, "767676"]
    for i,ws in enumerate(wb.worksheets):
        ws.sheet_properties.tabColor = colors[i % len(colors)]
    buf = io.BytesIO(); wb.save(buf); buf.seek(0)
    return buf.getvalue()
