"""Approval panel — preparer sees status only; reviewer (via tokened link) approves/rejects."""
import os
import streamlit as st

from modules.inputs.steps_1_2 import section_hdr, callout
from modules.state import approval_store as A


def review_link(slug, version, token) -> str:
    base = (os.environ.get("APP_BASE_URL", "") or "").rstrip("/")
    qs = f"?p={slug}&v={version}&t={token}"
    return f"{base}/{qs}" if base else qs


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


def render_approval_panel():
    from modules.state.estimate_store import store_configured
    if not store_configured():
        return

    review = st.session_state.get("_review")

    # ── Reviewer mode (opened via tokened link) ───────────────
    if review:
        st.divider()
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
    st.divider()
    section_hdr("✅ Approval")
    ref = st.session_state.get("_current_estimate_ref")
    if not ref:
        callout("Save this calculation (sidebar → <strong>💾 Save version</strong>) to request approval.", "info")
        return

    rec = A.get_approval(ref["slug"], ref["version"])
    st.caption(f"Estimate: **{ref['project']} — v{ref['version']}**")
    if rec:
        _status_badge(rec)
    else:
        callout("Status: 📝 <strong>Draft</strong> — not yet submitted for approval.", "info")

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
                from modules.notify.email_sender import email_configured, send_review_email
                sent = False
                if email_configured():
                    if not link.lower().startswith("http"):
                        st.warning("Set the APP_BASE_URL variable so the emailed link is clickable.")
                    try:
                        send_review_email(email.strip(), ref["project"], ref["version"],
                                          link, st.session_state.get("prepared_by", ""))
                        sent = True
                        st.success(f"Approval requested and emailed to {email.strip()}.")
                    except Exception as e:
                        st.warning(f"Request saved, but the email failed to send: {e}")
                else:
                    st.success("Approval requested.")
                if not sent:
                    st.caption("Share this review link with the reviewer:")
                    st.code(link)
    elif rec.get("status") == A.STATUS_PENDING:
        st.caption(f"Awaiting review by {rec.get('reviewer_email') or 'the reviewer'}. "
                   "Re-share the link below if needed:")
        st.code(review_link(ref["slug"], ref["version"], rec["token"]))
