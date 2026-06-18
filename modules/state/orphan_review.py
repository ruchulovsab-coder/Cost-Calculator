"""
Orphan-deletion review records. An abandoned draft is never deleted directly on
screen — the on-screen user emails a recipient a token-gated link, and the recipient
confirms the deletion on a scoped page. This reuses the approval workflow's pattern
(tokened link + ACS email).

One record per emailed batch:  __orphan_reviews__/<token>.json
carrying the recipient, the exact orphan blobs they may delete, and who requested it.
"""
import json
from datetime import datetime, timezone

from modules.state.estimate_store import _container_client, store_configured  # noqa: F401
from modules.state.approval_store import new_token  # reuse the same token generator

REVIEW_PREFIX = "__orphan_reviews__/"

STATUS_PENDING = "pending"
STATUS_PARTIAL = "partial"
STATUS_DONE = "done"


# ── Pure helpers (unit-tested) ───────────────────────────────────────────────────

def review_blob_name(token: str) -> str:
    return f"{REVIEW_PREFIX}{token}.json"


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_orphan_review(recipient, orphan_blobs, requested_by, token=None) -> dict:
    return {
        "token": token or new_token(),
        "recipient": recipient or "",
        "orphan_blobs": list(orphan_blobs or []),
        "requested_by": requested_by or "",
        "requested_at": _utc(),
        "status": STATUS_PENDING,
        "deleted_blobs": [],
        "decided_at": "",
    }


def chosen_in_scope(rec: dict, blobs):
    """The subset of `blobs` that this review record actually authorises deleting."""
    allowed = set(rec.get("orphan_blobs") or [])
    return [b for b in (blobs or []) if b in allowed]


def apply_delete(rec: dict, token: str, blobs):
    """Pure: validate the token and that the chosen blobs are within this record's
    authorised set, returning (updated_rec, error)."""
    if not rec:
        return None, "No deletion request found for this link."
    if token != rec.get("token"):
        return None, "Invalid or expired link."
    chosen = chosen_in_scope(rec, blobs)
    if not chosen:
        return None, "Select at least one item to delete."
    rec = dict(rec)
    rec["deleted_blobs"] = sorted(set(rec.get("deleted_blobs") or []) | set(chosen))
    remaining = set(rec.get("orphan_blobs") or []) - set(rec["deleted_blobs"])
    rec["status"] = STATUS_DONE if not remaining else STATUS_PARTIAL
    rec["decided_at"] = _utc()
    return rec, None


# ── Blob operations ───────────────────────────────────────────────────────────

def _write(rec: dict):
    cc = _container_client()
    cc.upload_blob(name=review_blob_name(rec["token"]),
                   data=json.dumps(rec, indent=2).encode("utf-8"), overwrite=True)


def request_orphan_review(recipient, orphan_blobs, requested_by) -> dict:
    rec = build_orphan_review(recipient, orphan_blobs, requested_by)
    _write(rec)
    return rec


def get_orphan_review(token):
    if not token or not store_configured():
        return None
    cc = _container_client()
    try:
        raw = cc.download_blob(review_blob_name(token)).readall()
        return json.loads(raw)
    except Exception:
        return None


def confirm_delete(token, blobs):
    """Validate the token, hard-delete the chosen (authorised) orphan blobs, and
    persist the updated record. Returns (updated_rec, error)."""
    rec = get_orphan_review(token)
    updated, err = apply_delete(rec, token, blobs)
    if err:
        return rec, err
    from modules.state.draft_store import delete_blobs
    delete_blobs(chosen_in_scope(rec, blobs))
    _write(updated)
    return updated, None
