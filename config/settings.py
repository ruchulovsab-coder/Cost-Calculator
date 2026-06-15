"""
Central configuration.
Add new roles, grades, coverage models, currencies, or workload defaults here.
No code changes needed anywhere else.
"""

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

# ── Currencies (INR only) ─────────────────────────────────────────────────────
DEFAULT_CURRENCIES = ["INR"]
CURRENCY_SYMBOLS   = {"INR": "₹"}

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

DEFAULT_ADDITIONAL_ACTIVITIES = [
    {
        "name": "Scheduled Maintenance",
        "hours": 0.0,
        "custom": False,
        "dist": {"L1": 0.0, "L2": 70.0, "L3": 30.0, "Architect": 0.0, "SDM": 0.0, "SSDM": 0.0}
    },
    {
        "name": "Root Cause Analysis (RCA)",
        "hours": 0.0,
        "custom": False,
        "dist": {"L1": 0.0, "L2": 20.0, "L3": 50.0, "Architect": 30.0, "SDM": 0.0, "SSDM": 0.0}
    },
    {
        "name": "Problem Management",
        "hours": 0.0,
        "custom": False,
        "dist": {"L1": 0.0, "L2": 0.0, "L3": 70.0, "Architect": 20.0, "SDM": 10.0, "SSDM": 0.0}
    },
    {
        "name": "Documentation & Knowledge Base",
        "hours": 0.0,
        "custom": False,
        "dist": {"L1": 0.0, "L2": 20.0, "L3": 50.0, "Architect": 30.0, "SDM": 0.0, "SSDM": 0.0}
    },
    {
        "name": "Service Review Preparation",
        "hours": 0.0,
        "custom": False,
        "dist": {"L1": 0.0, "L2": 40.0, "L3": 50.0, "Architect": 0.0, "SDM": 10.0, "SSDM": 0.0}
    },
    {
        "name": "Other",
        "hours": 0.0,
        "custom": False,
        "dist": {"L1": 0.0, "L2": 100.0, "L3": 0.0, "Architect": 0.0, "SDM": 0.0, "SSDM": 0.0}
    },
]

