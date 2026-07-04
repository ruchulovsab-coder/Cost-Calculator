"""Global real-time feedback control — a compact popover present on every page/stage
(single-mode steps, every multi-skill tab, chat). Category + Raised-by + notes → cloud
on Submit, auto-tagged with the stage, mode, user, project and app version.

Deterministic, additive, self-contained; graceful no-op when the feedback store isn't
configured (local dev)."""
import streamlit as st

from config.settings import APP_VERSION
from modules.state.feedback_store import CATEGORIES, save_feedback, store_configured


def render_feedback_widget(stage: str, key: str):
    """Render the 💬 Feedback popover for the given stage label. `key` must be unique
    per placement (one per step / tab)."""
    # A nonce lets us reset the fields after a submit (fresh widget keys), avoiding the
    # "cannot modify a widget after it is instantiated" pitfall.
    nonce = st.session_state.get(f"{key}_n", 0)
    k = f"{key}_{nonce}"
    with st.popover("💬 Feedback", use_container_width=False):
        st.markdown(f"<span style='font-size:.8rem;color:#7A8A99'>Feedback on "
                    f"<strong>{stage}</strong></span>", unsafe_allow_html=True)
        cat = st.selectbox("Category", CATEGORIES, key=f"{k}_cat")
        by = st.text_input("Raised by (name / role)", key=f"{k}_by",
                           placeholder="e.g. Manager · Client SME · Team")
        note = st.text_area("Feedback", key=f"{k}_note", height=110,
                            placeholder="Capture what was said…")
        if st.button("Submit", type="primary", key=f"{k}_submit", use_container_width=True):
            if not (note or "").strip():
                st.warning("Add a note first.")
            elif not store_configured():
                st.warning("Feedback store isn't configured here — not saved (local dev).")
            else:
                ok = save_feedback(
                    stage=stage, category=cat, raised_by=by, note=note,
                    submitted_by=st.session_state.get("user_email", ""),
                    mode=(st.session_state.get("estimation_mode")
                          or st.session_state.get("app_mode") or "single"),
                    project=(st.session_state.get("project_name") or "").strip(),
                    app_version=APP_VERSION)
                if ok:
                    st.session_state[f"{key}_n"] = nonce + 1      # reset the fields
                    st.session_state["_fb_toast"] = "✓ Feedback saved"
                    st.rerun()
                else:
                    st.warning("Couldn't save — please try again.")
