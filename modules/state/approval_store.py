"""
Approval workflow records, stored in the estimates Blob container via managed identity.
One current approval per saved estimate version:  __approvals__/<slug>__v<version>.json

Token-gated: the reviewer's link carries a secret token; only that token unlocks
Approve/Reject. The preparer (no token) sees status only.
"""
import json
import secrets
from datetime import datetime, timezone

from modules.state.estimate_store import _container_client, store_configured  # noqa: F401

STATUS_PENDING = "pending"
STATUS_APPROVED = "approved"
STATUS_REJECTED = "rejected"

STATUS_LABEL = {
    STATUS_PENDING:  "🕓 Approval initiated — pending",
    STATUS_APPROVED: "✅ Approved",
    STATUS_REJECTED: "❌ Not approved — rework",
    "draft":         "📝 Draft — not submitted",
}


# ── Pure helpers (unit-tested) ───────────────────────────────────────────────────

def approval_blob_name(slug: str, version) -> str:
    return f"__approvals__/{slug}__v{int(version)}.json"


def new_token() -> str:
    return secrets.token_urlsafe(24)


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_request(slug, version, project, estimate_blob, reviewer_email, requested_by, token=None) -> dict:
    return {
        "slug": slug, "version": int(version), "project": project,
        "estimate_blob": estimate_blob, "reviewer_email": reviewer_email or "",
        "requested_by": requested_by or "", "requested_at": _utc(),
        "token": token or new_token(),
        "status": STATUS_PENDING, "comment": "", "decided_at": "",
    }


def apply_decision(rec: dict, token: str, approved: bool, comment: str = ""):
    """Pure: validate token + state, return (updated_rec, error)."""
    if not rec:
        return None, "No approval request found for this estimate."
    if token != rec.get("token"):
        return None, "Invalid or expired review link."
    if rec.get("status") != STATUS_PENDING:
        return rec, f"Already decided ({rec.get('status')})."
    if not approved and not (comment or "").strip():
        return None, "A comment is required to reject."
    rec = dict(rec)
    rec["status"] = STATUS_APPROVED if approved else STATUS_REJECTED
    rec["comment"] = (comment or "").strip()
    rec["decided_at"] = _utc()
    return rec, None


# ── Blob operations ───────────────────────────────────────────────────────────

def _write(rec: dict):
    cc = _container_client()
    cc.upload_blob(name=approval_blob_name(rec["slug"], rec["version"]),
                   data=json.dumps(rec, indent=2).encode("utf-8"), overwrite=True)


def request_approval(slug, version, project, estimate_blob, reviewer_email, requested_by) -> dict:
    rec = build_request(slug, version, project, estimate_blob, reviewer_email, requested_by)
    _write(rec)
    return rec


def get_approval(slug, version):
    cc = _container_client()
    try:
        raw = cc.download_blob(approval_blob_name(slug, version)).readall()
        return json.loads(raw)
    except Exception:
        return None


def decide(slug, version, token, approved, comment=""):
    rec = get_approval(slug, version)
    updated, err = apply_decision(rec, token, approved, comment)
    if err:
        return rec, err
    _write(updated)
    return updated, None
