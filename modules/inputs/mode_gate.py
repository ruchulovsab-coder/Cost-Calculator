"""
Mode-selection gate (Chat vs Manual) + the Phase-1 chat placeholder.

After the email gate the user picks how to build the estimate. **Manual** routes to the
existing app, completely unchanged. **Chat** (the full conversational flow) arrives in a
later phase — for now it shows a placeholder carrying the PII / scope note and a way out.

Both screens render as the sole content of the run (the caller follows them with
st.stop()), so they are blocking and the sidebar / step nav stay hidden until a mode is
chosen. Styling reuses the identity-gate card CSS for consistency.
"""
import streamlit as st

from modules.inputs.identity_gate import _GATE_CSS


def render_mode_gate():
    """Full-screen 'Chat or Manual?' chooser. Sets st.session_state['app_mode']."""
    st.markdown(_GATE_CSS, unsafe_allow_html=True)
    _, mid, _ = st.columns([1, 2.4, 1])
    with mid:
        with st.container(border=True):
            st.markdown(
                '<div class="gate-title">How would you like to build this estimate?</div>'
                '<div class="gate-sub">Pick a way to work — you can switch anytime.</div>',
                unsafe_allow_html=True,
            )
            c1, c2 = st.columns(2)
            with c1:
                if st.button("💬  Chat to estimate", use_container_width=True,
                             type="primary", key="mode_chat"):
                    st.session_state["app_mode"] = "chat"
                    st.rerun()
                st.caption("Describe your requirement in plain language; the assistant asks "
                           "for anything missing, then calculates.")
            with c2:
                if st.button("✍️  Enter manually", use_container_width=True, key="mode_manual"):
                    st.session_state["app_mode"] = "manual"
                    st.rerun()
                st.caption("Go step by step through the full calculator — the classic flow, "
                           "unchanged.")
