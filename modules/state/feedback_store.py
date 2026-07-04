"""Real-time feedback capture (demos / reviews). Stores one JSON blob per note in the
shared estimates container (managed identity), under __feedback__/. Graceful no-op when
the store isn't configured (local dev), mirroring estimate_store/draft_store.

Blob layout:  __feedback__/<UTC-timestamp>__<id>.json
"""
import json
import uuid

from modules.state.estimate_store import (  # noqa: F401  (reuse the configured Blob client)
    _container_client, store_configured, utc_stamp,
)

FEEDBACK_PREFIX = "__feedback__/"

CATEGORIES = ["General", "Bug / Defect", "UX / Usability", "Idea / Enhancement",
              "Data / Calculation", "Question"]

# CSV / table column order (also the export order).
FIELDS = ["saved_at", "stage", "mode", "category", "raised_by", "note",
          "submitted_by", "project", "app_version", "id"]


# ── Pure helpers (unit-tested — no Azure required) ───────────────────────────────

def build_feedback(stage, category, raised_by, note, submitted_by="", mode="",
                   project="", app_version="", saved_at=None, fid=None) -> dict:
    """Assemble the JSON document stored per feedback note. Pure."""
    return {
        "id": fid or uuid.uuid4().hex[:8],
        "saved_at": saved_at or utc_stamp(),
        "stage": (stage or "").strip(),
        "category": category or "General",
        "raised_by": (raised_by or "").strip(),
        "note": (note or "").strip(),
        "submitted_by": submitted_by or "",
        "mode": mode or "",
        "project": (project or "").strip(),
        "app_version": app_version or "",
    }


def feedback_blob_name(saved_at: str, fid: str) -> str:
    return f"{FEEDBACK_PREFIX}{saved_at}__{fid}.json"


def to_csv(rows) -> str:
    """Render feedback rows as CSV text (FIELDS order). Pure."""
    import csv
    import io
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(FIELDS)
    for r in (rows or []):
        w.writerow([str(r.get(c, "")) for c in FIELDS])
    return buf.getvalue()


# ── Blob operations ──────────────────────────────────────────────────────────

def save_feedback(stage, category, raised_by, note, submitted_by="", mode="",
                  project="", app_version="") -> bool:
    """Persist one feedback note. No-op (False) when the store is unconfigured or the
    note is empty."""
    if not store_configured() or not (note or "").strip():
        return False
    rec = build_feedback(stage, category, raised_by, note, submitted_by, mode, project, app_version)
    cc = _container_client()
    cc.upload_blob(name=feedback_blob_name(rec["saved_at"], rec["id"]),
                   data=json.dumps(rec, indent=2, default=str).encode("utf-8"),
                   overwrite=True)
    return True


def _list_names():
    cc = _container_client()
    try:
        return [n for n in cc.list_blob_names(name_starts_with=FEEDBACK_PREFIX)]
    except Exception:
        return [getattr(b, "name", None) for b in cc.list_blobs(name_starts_with=FEEDBACK_PREFIX)]


def list_feedback() -> list:
    """Every captured feedback note, newest first. Empty when unconfigured."""
    if not store_configured():
        return []
    cc = _container_client()
    out = []
    for name in _list_names():
        if not name or not name.endswith(".json"):
            continue
        try:
            rec = json.loads(cc.download_blob(name).readall())
            rec["_blob"] = name
            out.append(rec)
        except Exception:
            continue
    out.sort(key=lambda r: r.get("saved_at") or "", reverse=True)
    return out


def feedback_count() -> int:
    """Cheap count for the header/sidebar badge. 0 when unconfigured."""
    if not store_configured():
        return 0
    try:
        return sum(1 for n in _list_names() if n and n.endswith(".json"))
    except Exception:
        return 0
