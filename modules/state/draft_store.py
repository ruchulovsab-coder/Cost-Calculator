"""
Per-project WIP autosave + orphan recovery. Shares the estimates Blob container
(managed identity) with estimate_store, but is kept separate from the manual
"💾 Save version" history.

Blob layout:
    __drafts__/<slug>.json              one live draft per project, overwritten on each
                                        page navigation (the live work-in-progress).
    __orphans__/<slug>__<UTC-ts>.json   abandoned drafts, preserved (never overwritten),
                                        so they survive even if a new draft for the same
                                        name is started later.

A draft is "resumable" while it is ≤ DRAFT_ORPHAN_DAYS old. Older drafts — and any
draft the user explicitly abandons ("start afresh") — are treated as orphans. The
30-day clock is evaluated lazily on read: the app is scale-to-zero (no background
job can run), so stale drafts are simply surfaced as orphans by list_orphans()
rather than being moved on a timer.

When the estimates store is not configured (local dev), store_configured() is False
and every operation here is a graceful no-op, mirroring estimate_store/approval_store.
"""
import json
from datetime import datetime, timezone

from config.settings import DRAFT_ORPHAN_DAYS
from modules.state.estimate_store import (  # noqa: F401
    _container_client, store_configured, slugify, utc_stamp,
)

DRAFT_PREFIX = "__drafts__/"
ORPHAN_PREFIX = "__orphans__/"


# ── Pure helpers (unit-tested — no Azure required) ───────────────────────────────

def draft_blob_name(slug: str) -> str:
    return f"{DRAFT_PREFIX}{slug}.json"


def orphan_blob_name(slug: str, ts: str) -> str:
    return f"{ORPHAN_PREFIX}{slug}__{ts}.json"


def _parse_ts(ts: str):
    """Parse a 'YYYY-MM-DDTHH-MM-SSZ' stamp (estimate_store.utc_stamp format) to an
    aware UTC datetime, or None if unparseable."""
    try:
        return datetime.strptime(ts, "%Y-%m-%dT%H-%M-%SZ").replace(tzinfo=timezone.utc)
    except Exception:
        return None


def age_days(saved_at: str, now: datetime = None) -> float:
    """Age of a draft/orphan in days from its saved_at stamp. 0.0 if unparseable."""
    dt = _parse_ts(saved_at)
    if not dt:
        return 0.0
    now = now or datetime.now(timezone.utc)
    return max(0.0, (now - dt).total_seconds() / 86400.0)


def is_resumable(saved_at: str, now: datetime = None) -> bool:
    """True while the draft is within the orphan window (≤ DRAFT_ORPHAN_DAYS old)."""
    return age_days(saved_at, now) <= DRAFT_ORPHAN_DAYS


def build_draft(slug: str, project: str, prepared_by: str, inputs: dict, saved_at: str = None) -> dict:
    """Assemble the JSON document stored per live draft. Pure."""
    return {
        "slug": slug,
        "project": project or "",
        "prepared_by": prepared_by or "",
        "saved_at": saved_at or utc_stamp(),
        "inputs": inputs or {},
    }


def orphan_name_parts(blob_name: str):
    """('__orphans__/<slug>__<ts>.json') → (slug, ts). Best-effort."""
    leaf = blob_name.rsplit("/", 1)[-1]
    if leaf.endswith(".json"):
        leaf = leaf[:-5]
    if "__" in leaf:
        slug, ts = leaf.rsplit("__", 1)
        return slug, ts
    return leaf, ""


# ── Blob operations ──────────────────────────────────────────────────────────

def _safe_download(cc, name):
    try:
        return json.loads(cc.download_blob(name).readall())
    except Exception:
        return None


def _delete(cc, name):
    try:
        cc.delete_blob(name)
        return True
    except Exception:
        return False


def _list_names(prefix: str):
    cc = _container_client()
    try:
        return [n for n in cc.list_blob_names(name_starts_with=prefix)]
    except Exception:
        return [getattr(b, "name", None) for b in cc.list_blobs(name_starts_with=prefix)]


def save_draft(slug: str, project: str, prepared_by: str, inputs: dict) -> bool:
    """Overwrite this project's live draft with the current WIP. No-op (False) when
    the store is unconfigured or the project is unnamed/untitled."""
    if not store_configured() or not slug or slug == "untitled":
        return False
    rec = build_draft(slug, project, prepared_by, inputs, utc_stamp())
    cc = _container_client()
    cc.upload_blob(name=draft_blob_name(slug),
                   data=json.dumps(rec, indent=2, default=str).encode("utf-8"),
                   overwrite=True)
    return True


def get_draft(slug: str):
    """Return this project's live draft record, or None."""
    if not store_configured() or not slug:
        return None
    return _safe_download(_container_client(), draft_blob_name(slug))


def orphan_draft(slug: str) -> bool:
    """Preserve this project's draft into the orphan namespace, then drop the live
    draft. Idempotent; returns False if there was nothing to orphan."""
    if not store_configured() or not slug:
        return False
    rec = get_draft(slug)
    if not rec:
        return False
    cc = _container_client()
    ts = rec.get("saved_at") or utc_stamp()
    cc.upload_blob(name=orphan_blob_name(slug, ts),
                   data=json.dumps(rec, indent=2, default=str).encode("utf-8"),
                   overwrite=True)
    _delete(cc, draft_blob_name(slug))
    return True


def clear_draft(slug: str) -> bool:
    """Drop this project's live draft without preserving it (used after an explicit
    Save version, where the work is already in the version history)."""
    if not store_configured() or not slug:
        return False
    return _delete(_container_client(), draft_blob_name(slug))


def list_drafts(include_stale: bool = False) -> list:
    """All live drafts. By default only the resumable (≤ DRAFT_ORPHAN_DAYS) ones;
    stale drafts are surfaced as orphans via list_orphans() instead."""
    if not store_configured():
        return []
    cc = _container_client()
    out = []
    for name in _list_names(DRAFT_PREFIX):
        if not name or not name.endswith(".json"):
            continue
        rec = _safe_download(cc, name)
        if not rec:
            continue
        saved_at = rec.get("saved_at", "")
        item = {
            "blob": name,
            "slug": rec.get("slug") or name[len(DRAFT_PREFIX):-5],
            "project": rec.get("project", ""),
            "prepared_by": rec.get("prepared_by", ""),
            "saved_at": saved_at,
            "age_days": age_days(saved_at),
            "resumable": is_resumable(saved_at),
        }
        if include_stale or item["resumable"]:
            out.append(item)
    out.sort(key=lambda x: x.get("saved_at") or "", reverse=True)
    return out


def list_orphans() -> list:
    """Every orphan: explicit orphan blobs PLUS stale (> DRAFT_ORPHAN_DAYS) drafts,
    which are treated as orphans without being physically moved. Each carries the
    project, who initiated it (prepared_by), and its age."""
    if not store_configured():
        return []
    cc = _container_client()
    out = []
    for name in _list_names(ORPHAN_PREFIX):
        if not name or not name.endswith(".json"):
            continue
        rec = _safe_download(cc, name)
        if not rec:
            continue
        saved_at = rec.get("saved_at", "")
        out.append({
            "blob": name, "kind": "orphan",
            "slug": rec.get("slug", ""), "project": rec.get("project", ""),
            "prepared_by": rec.get("prepared_by", ""),
            "saved_at": saved_at, "age_days": age_days(saved_at),
        })
    for d in list_drafts(include_stale=True):
        if not d["resumable"]:
            out.append({
                "blob": d["blob"], "kind": "stale_draft",
                "slug": d["slug"], "project": d["project"],
                "prepared_by": d["prepared_by"],
                "saved_at": d["saved_at"], "age_days": d["age_days"],
            })
    out.sort(key=lambda x: x.get("saved_at") or "", reverse=True)
    return out


def delete_blobs(names) -> int:
    """Hard-delete the given draft/orphan blobs (used by the orphan review flow).
    Returns the count actually deleted."""
    if not store_configured() or not names:
        return 0
    cc = _container_client()
    return sum(1 for n in names if n and _delete(cc, n))
