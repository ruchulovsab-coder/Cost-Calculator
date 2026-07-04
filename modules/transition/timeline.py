"""Deterministic transition-timeline solver. PURE — no Streamlit, no LLM, no side effects.

Given a start date, ordered phases (durations in weeks, include flags, optional overlap lead) and
a sequencing mode, it resolves consistent phase start/end dates, places milestones (M1–M4 + Go-Live)
and validates against the user's configured overall duration and Go-Live date — surfacing conflicts
as advisories (never silently 'correcting' them)."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from .catalog import MILESTONE_GATES


def _as_date(v: Any, default: Optional[date] = None) -> Optional[date]:
    if isinstance(v, date):
        return v
    if isinstance(v, str) and v.strip():
        try:
            return date.fromisoformat(v.strip()[:10])
        except ValueError:
            return default
    return default


def fit_phases_to_go_live(start: Any, phases: List[Dict[str, Any]], go_live: Any,
                          sequencing: str = "Sequential") -> List[Dict[str, Any]]:
    """Scale the phases up to & including the Go-Live milestone so Reverse-Shadow ends on the
    configured Go-Live date; phases after Go-Live keep their durations. PURE — returns a new
    phases list, never mutates the input. No-op (returns phases unchanged) when Go-Live is
    missing/invalid, there is no included Go-Live phase, or the nominal pre-Go-Live span is 0."""
    start_d = _as_date(start)
    gl = _as_date(go_live)
    if not start_d or not gl or gl <= start_d:
        return phases
    gl_key = next((p["key"] for p in phases
                   if p.get("milestone") == "Go-Live" and p.get("included", True)), None)
    if gl_key is None:
        return phases
    window_days = (gl - start_d).days
    # pre-Go-Live phases (up to & including the Go-Live phase), in order.
    pre_keys = []
    for p in phases:
        pre_keys.append(p["key"])
        if p["key"] == gl_key:
            break
    inc = [p for p in phases if p["key"] in set(pre_keys) and p.get("included", True)]
    weeks = [float(p.get("duration_weeks", p.get("default_weeks", 1)) or 0) for p in inc]
    total = sum(weeks)
    if total <= 0:
        return phases

    if sequencing == "Overlap":
        # Overlap span ≠ Σ durations, so scale durations + leads proportionally to the window.
        nominal = solve_timeline(start_d, phases, sequencing=sequencing)
        rs = next((r for r in nominal["rows"] if r.get("milestone") == "Go-Live"), None)
        nd = (rs["end"] - start_d).days if rs else 0
        if nd <= 0:
            return phases
        k = window_days / nd
        scale = {p["key"]: k for p in inc}
        out = []
        for p in phases:
            q = dict(p)
            if p["key"] in scale:
                q["duration_weeks"] = float(p.get("duration_weeks", p.get("default_weeks", 1)) or 0) * k
                q["overlap_lead_weeks"] = float(p.get("overlap_lead_weeks", 0) or 0) * k
            out.append(q)
        return out

    # Sequential: allocate whole days across the pre-Go-Live phases by cumulative rounding, so the
    # last one ends exactly on Go-Live (no per-phase truncation drift).
    day_alloc, running, prev_cd = {}, 0.0, 0
    for p, w in zip(inc, weeks):
        running += w
        cd = round(running / total * window_days)
        day_alloc[p["key"]] = cd - prev_cd
        prev_cd = cd
    out = []
    for p in phases:
        q = dict(p)
        if p["key"] in day_alloc:
            q["duration_weeks"] = day_alloc[p["key"]] / 7.0
        out.append(q)
    return out


def solve_timeline(start: Any, phases: List[Dict[str, Any]], sequencing: str = "Sequential",
                   overall_weeks: Optional[float] = None, go_live: Any = None,
                   incumbent_present: bool = True) -> Dict[str, Any]:
    """phases: ordered dicts {key, name, band, duration_weeks, included, overlap_lead_weeks,
    milestone, ongoing?}. Returns {rows[], milestones[], span_weeks, advisories[]}."""
    start_d = _as_date(start) or date.today()
    rows: List[Dict[str, Any]] = []
    prev_start: Optional[date] = None
    prev_end: Optional[date] = None
    for ph in phases:
        if not ph.get("included", True):
            continue
        dur = max(0.0, float(ph.get("duration_weeks", ph.get("default_weeks", 1)) or 0))
        dur_days = round(dur * 7)        # fractional weeks (from Go-Live fitting) → whole days
        if prev_end is None:
            s = start_d
        else:
            lead = float(ph.get("overlap_lead_weeks", 0) or 0) if sequencing == "Overlap" else 0.0
            s = prev_end - timedelta(days=round(lead * 7))
            if s < prev_start:          # never start before the previous phase started
                s = prev_start
        e = s + timedelta(days=dur_days)
        rows.append({"key": ph["key"], "name": ph["name"], "band": ph.get("band", ""),
                     "start": s, "end": e, "duration_weeks": dur_days / 7.0,
                     "milestone": ph.get("milestone"), "ongoing": bool(ph.get("ongoing"))})
        prev_start, prev_end = s, e

    milestones: List[Dict[str, Any]] = []
    for r in rows:
        if r["milestone"]:
            milestones.append({"id": r["milestone"], "date": r["end"], "phase": r["name"],
                               "gate": MILESTONE_GATES.get(r["milestone"], "")})

    span_weeks = round(((rows[-1]["end"] - start_d).days / 7.0), 1) if rows else 0.0

    advisories: List[str] = []
    if overall_weeks and abs(span_weeks - float(overall_weeks)) > 0.5:
        advisories.append(
            f"Phase durations span {span_weeks:g} weeks but the configured overall duration is "
            f"{float(overall_weeks):g} weeks — reconcile the per-phase durations or the overall duration.")
    gl = _as_date(go_live)
    rs = next((r for r in rows if r["key"] == "reverse_shadow"), None)
    if gl and rs:
        if gl < rs["end"]:
            advisories.append(
                f"Configured Go-Live ({gl.isoformat()}) is before the Reverse-Shadow sign-off "
                f"({rs['end'].isoformat()}) — services cannot commence before Go-Live sign-off.")
        elif (gl - rs["end"]).days > 7:
            advisories.append(
                f"Configured Go-Live ({gl.isoformat()}) is {(gl - rs['end']).days} days after the "
                f"Reverse-Shadow sign-off ({rs['end'].isoformat()}) — align them or add a buffer phase.")
    if not incumbent_present:
        advisories.append(
            "No incumbent/vendor: Shadow & Reverse-Shadow assume live operations to shadow — for a "
            "greenfield build, treat these as guided dry-runs / hypercare instead.")

    return {"start": start_d, "rows": rows, "milestones": milestones,
            "span_weeks": span_weeks, "advisories": advisories}
