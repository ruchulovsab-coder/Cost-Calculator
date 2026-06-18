"""
Identity gate + resume modal.

The whole app is gated behind a Nagarro email: until a valid @nagarro.com address is
entered, nothing else renders — so every field, button and the step nav are
effectively disabled. The email is the owner key for a user's drafts (and pre-fills
the estimate's "Prepared By"). Once a valid email is given, a blocking, non-dismissible
modal offers to resume one of *that user's own* drafts or start afresh — shown only
when such drafts actually exist.

Both screens render as the sole content of the run (the caller follows them with
st.stop()), which is what makes them truly blocking — Streamlit's native st.dialog can
be dismissed by clicking the backdrop, so it isn't used here.
"""
import re
import streamlit as st

from modules.inputs.steps_1_2 import callout
from modules.state import draft_store as D

# Local-part then exactly @nagarro.com. Matched against the lower-cased input.
_NAGARRO_RE = re.compile(r"^[a-z0-9][a-z0-9._%+-]*@nagarro\.com$")

_GATE_CSS = """
<style>
section[data-testid="stSidebar"] { display:none !important; }
[data-testid="stAppViewContainer"] { background:#0E2A30 !important; }
.gate-title { font-size:1.35rem; font-weight:800; color:#0E2A30; margin:2px 0 6px; }
.gate-sub   { color:#3A6B73; font-size:0.92rem; margin:0 0 14px; line-height:1.4; }
.gate-row   { color:#3A6B73; font-size:0.82rem; }
</style>
"""


def _norm(s: str) -> str:
    return (s or "").strip().lower()


def valid_nagarro_email(s: str) -> bool:
    return bool(_NAGARRO_RE.match(_norm(s)))


def drafts_for_email(email: str) -> list:
    """Resumable drafts owned by this email (draft.prepared_by == email)."""
    e = _norm(email)
    if not e:
        return []
    try:
        return [d for d in D.list_drafts() if _norm(d.get("prepared_by", "")) == e]
    except Exception:
        return []


def _lower_email_cb():
    st.session_state["email_gate_w"] = _norm(st.session_state.get("email_gate_w", ""))


def render_email_gate():
    """Full-screen Nagarro-email gate. Sets user_email + prepared_by on success."""
    st.markdown(_GATE_CSS, unsafe_allow_html=True)
    _, mid, _ = st.columns([1, 2, 1])
    with mid:
        with st.container(border=True):
            st.markdown(
                '<div class="gate-title">🔐 Identify yourself to continue</div>'
                '<div class="gate-sub">Enter your Nagarro email to start. Everything '
                'stays locked until a valid email is provided.</div>',
                unsafe_allow_html=True,
            )
            email = st.text_input(
                "Your Nagarro Email *", key="email_gate_w",
                placeholder="firstname.lastname@nagarro.com",
                on_change=_lower_email_cb,
            )
            st.caption("📌 This email lets you find your saved versions and drafts later.")
            email = _norm(email)
            valid = valid_nagarro_email(email)
            if email and not valid:
                callout("Enter a valid <strong>@nagarro.com</strong> email address.", "warning")
            if st.button("Continue →", type="primary", disabled=not valid,
                         use_container_width=True, key="email_gate_continue"):
                st.session_state["user_email"] = email
                st.session_state["prepared_by"] = email
                st.rerun()


def render_resume_modal(email: str, on_resume):
    """Full-screen blocking modal: resume one of this user's drafts, or start afresh.
    `on_resume(slug)` loads the chosen draft. Only call when drafts_for_email is
    non-empty."""
    st.markdown(_GATE_CSS, unsafe_allow_html=True)
    drafts = drafts_for_email(email)
    _, mid, _ = st.columns([1, 2.4, 1])
    with mid:
        with st.container(border=True):
            st.markdown(
                '<div class="gate-title">↩️ Resume a draft?</div>'
                f'<div class="gate-sub">You have unsaved draft(s) under '
                f'<strong>{email}</strong>. Resume one to continue where you left off, '
                'or start a fresh estimate. Your other drafts stay saved.</div>',
                unsafe_allow_html=True,
            )
            for d in drafts:
                proj = d.get("project") or d.get("slug")
                age = d.get("age_days", 0)
                agestr = "today" if age < 1 else f"{int(age)}d ago"
                c1, c2 = st.columns([3, 1])
                c1.markdown(
                    f"**{proj}**  \n<span class='gate-row'>last edited "
                    f"{d.get('saved_at','')} · {agestr}</span>",
                    unsafe_allow_html=True,
                )
                if c2.button("Resume", key=f"resume_{d['slug']}", use_container_width=True,
                             type="primary"):
                    on_resume(d["slug"])
            st.divider()
            if st.button("🆕 Start afresh", key="resume_fresh", use_container_width=True):
                st.session_state["_resume_resolved"] = True
                st.rerun()
