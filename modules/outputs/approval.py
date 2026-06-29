"""Approval panel — preparer sees status only; reviewer (via tokened link) approves/rejects."""
import os
import streamlit as st

from modules.inputs.steps_1_2 import section_hdr, callout
from modules.state import approval_store as A


def review_link(slug, version, token) -> str:
    base = (os.environ.get("APP_BASE_URL", "") or "").rstrip("/")
    qs = f"?p={slug}&v={version}&t={token}"
    return f"{base}/{qs}" if base else qs


def _email_artifacts(ref):
    """Build the approval email's (summary, dashboard_html, attachments) from the
    current estimate session: plain-text headline figures, the inline dashboard
    summary for the body, and the editable Excel formula workbook as an attachment.
    Best-effort — a failed workbook is simply omitted (the email still sends)."""
    from modules.state.session_manager import run_model, build_estimate_summary
    from modules.notify.email_templates import dashboard_summary_html
    model = run_model()
    summary = build_estimate_summary(model)
    body_html = dashboard_summary_html(model)
    attachments = []
    try:
        from modules.outputs.excel_model import generate_excel_model
        proj = (ref.get("project") or "estimate").replace(" ", "_")
        attachments.append({
            "name": f"{proj}_v{ref.get('version')}_model.xlsx",
            "content_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "bytes": generate_excel_model(),
        })
    except Exception:
        pass
    return summary, body_html, attachments


def _status_badge(rec):
    status = rec.get("status", "draft")
    label = A.STATUS_LABEL.get(status, status)
    kind = {"approved": "success", "rejected": "error", "pending": "info"}.get(status, "info")
    extra = ""
    if rec.get("decided_at"):
        extra += f" &nbsp;·&nbsp; {rec['decided_at']}"
    callout(f"<strong>Status:</strong> {label}{extra}", kind)
    if status == A.STATUS_REJECTED and rec.get("comment"):
        callout(f"<strong>Reviewer comment:</strong> {rec['comment']}", "warning")


def change_state(rec=None) -> dict:
    """Preparer-side state for the currently loaded estimate: is it approved, and has
    it changed since it was saved? Returns {approved, diverged, rec, ref}. `diverged`
    is only ever True once the version is approved (the post-approval rule)."""
    from modules.state.estimate_store import store_configured
    from modules.state.session_manager import inputs_changed_since_save
    ref = st.session_state.get("_current_estimate_ref")
    if not ref or not store_configured():
        return {"approved": False, "diverged": False, "rec": None, "ref": ref}
    if rec is None:
        rec = A.get_approval(ref["slug"], ref["version"])
    approved = bool(rec and rec.get("status") == A.STATUS_APPROVED)
    return {"approved": approved,
            "diverged": approved and inputs_changed_since_save(),
            "rec": rec, "ref": ref}


def save_version(note: str):
    """Save the current session as a new (auto-incremented) version, set it as the
    current estimate and re-baseline. Returns the saved meta on success, else None
    (errors surfaced via st). Shared by every 'save a version' entry point."""
    from modules.state.session_manager import (
        serialize_inputs, build_estimate_summary, run_model, mark_saved_baseline)
    from modules.state.estimate_store import save_estimate, list_estimates
    proj = (st.session_state.get("project_name") or "").strip()
    if not proj:
        st.error("Set a Customer / RFP name on Step 1 before saving.")
        return None
    try:
        meta = save_estimate(
            proj, note.strip(), (st.session_state.get("prepared_by") or "").strip(),
            serialize_inputs(), build_estimate_summary(run_model()))
        list_estimates.clear()
        st.session_state["_current_estimate_ref"] = {
            "slug": meta["project_slug"], "version": meta["version"],
            "project": meta["project"], "blob": meta.get("_blob")}
        mark_saved_baseline()
        return meta
    except Exception as e:
        st.error(f"Save failed: {e}")
        return None


def inline_save_version(note_default: str = "", key: str = "inline_save",
                        button_label: str = "💾 Save this version",
                        success_suffix: str = "") -> bool:
    """Note field + save button (shared by the first-save prompt and the changed-
    after-approval gate). Returns True only after a successful save."""
    # Auto-populate the note from the live diff vs the last saved/resumed version. It keeps
    # refreshing as the user makes more changes — until they type their own note (override).
    from modules.state.session_manager import summarize_input_changes
    nk = f"{key}_note"; ak = f"{key}_note_auto"
    auto = note_default or summarize_input_changes()
    if st.session_state.get(nk) in (None, "", st.session_state.get(ak)):
        st.session_state[nk] = auto
    st.session_state[ak] = auto
    note = st.text_input("Version note", key=nk,
                         help="Auto-filled from what changed since the last version — edit if you like.")
    if st.button(button_label, type="primary", key=f"{key}_btn", use_container_width=True):
        meta = save_version(note)
        if meta:
            st.session_state.pop(nk, None)   # let the next save re-derive from new changes
            st.success(f"Saved {meta['project']} — v{meta['version']} (draft). {success_suffix}".strip())
            st.rerun()
    return False


def render_approval_panel(locked: bool = False, rec=None):
    from modules.state.estimate_store import store_configured
    if not store_configured():
        return

    review = st.session_state.get("_review")

    # ── Reviewer mode (opened via tokened link) ───────────────
    if review:
        section_hdr("✅ Approval Review")
        slug, version, token = review["slug"], review["version"], review["token"]
        rec = A.get_approval(slug, version)
        if not rec:
            callout("This review link is no longer valid (no matching request).", "error")
            return
        if token != rec.get("token"):
            callout("Invalid or expired review link.", "error")
            return
        st.info(f"Reviewing **{rec['project']} — v{rec['version']}**  "
                f"(requested by {rec.get('requested_by') or '—'}).")
        if rec.get("status") != A.STATUS_PENDING:
            _status_badge(rec)
            return
        comment = st.text_area("Comment (required to reject; optional to approve)", key="rev_comment")
        c1, c2 = st.columns(2)
        if c1.button("✅ Approve", type="primary", key="btn_approve", use_container_width=True):
            _, err = A.decide(slug, version, token, True, comment)
            if err:
                st.error(err)
            else:
                st.success("Approved."); st.rerun()
        if c2.button("❌ Reject (Rework)", key="btn_reject", use_container_width=True):
            if not comment.strip():
                st.error("Please enter a comment explaining the rework needed.")
            else:
                _, err = A.decide(slug, version, token, False, comment)
                if err:
                    st.error(err)
                else:
                    st.warning("Sent back for rework."); st.rerun()
        return

    # ── Preparer mode ─────────────────────────────────────────
    section_hdr("✅ Approval")
    ref = st.session_state.get("_current_estimate_ref")
    if not ref:
        callout("📝 <strong>Save this estimate as a version first.</strong> Approvals are "
                "requested against a saved version — save it below (or via the sidebar → "
                "📁 Saved Calculations), then the approval request appears here.", "info")
        if not (st.session_state.get("project_name") or "").strip():
            callout("Set a <strong>Customer / RFP name</strong> on Step 1 before saving.", "warning")
            return
        inline_save_version(key="firstsave", success_suffix="Now request approval below.")
        return

    if rec is None:
        rec = A.get_approval(ref["slug"], ref["version"])
    st.caption(f"Estimate: **{ref['project']} — v{ref['version']}**")
    if rec:
        _status_badge(rec)
    else:
        callout("Status: 📝 <strong>Draft</strong> — not yet submitted for approval.", "info")

    # Blocked: this approved estimate has unsaved changes — a new version must be
    # saved (and separately approved) before any further approval action.
    if locked:
        callout("🔒 This approved estimate has changed. Save it as a <strong>new version</strong> "
                "above before requesting approval.", "warning")
        return

    # Allow (re)requesting when there's no pending request
    if not rec or rec.get("status") != A.STATUS_PENDING:
        email = st.text_input("Reviewer email", key="appr_email", placeholder="reviewer@nagarro.com")
        if st.button("📧 Request approval", type="primary", key="btn_request_approval"):
            if not email.strip():
                st.error("Enter the reviewer's email.")
            else:
                newrec = A.request_approval(
                    ref["slug"], ref["version"], ref["project"], ref["blob"],
                    email.strip(), st.session_state.get("prepared_by", ""))
                link = review_link(ref["slug"], ref["version"], newrec["token"])
                is_abs = link.lower().startswith("http")
                from modules.notify.email_sender import email_configured, send_review_email
                if email_configured() and not is_abs:
                    # Can't email a dead relative URL — and we don't expose the link
                    # to the requester (they could self-approve). Tell the admin.
                    st.error("Request saved, but no email was sent: set the APP_BASE_URL "
                             "variable so the review link is absolute and emailable.")
                elif email_configured():
                    try:
                        summary, body_html, attachments = _email_artifacts(ref)
                        send_review_email(email.strip(), ref["project"], ref["version"],
                                          link, st.session_state.get("prepared_by", ""),
                                          summary, body_html, attachments)
                        st.success(f"Approval requested and emailed to {email.strip()} "
                                   "(estimate summary in the body + Excel model attached). "
                                   "If they don't receive it, use “Resend approval email” below.")
                    except Exception as e:
                        st.warning(f"Request saved, but the email failed to send: {e}")
                else:
                    # No email channel at all — the link is the only delivery path.
                    st.success("Approval requested.")
                    st.caption("Email isn't configured — share this review link with the reviewer:")
                    st.code(link)
    elif rec.get("status") == A.STATUS_PENDING:
        # Don't show the tokened link to the requester (they could self-approve).
        # Offer a resend to the reviewer on record instead.
        from modules.notify.email_sender import email_configured, send_review_email
        st.caption(f"Awaiting review by **{rec.get('reviewer_email') or 'the reviewer'}**.")
        link = review_link(ref["slug"], ref["version"], rec["token"])
        is_abs = link.lower().startswith("http")
        if email_configured() and is_abs:
            if st.button("📧 Resend approval email", key="btn_resend_approval"):
                try:
                    summary, body_html, attachments = _email_artifacts(ref)
                    send_review_email(rec.get("reviewer_email", ""), ref["project"],
                                      ref["version"], link, rec.get("requested_by", ""),
                                      summary, body_html, attachments)
                    st.success(f"Approval email resent to {rec.get('reviewer_email') or 'the reviewer'}.")
                except Exception as e:
                    st.warning(f"Could not resend the email: {e}")
        elif not is_abs:
            st.caption("⚠️ Set the APP_BASE_URL variable so the review link can be emailed.")
        else:
            st.caption("Email isn't configured — share this review link with the reviewer:")
            st.code(link)
