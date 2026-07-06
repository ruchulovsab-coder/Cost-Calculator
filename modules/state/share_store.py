"""Share records — one per saved estimate version, stored in the estimates Blob
container via managed identity:  __shares__/<slug>__v<version>.json

A share holds a list of recipients, each with their own secret token and a role
(viewer | editor). The recipient opens a capability link that carries the token
(?sh=<slug>&v=<version>&k=<token>); the token grants exactly that role — viewer =
read-only (the estimate opens locked), editor = may edit and save a NEW version
under the same estimate. Tokens are per-recipient, so a single person can be
revoked or have their role changed without affecting the others.

This mirrors approval_store: pure helpers (unit-tested) + thin Blob operations.
"""
import copy
import json
import secrets
from datetime import datetime, timezone

from modules.state.estimate_store import _container_client, store_configured  # noqa: F401

ROLE_VIEWER = "viewer"
ROLE_EDITOR = "editor"
ROLES = (ROLE_VIEWER, ROLE_EDITOR)

ROLE_LABEL = {
    ROLE_VIEWER: "👁️ Read-only",
    ROLE_EDITOR: "✏️ Editor",
}


# ── Pure helpers (unit-tested) ───────────────────────────────────────────────────

def share_blob_name(slug: str, version) -> str:
    return f"__shares__/{slug}__v{int(version)}.json"


def new_token() -> str:
    return secrets.token_urlsafe(24)


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def normalize_role(role) -> str:
    """Coerce any input to a valid role; default to viewer (least privilege)."""
    r = (role or "").strip().lower()
    return r if r in ROLES else ROLE_VIEWER


def build_share(slug, version, project, estimate_blob, shared_by) -> dict:
    return {
        "slug": slug, "version": int(version), "project": project or "",
        "estimate_blob": estimate_blob or "", "shared_by": shared_by or "",
        "created_at": _utc(), "recipients": [],
    }


def _new_recipient(email, role, token=None) -> dict:
    return {
        "email": (email or "").strip(), "role": normalize_role(role),
        "token": token or new_token(), "created_at": _utc(),
        "revoked": False, "last_opened_at": "",
    }


def add_recipient(rec: dict, email, role, token=None):
    """Pure: return (updated_rec, recipient). If an active recipient with the same
    email (case-insensitive) already exists, update its role and re-activate it
    instead of creating a duplicate (a re-invite keeps the original token)."""
    rec = copy.deepcopy(rec)
    email_l = (email or "").strip().lower()
    for r in rec["recipients"]:
        if r.get("email", "").strip().lower() == email_l and not r.get("revoked"):
            r["role"] = normalize_role(role)
            return rec, r
    r = _new_recipient(email, role, token)
    rec["recipients"].append(r)
    return rec, r


def find_recipient(rec: dict, token: str):
    if not rec:
        return None
    for r in rec.get("recipients", []):
        if r.get("token") == token:
            return r
    return None


def resolve(rec: dict, token: str):
    """Pure: validate a token against a share record. Returns (recipient, error)."""
    if not rec:
        return None, "This share link is no longer valid."
    r = find_recipient(rec, token)
    if not r:
        return None, "Invalid or expired share link."
    if r.get("revoked"):
        return None, "This share link has been revoked."
    return r, None


def set_role(rec: dict, token: str, role: str):
    """Pure: return (updated_rec, error)."""
    rec = copy.deepcopy(rec)
    r = find_recipient(rec, token)
    if not r:
        return rec, "Recipient not found."
    r["role"] = normalize_role(role)
    return rec, None


def revoke(rec: dict, token: str):
    """Pure: return (updated_rec, error)."""
    rec = copy.deepcopy(rec)
    r = find_recipient(rec, token)
    if not r:
        return rec, "Recipient not found."
    r["revoked"] = True
    return rec, None


def mark_opened(rec: dict, token: str, when: str = None):
    """Pure: stamp last_opened_at. Return (updated_rec, changed)."""
    rec = copy.deepcopy(rec)
    r = find_recipient(rec, token)
    if not r or r.get("revoked"):
        return rec, False
    r["last_opened_at"] = when or _utc()
    return rec, True


def active_recipients(rec: dict) -> list:
    return [r for r in (rec or {}).get("recipients", []) if not r.get("revoked")]


# ── Blob operations ───────────────────────────────────────────────────────────

def _write(rec: dict):
    cc = _container_client()
    cc.upload_blob(name=share_blob_name(rec["slug"], rec["version"]),
                   data=json.dumps(rec, indent=2, default=str).encode("utf-8"),
                   overwrite=True)


def get_share(slug, version):
    cc = _container_client()
    try:
        raw = cc.download_blob(share_blob_name(slug, version)).readall()
        return json.loads(raw)
    except Exception:
        return None


def _load_or_build(slug, version, project, estimate_blob, shared_by) -> dict:
    rec = get_share(slug, version)
    if rec:
        # Keep identity fields fresh (project rename / re-save can change the blob).
        rec["project"] = project or rec.get("project", "")
        rec["estimate_blob"] = estimate_blob or rec.get("estimate_blob", "")
        if shared_by and not rec.get("shared_by"):
            rec["shared_by"] = shared_by
        return rec
    return build_share(slug, version, project, estimate_blob, shared_by)


def add_recipients(slug, version, project, estimate_blob, shared_by, emails, role):
    """Add one or more recipients (all the same role) to a version's share record,
    creating the record if needed. Returns (rec, added_recipients)."""
    rec = _load_or_build(slug, version, project, estimate_blob, shared_by)
    added = []
    for email in emails:
        if not (email or "").strip():
            continue
        rec, r = add_recipient(rec, email, role)
        added.append(r)
    _write(rec)
    return rec, added


def revoke_recipient(slug, version, token):
    rec = get_share(slug, version)
    updated, err = revoke(rec, token)
    if err:
        return rec, err
    _write(updated)
    return updated, None


def set_recipient_role(slug, version, token, role):
    rec = get_share(slug, version)
    updated, err = set_role(rec, token, role)
    if err:
        return rec, err
    _write(updated)
    return updated, None


def record_open(slug, version, token):
    """Best-effort: stamp last_opened_at for the recipient. Never raises."""
    try:
        rec = get_share(slug, version)
        updated, changed = mark_opened(rec, token)
        if changed:
            _write(updated)
    except Exception:
        pass
