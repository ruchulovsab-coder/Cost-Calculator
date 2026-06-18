"""
Orphan clean-up UI.

Abandoned drafts are never deleted directly on screen. The on-screen user (preparer)
reviews orphans and emails a recipient a token-gated link; the recipient confirms the
deletion on a scoped page that shows only the orphans they were emailed about. This
reuses the approval workflow's tokened-link + ACS-email pattern.
"""
import os
import streamlit as st

from modules.inputs.steps_1_2 import section_hdr, callout
from modules.state import orphan_review as OR
from modules.state import draft_store as D


def orphan_link(token) -> str:
    base = (os.environ.get("APP_BASE_URL", "") or "").rstrip("/")
    qs = f"?orphan={token}"
    return f"{base}/{qs}" if base else qs


def _page_title(title: str, subtitle: str = ""):
    st.markdown(
        f'<div class="page-header"><h2>{title}</h2>'
        f'{("<p>" + subtitle + "</p>") if subtitle else ""}</div>',
        unsafe_allow_html=True,
    )


def _fmt_age(d) -> str:
    a = d.get("age_days", 0)
    return "today" if a < 1 else f"{int(a)}d ago"


def orphan_count() -> int:
    try:
        return len(D.list_orphans())
    except Exception:
        return 0


@st.cache_data(show_spinner=False, ttl=30)
def orphan_count_cached() -> int:
    """Cheap sidebar indicator value; cleared after a deletion."""
    return orphan_count()


# ── Preparer: review + email for deletion ───────────────────────────────────────

def render_orphan_admin():
    _page_title("🧹 Abandoned Draft Clean-up",
                "Review abandoned / expired draft estimates and send them to a "
                "recipient for confirmed deletion.")
    from modules.state.estimate_store import store_configured
    if not store_configured():
        callout("Draft storage isn't configured in this environment.", "info")
        return

    orphans = D.list_orphans()
    if not orphans:
        callout("No abandoned drafts. 🎉", "info")
        return

    callout("Select the abandoned drafts to clean up, then email a recipient a secure "
            "link. <strong>Deletion is confirmed by the recipient</strong> on that link "
            "— nothing is deleted from this page.", "info")

    section_hdr("Abandoned drafts")
    chosen = []
    for d in orphans:
        proj = d.get("project") or d.get("slug")
        by = d.get("prepared_by") or "—"
        label = f"**{proj}** — initiated by {by} · {_fmt_age(d)} ({d.get('saved_at','')})"
        if st.checkbox(label, key=f"orph_{d['blob']}"):
            chosen.append(d["blob"])

    st.divider()
    email = st.text_input("Recipient email", key="orph_email",
                          placeholder="owner@nagarro.com")
    if st.button(f"📧 Send {len(chosen)} for deletion", type="primary", key="orph_send"):
        if not chosen:
            st.error("Select at least one draft to clean up.")
        elif not email.strip():
            st.error("Enter the recipient's email.")
        else:
            rec = OR.request_orphan_review(email.strip(), chosen,
                                           st.session_state.get("prepared_by", ""))
            link = orphan_link(rec["token"])
            from modules.notify.email_sender import email_configured, send_orphan_review_email
            sent = False
            if email_configured() and not link.lower().startswith("http"):
                st.error("Request saved, but no email was sent: set the APP_BASE_URL "
                         "variable so the link is absolute and clickable. Share the "
                         "link below manually for now.")
            elif email_configured():
                try:
                    send_orphan_review_email(email.strip(),
                                             st.session_state.get("prepared_by", ""),
                                             len(chosen), link)
                    sent = True
                    st.success(f"Sent {len(chosen)} draft(s) to {email.strip()} for deletion.")
                except Exception as e:
                    st.warning(f"Request saved, but the email failed to send: {e}")
            else:
                st.success("Deletion request saved.")
            if not sent:
                st.caption("Share this secure link with the recipient:")
                st.code(link)


# ── Recipient: token-gated confirm + delete ─────────────────────────────────────

def render_orphan_delete(token):
    _page_title("🗑️ Confirm Draft Deletion",
                "You've been asked to permanently delete the abandoned draft "
                "estimate(s) below.")
    from modules.state.estimate_store import store_configured
    if not store_configured():
        callout("Draft storage isn't configured in this environment.", "error")
        return

    rec = OR.get_orphan_review(token)
    if not rec or token != rec.get("token"):
        callout("This deletion link is no longer valid.", "error")
        return

    allowed = rec.get("orphan_blobs") or []
    meta = {o["blob"]: o for o in D.list_orphans()}
    remaining = [b for b in allowed if b in meta]
    already = [b for b in allowed if b not in meta]

    st.caption(f"Requested by {rec.get('requested_by') or '—'} on "
               f"{rec.get('requested_at', '')}.")
    if already:
        callout(f"{len(already)} item(s) from this request were already deleted.", "info")
    if not remaining:
        callout("Nothing left to delete — all items in this request are already gone.",
                "success")
        return

    section_hdr("Drafts to delete")
    chosen = []
    for b in remaining:
        d = meta[b]
        proj = d.get("project") or d.get("slug")
        by = d.get("prepared_by") or "—"
        if st.checkbox(f"**{proj}** — initiated by {by} · {_fmt_age(d)}",
                       key=f"del_{b}", value=True):
            chosen.append(b)

    st.divider()
    callout("⚠️ Deletion is permanent and cannot be undone.", "warning")
    if st.button(f"🗑️ Delete {len(chosen)} selected", type="primary", key="orph_confirm_del"):
        if not chosen:
            st.error("Select at least one item to delete.")
        else:
            _, err = OR.confirm_delete(token, chosen)
            if err:
                st.error(err)
            else:
                orphan_count_cached.clear()
                st.success(f"Deleted {len(chosen)} draft(s).")
                st.rerun()
