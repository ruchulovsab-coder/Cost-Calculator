"""Client-facing PDF proposal export (reportlab). Reads the unified compute model."""
import io
import os
from datetime import date

import streamlit as st
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image,
)

from config.settings import ALL_ROLES, CURRENCY_SYMBOLS, APP_NAME, ORG_NAME
from modules.state.session_manager import run_model

_LOGO_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                          "assets", "nagarro_logo.png")

NAVY = colors.HexColor("#1F3864")
TEAL = colors.HexColor("#1A5F6A")
LB = colors.HexColor("#D5E8F0")
GREY = colors.HexColor("#767676")


def _sym(currency: str) -> str:
    return CURRENCY_SYMBOLS.get(currency, currency + " ")


def _money(value: float, currency: str = "INR") -> str:
    return f"{_sym(currency)}{value:,.0f}"


def _table(data, col_widths, header=True, total_row_idx=None):
    t = Table(data, colWidths=col_widths, hAlign="LEFT")
    style = [
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CCCCCC")),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    if header:
        style += [
            ("BACKGROUND", (0, 0), (-1, 0), NAVY),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ]
    if total_row_idx is not None:
        style += [
            ("BACKGROUND", (0, total_row_idx), (-1, total_row_idx), LB),
            ("FONTNAME", (0, total_row_idx), (-1, total_row_idx), "Helvetica-Bold"),
        ]
    t.setStyle(TableStyle(style))
    return t


def generate_pdf_report() -> bytes:
    model = st.session_state.get("_model") or run_model()
    cur = model["reporting_currency"]
    cost = model["cost_result"]
    price = model["price_result"]

    country = st.session_state.get("delivery_country", "India")
    location = st.session_state.get("delivery_location")
    scope = country + (f" / {location}" if location else "")

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=18 * mm, bottomMargin=16 * mm,
                            leftMargin=16 * mm, rightMargin=16 * mm,
                            title=f"{APP_NAME} — Proposal")
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=styles["Title"], textColor=NAVY, fontSize=20, spaceAfter=2)
    sub = ParagraphStyle("sub", parent=styles["Normal"], textColor=GREY, fontSize=10, spaceAfter=2)
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], textColor=TEAL, fontSize=13, spaceBefore=12, spaceAfter=6)
    note = ParagraphStyle("note", parent=styles["Normal"], textColor=GREY, fontSize=8, spaceBefore=10)

    e = []
    if os.path.exists(_LOGO_PATH):
        try:
            img = Image(_LOGO_PATH); img._restrictSize(45 * mm, 16 * mm); img.hAlign = "LEFT"
            e.append(img); e.append(Spacer(1, 4))
        except Exception:
            pass
    e.append(Paragraph(APP_NAME, h1))
    e.append(Paragraph(f"{ORG_NAME} &middot; Cloud &amp; Infrastructure Practices", sub))
    e.append(Paragraph(f"Delivery location: <b>{scope}</b> &nbsp;|&nbsp; Reporting currency: <b>{cur}</b> "
                       f"&nbsp;|&nbsp; Generated: {date.today()}", sub))
    e.append(Spacer(1, 6))

    # Executive summary
    e.append(Paragraph("Executive Summary", h2))
    conv_sp = model["selling_price_converted"]
    conv_dc = model["delivery_cost_converted"]
    exec_rows = [
        ["Metric", "Value"],
        ["Total Monthly Effort", f"{model['total_effort']:,.1f} hrs"],
        ["Total FTE Required", f"{model['total_fte']:.1f}"],
        ["Coverage Model", st.session_state.get("coverage_model", "—") or "—"],
        ["Gross Margin", f"{price['margin_pct']:.1f}%"],
        ["Total Delivery Cost", _money(conv_dc, cur)],
        ["Monthly Selling Price", _money(conv_sp, cur)],
    ]
    if model["transition_cost"] > 0:
        exec_rows.append(["One-Time Transition Cost", _money(model["transition_cost_converted"], cur)])
    e.append(_table(exec_rows, [95 * mm, 75 * mm], total_row_idx=len(exec_rows) - 1))

    # Resource plan
    e.append(Paragraph("Resource Plan", h2))
    rc_rows = [["Role", "Genus", "FTE", "Rate (INR/hr)", "Monthly Cost (INR)"]]
    for role in ALL_ROLES:
        r = model["resource_costs"][role]
        if r["fte"] <= 0:
            continue
        rc_rows.append([role, r["genus"] or "—", f"{r['fte']:.1f}",
                        f"{r['rate_inr']:,.0f}", f"{r['cost_inr']:,.0f}"])
    rc_rows.append(["Total", "", f"{model['total_fte']:.1f}", "", f"{model['total_resource_cost']:,.0f}"])
    e.append(_table(rc_rows, [28 * mm, 52 * mm, 20 * mm, 35 * mm, 40 * mm], total_row_idx=len(rc_rows) - 1))

    # Financial summary
    e.append(Paragraph("Financial Summary", h2))
    fin_rows = [["Component", "INR", cur]]
    items = [
        ("Total Resource Cost", cost["resource_cost"]),
        ("Additional Expenses", cost["additional_expenses"]),
        ("SLA Penalty Provision", cost["sla_provision"]),
        ("Total Delivery Cost", cost["total_delivery_cost"]),
        ("Gross Profit", price["gross_profit"]),
        ("Monthly Selling Price", price["selling_price"]),
    ]
    fx = dict(st.session_state.get("exchange_rates", {}) or {})
    fx.setdefault("INR", 1.0)
    from modules.calculations.engine import convert_to_currency
    for label, inr in items:
        conv = convert_to_currency(inr, cur, fx)
        fin_rows.append([label, f"{inr:,.0f}", _money(conv, cur)])
    e.append(_table(fin_rows, [80 * mm, 45 * mm, 45 * mm], total_row_idx=len(fin_rows) - 1))

    e.append(Paragraph(
        f"This proposal is an estimate generated by the {APP_NAME} based on the "
        "volumes and assumptions provided. Final pricing is subject to contract. Transition costs, "
        "where shown, are one-time and billed separately from the monthly delivery charge.", note))

    doc.build(e)
    buf.seek(0)
    return buf.getvalue()
