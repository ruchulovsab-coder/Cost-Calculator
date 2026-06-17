"""
Central configuration.
Add new roles, grades, coverage models, currencies, or workload defaults here.
No code changes needed anywhere else.
"""

# ── Branding ──────────────────────────────────────────────────────────────────
APP_NAME       = "Cloud & Infrastructure Practices — Ops Effort Estimation Tool"
APP_NAME_SHORT = "Cloud & Infra Ops Effort Estimator"
ORG_NAME       = "Nagarro"

# ── Design tokens (single source of truth) ────────────────────────────────────
# These hex values are mirrored in assets/styles.css :root (CSS can't read Python).
# Web CSS, Plotly charts, the PDF (reportlab) and Excel (openpyxl) all draw from
# THEME so the app, proposal and workbook share one brand palette.
# Note: openpyxl wants hex WITHOUT the leading '#'. Use hx(name) for that.
THEME = {
    "primary":       "#00C4B4",   # primary CTA, chart accent
    "primary_hover": "#00A396",
    "teal_dark":     "#1A5F6A",   # section headers, table totals
    "navy":          "#0D1B2A",   # headings, page-header / report header bg
    "badge":         "#2A8A8A",   # badges, table heads
    "bg":            "#F4FAFA",   # app background
    "card":          "#FFFFFF",   # surfaces
    "tint":          "#D6F0ED",   # zebra rows / subtle fills
    "accent_light":  "#A8DDD8",   # light captions on dark
    "text":          "#0D1B2A",
    "text_body":     "#0D4A4A",
    "text_muted":    "#6B7B7B",
    "success":       "#1A7A6A",
    "warning":       "#F39C12",
    "error":         "#E74C3C",
}


def hx(name: str) -> str:
    """THEME color as a bare hex (no '#') — convenient for openpyxl fills/fonts."""
    return THEME[name].lstrip("#")

# ── Roles ─────────────────────────────────────────────────────────────────────
ALL_ROLES = ["L1", "L2", "L3", "Architect", "SDM", "SSDM"]
COVERAGE_APPLICABLE_ROLES = ["L1", "L2"]

# ── Grade eligibility ─────────────────────────────────────────────────────────
GRADE_ELIGIBILITY = {
    "L1":        ["2.1-INFRAOPS", "2.2-INFRAOPS"],
    "L2":        ["2.3-INFRAOPS", "3.1-INFRAOPS"],
    "L3":        ["3.2-INFRAOPS", "3.3-INFRAOPS"],
    "Architect": ["4.1-INFRAOPS"],
    "SDM":       ["4.1-DELIVERY-ITIL"],
    "SSDM":      ["4.2-DELIVERY-ITIL"],
}

# ── Coverage models ───────────────────────────────────────────────────────────
COVERAGE_MODELS = {
    "8×5":   {"hours_per_day": 8,  "days_per_week": 5, "weekly_hours": 40,  "multiplier": 1.00},
    "12×5":  {"hours_per_day": 12, "days_per_week": 5, "weekly_hours": 60,  "multiplier": 1.50},
    "16×5":  {"hours_per_day": 16, "days_per_week": 5, "weekly_hours": 80,  "multiplier": 2.00},
    "24×5":  {"hours_per_day": 24, "days_per_week": 5, "weekly_hours": 120, "multiplier": 3.00},
    "24×7":  {"hours_per_day": 24, "days_per_week": 7, "weekly_hours": 168, "multiplier": 4.20},
    "Custom":{"hours_per_day": None,"days_per_week": None,"weekly_hours": None,"multiplier": None},
}

# ── Currencies ────────────────────────────────────────────────────────────────
# INR is the base/default. Other currencies are supported for the *reporting*
# (output) view and for rate cards whose rates are quoted in foreign currency.
# Exchange rates are entered by the user as: 1 <CUR> = X INR.
DEFAULT_CURRENCIES   = ["INR"]
REPORTING_CURRENCIES = ["INR", "USD", "EUR", "GBP", "AUD", "AED", "SGD", "CAD", "JPY"]
CURRENCY_SYMBOLS     = {
    "INR": "₹", "USD": "$", "EUR": "€", "GBP": "£", "AUD": "A$",
    "AED": "AED ", "SGD": "S$", "CAD": "C$", "JPY": "¥",
}

# ── Ticket category labels ────────────────────────────────────────────────────
TICKET_CATEGORIES = ["Monitoring Alerts", "Service Requests", "Incidents", "Change Requests"]

# Sub-labels per category (used for display ordering only)
ALERT_SEVERITIES      = ["Critical", "High", "Medium", "Low"]
SR_COMPLEXITIES       = ["Low", "Medium", "High"]
INCIDENT_SEVERITIES   = ["Low", "Medium", "High"]
INCIDENT_COMPLEXITIES = INCIDENT_SEVERITIES   # alias for backward compatibility
CHANGE_TYPES          = ["Standard", "Normal", "Complex"]

# Canonical sub-label order per category key
CATEGORY_SUBLABELS = {
    "alerts":           ALERT_SEVERITIES,
    "service_requests": SR_COMPLEXITIES,
    "incidents":        INCIDENT_SEVERITIES,
    "changes":          CHANGE_TYPES,
}

# ── Industry-standard defaults ────────────────────────────────────────────────
# All three tables (distribution %, effort minutes, L1/L2/L3 split %) are pre-filled
# from these values when the user enters a total volume. All values remain editable.

# --- Volume distribution across sub-labels (must sum to 100) ---
DEFAULT_VOLUME_DIST_PCT = {
    "alerts":           {"Critical": 5,  "High": 15, "Medium": 35, "Low": 45},
    "service_requests": {"Low": 50, "Medium": 35, "High": 15},
    "incidents":        {"Low": 50, "Medium": 35, "High": 15},
    "changes":          {"Standard": 60, "Normal": 30, "Complex": 10},
}

# --- Avg effort in minutes per ticket per sub-label ---
DEFAULT_EFFORT_MINUTES = {
    "alerts": {
        "Critical": 45, "High": 30, "Medium": 20, "Low": 10,
    },
    "service_requests": {
        "Low": 20, "Medium": 30, "High": 60,
    },
    "incidents": {
        "Low": 30, "Medium": 60, "High": 90,
    },
    "changes": {
        "Standard": 60, "Normal": 120, "Complex": 240,
    },
}

# --- L1/L2/L3 resolution split % per sub-label (must sum to 100 per row) ---
DEFAULT_RESOLUTION_PCT = {
    "alerts": {
        "Critical": {"L1":  0, "L2": 30, "L3": 70},
        "High":     {"L1": 10, "L2": 60, "L3": 30},
        "Medium":   {"L1": 60, "L2": 35, "L3":  5},
        "Low":      {"L1": 80, "L2": 18, "L3":  2},
    },
    "service_requests": {
        "Low":    {"L1": 80, "L2": 18, "L3":  2},
        "Medium": {"L1": 50, "L2": 40, "L3": 10},
        "High":   {"L1": 10, "L2": 50, "L3": 40},
    },
    "incidents": {
        "Low":    {"L1": 70, "L2": 25, "L3":  5},
        "Medium": {"L1": 30, "L2": 50, "L3": 20},
        "High":   {"L1":  0, "L2": 40, "L3": 60},
    },
    "changes": {
        "Standard": {"L1": 50, "L2": 40, "L3": 10},
        "Normal":   {"L1": 10, "L2": 60, "L3": 30},
        "Complex":  {"L1":  0, "L2": 30, "L3": 70},
    },
}

# Overhead roles
OVERHEAD_ROLES   = ["Architect", "SDM", "SSDM"]
RESOLUTION_ROLES = ["L1", "L2", "L3"]

# Default per-row, per-role effort buffer (%) applied to L1/L2/L3 hours in Step 2.
DEFAULT_ROLE_BUFFER_PCT = 20.0

# ── Server patching effort defaults ───────────────────────────────────────────
# Effort is modelled as (minutes per server × server count). All values are
# user-editable; these are the recommended starting points.
DEFAULT_NUM_SERVERS       = 20
PATCHING_EFFORT_DEFAULTS  = {"Manual": 45.0, "Tool-Based": 30.0}  # minutes/server

# ── Auto-derived additional-activity effort formulas ──────────────────────────
# For each activity the monthly effort (hours) = (Σ driver_quantity × per_unit_min) ÷ 60.
# Drivers: "servers" (from patching server count) and the four ticket volumes
# (alerts, incidents, service_requests, changes). These produce recommended
# defaults only — users can switch "Auto" off and enter their own value.
ACTIVITY_FORMULAS = {
    "Scheduled Maintenance": {
        "drivers": {"servers": 30.0},
        "text": "30 min × servers",
    },
    "Root Cause Analysis (RCA)": {
        "drivers": {"incidents": 360.0},
        "text": "360 min × incidents",
    },
    "Problem Management": {
        "drivers": {"incidents": 600.0},
        "text": "600 min × incidents",
    },
    "Documentation & Knowledge Base": {
        "drivers": {"servers": 30.0, "incidents": 120.0, "service_requests": 15.0, "changes": 120.0},
        "text": "30 min × servers + 120 min × incidents + 15 min × service requests + 120 min × changes",
    },
}

DEFAULT_ADDITIONAL_ACTIVITIES = [
    {
        "name": "Scheduled Maintenance",
        "hours": 0.0,
        "custom": False,
        "auto": True,
        "dist": {"L1": 0.0, "L2": 70.0, "L3": 30.0, "Architect": 0.0, "SDM": 0.0, "SSDM": 0.0}
    },
    {
        "name": "Root Cause Analysis (RCA)",
        "hours": 0.0,
        "custom": False,
        "auto": True,
        "dist": {"L1": 0.0, "L2": 20.0, "L3": 50.0, "Architect": 30.0, "SDM": 0.0, "SSDM": 0.0}
    },
    {
        "name": "Problem Management",
        "hours": 0.0,
        "custom": False,
        "auto": True,
        "dist": {"L1": 0.0, "L2": 0.0, "L3": 70.0, "Architect": 20.0, "SDM": 10.0, "SSDM": 0.0}
    },
    {
        "name": "Documentation & Knowledge Base",
        "hours": 0.0,
        "custom": False,
        "auto": True,
        "dist": {"L1": 0.0, "L2": 20.0, "L3": 50.0, "Architect": 30.0, "SDM": 0.0, "SSDM": 0.0}
    },
    {
        "name": "Service Review Preparation",
        "hours": 0.0,
        "custom": False,
        "auto": False,
        "dist": {"L1": 0.0, "L2": 40.0, "L3": 50.0, "Architect": 0.0, "SDM": 10.0, "SSDM": 0.0}
    },
    {
        "name": "Other",
        "hours": 0.0,
        "custom": False,
        "auto": False,
        "dist": {"L1": 0.0, "L2": 100.0, "L3": 0.0, "Architect": 0.0, "SDM": 0.0, "SSDM": 0.0}
    },
]

