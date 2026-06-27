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
import os
import re
import base64
import streamlit as st

from modules.inputs.steps_1_2 import callout
from modules.state import draft_store as D

# Local-part then exactly @nagarro.com. Matched against the lower-cased input.
_NAGARRO_RE = re.compile(r"^[a-z0-9][a-z0-9._%+-]*@nagarro\.com$")

# assets/ sits at the project root (this file is modules/inputs/identity_gate.py).
_LOGO_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "assets", "nagarro_logo.png")

#  IMPORTANT — selectors below use data-testids VERIFIED against Streamlit 1.58's
#  bundle: stWidgetLabel (input labels), stCaptionContainer (st.caption),
#  stTextInput (text inputs), stContainer (st.container(border=True)). A previous
#  version targeted "stVerticalBlockBorderWrapper", which does NOT exist in 1.58,
#  so the intended white card never rendered and the dark text stayed invisible.
#  Approach: keep the branded dark backdrop (the logo plate blends with it) and
#  force every text element light, rather than relying on a card surface.
_GATE_CSS = """
<style>
section[data-testid="stSidebar"] { display:none !important; }

/* Branded navy→teal backdrop — same family as the sidebar. */
[data-testid="stAppViewContainer"] {
    background: linear-gradient(160deg,#07041F 0%,#0B2530 55%,#103A41 100%) !important;
}

/* Give the bordered container a subtle translucent panel so the form reads as a
   card on the dark backdrop (text readability does NOT depend on this). */
[data-testid="stAppViewContainer"] [data-testid="stContainer"] {
    background: rgba(255,255,255,0.06) !important;
    border: 1px solid rgba(168,221,216,0.30) !important;
    border-radius: 14px !important;
    box-shadow: 0 14px 44px rgba(0,0,0,0.35) !important;
}

/* The fix: make the text Streamlit renders here light + readable on the dark bg. */
[data-testid="stWidgetLabel"], [data-testid="stWidgetLabel"] *,
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] * {
    color: #EAF6F4 !important;
}

/* Inputs keep a white field so what the user types stays dark and readable. */
[data-testid="stTextInput"] input {
    background: #FFFFFF !important;
    color: #0D1B2A !important;
}
[data-testid="stTextInput"] input::placeholder { color: #6B7B7B !important; }

/* The logo carries a fullscreen button on hover — hide it on these screens. */
[data-testid="StyledFullScreenButton"],
button[title="View fullscreen"] { display:none !important; }

.gate-logo     { text-align:center; margin:6vh 0 18px; }
.gate-logo img { width:200px; max-width:60%; height:auto; }
.gate-brand    { color:#A8DDD8; font-size:0.8rem; font-weight:600;
                 margin-top:10px; letter-spacing:0.3px; }
.gate-title { font-size:1.4rem; font-weight:800; color:#FFFFFF !important; margin:2px 0 6px; }
.gate-sub   { color:#CFEAE6; font-size:0.92rem; margin:0 0 14px; line-height:1.45; }
.gate-sub strong { color:#FFFFFF; }
.gate-row   { color:#A8DDD8; font-size:0.82rem; }
</style>
"""


def render_gate_logo():
    """Centered Nagarro logo + product line, shown above every gate card so the
    sign-in / mode screens carry the same branding as the rest of the app."""
    try:
        with open(_LOGO_PATH, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        img = f'<img src="data:image/png;base64,{b64}" alt="Nagarro"/>'
    except Exception:
        img = ('<span style="font-family:Arial,Helvetica,sans-serif;font-weight:800;'
               'font-size:2rem;color:#FFFFFF;letter-spacing:0.5px">nagarro</span>')
    st.markdown(
        f'<div class="gate-logo">{img}'
        '<div class="gate-brand">Cloud &amp; Infrastructure Practices · '
        'Ops Effort Estimation Tool</div></div>',
        unsafe_allow_html=True,
    )


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
        render_gate_logo()
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
        render_gate_logo()
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
                c1, c2, c3 = st.columns([3, 1.2, 1.2])
                # Light project name (matches .gate-sub) — plain markdown bold would
                # fall back to the dark theme text colour and be unreadable on the
                # dark gate backdrop.
                c1.markdown(
                    f"<div style='color:#CFEAE6;font-weight:700;font-size:1rem'>{proj}</div>"
                    f"<span class='gate-row'>last edited "
                    f"{d.get('saved_at','')} · {agestr}</span>",
                    unsafe_allow_html=True,
                )
                if st.session_state.get("_confirm_del_draft") == d["slug"]:
                    # Two-step delete so a stray click can't discard WIP.
                    if c2.button("✓ Delete", key=f"delyes_{d['slug']}", type="primary",
                                 use_container_width=True):
                        D.clear_draft(d["slug"])
                        st.session_state.pop("_confirm_del_draft", None)
                        st.rerun()
                    if c3.button("✕ Keep", key=f"delno_{d['slug']}", use_container_width=True):
                        st.session_state.pop("_confirm_del_draft", None)
                        st.rerun()
                else:
                    if c2.button("Resume", key=f"resume_{d['slug']}", use_container_width=True,
                                 type="primary"):
                        on_resume(d["slug"])
                    if c3.button("🗑️ Delete", key=f"del_{d['slug']}", use_container_width=True):
                        st.session_state["_confirm_del_draft"] = d["slug"]
                        st.rerun()
            st.divider()
            if st.button("🆕 Start afresh", key="resume_fresh", use_container_width=True):
                st.session_state["_resume_resolved"] = True
                st.rerun()
