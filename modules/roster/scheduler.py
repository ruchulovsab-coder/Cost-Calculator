"""Deterministic shift-plan scheduler.

Turns a computed multi-skill estimate into a proposal-ready roster. PURE — takes the
estimator's output dict + a small RosterConfig, returns a RosterPlan dict. No Streamlit,
no LLM, no side effects, no writes back to the estimate.

Reconciliation principle
------------------------
The estimator already inflates L1/L2 FTE by the coverage multiplier (24×7 = 4.20), so that
multiplier IS the relief factor. We therefore do NOT add a second relief factor. Deployable
whole heads = ceil(delivered FTE) per skill×level. The delta (seats − billed FTE) is shown
transparently and never changes the commercials.

Shift model (v1, "Balanced")
----------------------------
- L1/L2 are coverage roles: their seats are spread across the daily coverage window, split
  into ~shift_length-hour blocks (24h → 3 blocks, 16h → 2, 8h → 1).
- L3/Architect are NOT coverage-inflated by the engine, so they sit in business hours and go
  on-call/escalation outside it (shown, not spread across nights).
- Window placement for non-24×7 skills follows the per-skill coverage preference
  (Business / Non-Business / Custom).
- Every shift renders in BOTH customer-local and delivery-local time.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List

# Fixed UTC offsets for the preset zones. v1 ignores DST on purpose — shift windows are
# abstract time-of-day ranges, not dated instants, so a fixed offset is predictable and
# defensible for a proposal. DST/IANA calendars are a documented future extension.
TZ_OFFSETS: Dict[str, float] = {
    "PST": -8.0, "MST": -7.0, "CST": -6.0, "EST": -5.0,
    "UTC": 0.0, "GMT": 0.0, "CET": 1.0, "EET": 2.0,
    "IST": 5.5, "SGT": 8.0, "AEST": 10.0,
}
CUSTOMER_TZ_CHOICES = ["EST", "CST", "MST", "PST", "GMT", "CET", "EET", "IST", "SGT", "AEST"]
DELIVERY_TZ_CHOICES = ["IST", "SGT", "CET", "GMT", "EST", "CST", "PST"]
COVERAGE_PREF_MODES = ["Business Hours", "Non-Business Hours", "Custom Window"]

_COVERAGE_ROLES = ("L1", "L2")   # engine applies the coverage multiplier only to these
_ALL_LEVELS = ("L1", "L2", "L3", "Architect")


# ── time helpers ──────────────────────────────────────────────────────────────
def parse_hhmm(val: Any, default: float = 9.0) -> float:
    """'09:00' / '9' / '17:30' → hours as float. Tolerant; falls back to default."""
    if val is None:
        return default
    if isinstance(val, (int, float)):
        return float(val) % 24
    s = str(val).strip().upper().replace(" ", "")
    ampm = 0.0
    if s.endswith("AM"):
        s = s[:-2]
    elif s.endswith("PM"):
        s = s[:-2]
        ampm = 12.0
    try:
        if ":" in s:
            h, m = s.split(":", 1)
            val = int(h) + int(m) / 60.0
        else:
            val = float(s)
    except (ValueError, TypeError):
        return default
    if ampm and val < 12:
        val += 12
    return val % 24


def fmt_hhmm(h: float) -> str:
    h = h % 24
    hh = int(h)
    mm = int(round((h - hh) * 60))
    if mm == 60:
        hh, mm = (hh + 1) % 24, 0
    return f"{hh:02d}:{mm:02d}"


def convert(hour: float, from_off: float, to_off: float) -> float:
    return (hour + (to_off - from_off)) % 24


def _shift_label(start: float) -> str:
    s = start % 24
    if 5 <= s < 12:
        return "Morning"
    if 12 <= s < 17:
        return "Afternoon"
    if 17 <= s < 22:
        return "Evening"
    return "Night"


def _blocks(hpd: float, start: float, shift_len: float) -> List[tuple]:
    """Split an hpd-hour window starting at `start` into ~shift_len blocks (even split)."""
    n = max(1, math.ceil(round(hpd, 6) / shift_len - 1e-9))
    span = hpd / n
    return [(start + i * span, start + (i + 1) * span) for i in range(n)]


# ── main entry ────────────────────────────────────────────────────────────────
def build_roster(model: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
    """model = compute_multi_skill_model(...) output; config = RosterConfig dict.

    Returns a RosterPlan dict: {strategy, customer_tz, delivery_tz, shifts[], reconciliation[],
    advisories[], totals{}}. Deterministic: same model + config → identical plan.
    """
    from config.settings import COVERAGE_MODELS

    strategy = config.get("strategy", "Balanced")
    cust_tz = config.get("customer_tz", "EST")
    deliv_tz = config.get("delivery_tz", "IST")
    co = TZ_OFFSETS.get(cust_tz, 0.0)
    do = TZ_OFFSETS.get(deliv_tz, 0.0)
    bh_start = parse_hhmm(config.get("business_start", "09:00"), 9.0)
    bh_end = parse_hhmm(config.get("business_end", "17:00"), 17.0)
    shift_len = float(config.get("shift_length_h", 8) or 8)
    prefs = config.get("coverage_prefs", {}) or {}

    shifts: List[Dict[str, Any]] = []
    recon: List[Dict[str, Any]] = []
    advisories: List[str] = []

    def _win(start: float, end: float) -> Dict[str, str]:
        return {
            "customer": f"{fmt_hhmm(start)}–{fmt_hhmm(end)}",
            "delivery": f"{fmt_hhmm(convert(start, co, do))}–{fmt_hhmm(convert(end, co, do))}",
        }

    for sid, ps in (model.get("per_skill", {}) or {}).items():
        name = ps.get("name") or sid
        cov = ps.get("coverage_model") or "8×5"
        cfg = COVERAGE_MODELS.get(cov, COVERAGE_MODELS["8×5"])
        hpd = float(cfg.get("hours_per_day") or 8)
        dpw = float(cfg.get("days_per_week") or 5)
        is_247 = hpd >= 24 and dpw >= 7
        days = "Mon–Sun" if dpw >= 7 else ("Mon–Fri" if dpw >= 5 else f"{int(dpw)} days/wk")
        weekend = dpw >= 7

        # Window placement (L1/L2 coverage roles).
        pref = prefs.get(sid, {}) or {}
        mode = pref.get("mode", "Business Hours")
        if hpd >= 24:
            win_start, win_hpd = 6.0, 24.0        # full day, Morning/Evening/Night anchoring
        elif mode == "Non-Business Hours":
            win_start, win_hpd = bh_end, hpd
        elif mode == "Custom Window":
            win_start = parse_hhmm(pref.get("start"), bh_start)
            cwin = (parse_hhmm(pref.get("end"), win_start + hpd) - win_start) % 24
            win_hpd = cwin or hpd
        else:  # Business Hours
            win_start, win_hpd = bh_start, hpd
        blocks = _blocks(win_hpd, win_start, shift_len)
        n_blocks = len(blocks)

        fbl = ps.get("fte_by_level", {}) or {}
        for lvl in _ALL_LEVELS:
            fte = float(fbl.get(lvl, 0) or 0)
            if fte <= 1e-9:
                continue
            seats = max(1, math.ceil(fte - 1e-9))     # whole deployable heads
            recon.append({"skill": name, "level": lvl, "coverage": cov,
                          "fte": round(fte, 2), "seats": seats, "delta": round(seats - fte, 2)})

            if lvl in _COVERAGE_ROLES:
                # Spread seats across the daily shift blocks as evenly as possible.
                base, extra = divmod(seats, n_blocks)
                for i, (s, e) in enumerate(blocks):
                    blk_seats = base + (1 if i < extra else 0)
                    if blk_seats == 0:
                        continue
                    shifts.append({
                        "skill": name, "level": lvl, "shift": _shift_label(s),
                        "days": days, "seats": blk_seats, "on_call": False,
                        "note": "incl. weekend rotation" if weekend else "",
                        **_win(s, e),
                    })
                if seats < n_blocks:
                    advisories.append(
                        f"{name} · {lvl}: {seats} seat(s) cannot continuously staff {n_blocks} "
                        f"shift blocks for {cov} — expect rotation gaps; consider ≥{n_blocks}.")
                if is_247 and seats < 5:
                    advisories.append(
                        f"{name} · {lvl}: sustainable 24×7 rotation typically needs ≥5 seats "
                        f"(cover + leave/relief); estimate yields {seats}.")
            else:
                # L3 / Architect: business hours + on-call/escalation outside it.
                bs, be = bh_start, bh_start + min(win_hpd if win_hpd < 24 else 8, 8)
                shifts.append({
                    "skill": name, "level": lvl, "shift": "Business + on-call" if is_247 else "Business",
                    "days": "Mon–Fri", "seats": seats, "on_call": is_247,
                    "note": "escalation / on-call after hours" if is_247 else "",
                    **_win(bs, be),
                })

    total_fte = round(sum(r["fte"] for r in recon), 2)
    total_seats = sum(r["seats"] for r in recon)
    return {
        "strategy": strategy,
        "customer_tz": cust_tz, "delivery_tz": deliv_tz,
        "business_hours": f"{fmt_hhmm(bh_start)}–{fmt_hhmm(bh_end)} {cust_tz}",
        "shifts": shifts,
        "reconciliation": recon,
        "advisories": advisories,
        "totals": {"delivered_fte": total_fte, "deployable_seats": total_seats,
                   "delta": round(total_seats - total_fte, 2)},
        "fte_basis": model.get("fte_basis", "rounded"),
    }
