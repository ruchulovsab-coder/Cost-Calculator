"""
Conversational "Chat to estimate" page.

Guarded chat (see modules/llm/chat_assist.py) → structured inputs → applied to the
session using **India delivery rates** → lands on the Results Dashboard in manual mode,
where every field stays reviewable/editable. Degrades gracefully when the AI isn't
configured.
"""
import streamlit as st

from modules.inputs.steps_1_2 import callout
from modules.inputs.identity_gate import _GATE_CSS
from modules.llm import chat_assist as CA


def _apply_and_cook(data: dict):
    """Apply the assistant's extracted inputs to session state (India delivery rates),
    auto-map role→genus from the India rate card, and land on the Results Dashboard."""
    from modules.state.session_manager import apply_total_volume
    from config.settings import ALL_ROLES, GRADE_ELIGIBILITY

    totals = st.session_state.setdefault("workload_totals", {})
    for key, field in (("alerts", "monthly_alerts"),
                       ("service_requests", "monthly_service_requests"),
                       ("incidents", "monthly_incidents"),
                       ("changes", "monthly_changes")):
        v = int(data.get(field, 0) or 0)
        totals[key] = v
        apply_total_volume(key, v)

    servers = int(data.get("num_servers", 0) or 0)
    st.session_state["num_servers"] = servers
    inc = data.get("patching_included", servers > 0)
    st.session_state["patching_included"] = "Yes" if (inc and servers > 0) else "No"
    method = data.get("patching_method") or "Tool-Based"
    st.session_state["patching_method"] = method if method in ("Manual", "Tool-Based") else "Tool-Based"

    st.session_state["coverage_model"] = CA.normalize_coverage(data.get("coverage_model", "8×5"))
    st.session_state["contingency_pct"] = float(data.get("contingency_pct", 10.0) or 0)
    st.session_state["target_margin_pct"] = float(data.get("target_margin_pct", 20.0) or 0)
    st.session_state["reporting_currency"] = "INR"

    # ── India delivery + cloud rate card + auto genus mapping ──
    st.session_state["delivery_country"] = "India"
    st.session_state["delivery_location"] = None
    try:
        from modules.inputs.steps_6_7 import auto_load_rate_card
        auto_load_rate_card()
    except Exception:
        pass

    available = set()
    df = st.session_state.get("rate_card_df")
    if df is not None:
        try:
            from modules.calculations.engine import filter_rate_card
            scoped = filter_rate_card(df, "India", None)
            available = set(scoped["genus"].dropna().astype(str).tolist())
        except Exception:
            available = set()
    st.session_state["role_genus"] = {
        r: next((g for g in GRADE_ELIGIBILITY.get(r, []) if g in available),
                (GRADE_ELIGIBILITY.get(r, [None]) or [None])[0])
        for r in ALL_ROLES
    }

    st.session_state["_chat_assumptions"] = list(data.get("assumptions", []) or [])
    st.session_state["_chat_cooked"] = True
    st.session_state["project_name"] = st.session_state.get("project_name") or "Chat estimate"
    st.session_state["current_step"] = 9       # Results Dashboard
    st.session_state["app_mode"] = "manual"     # render via the normal app (sidebar, exports…)
    st.session_state["_resume_resolved"] = True


def render_chat():
    st.markdown(_GATE_CSS, unsafe_allow_html=True)
    # This page renders on the gate's dark background but (unlike the email/mode
    # gates) outside a light bordered card, so the shared dark .gate-title text would
    # be invisible — force light header colours that read on the dark backdrop.
    st.markdown(
        '<div class="gate-title" style="color:#FFFFFF">💬 Chat to estimate</div>'
        '<div class="gate-sub" style="color:#A8DDD8">Describe your managed-services '
        'requirement; I\'ll ask for anything missing, then build the estimate using '
        '<strong style="color:#FFFFFF">India delivery rates</strong>.</div>',
        unsafe_allow_html=True,
    )
    callout("⚠️ <strong>Do not enter personal or client-identifying information</strong> "
            "(customer names, locations, contacts). I only handle managed-services effort &amp; "
            "cost estimation.", "warning")

    if not CA.llm_configured():
        callout("AI chat isn't configured in this environment yet. Please use manual entry.", "info")
        if st.button("✍️ Switch to manual entry", type="primary", key="chat_to_manual_nc"):
            st.session_state["app_mode"] = "manual"; st.rerun()
        if st.button("← Back to mode selection", key="chat_back_nc"):
            st.session_state.pop("app_mode", None); st.rerun()
        return

    msgs = st.session_state.setdefault("chat_messages", [])

    c1, c2 = st.columns(2)
    if c1.button("✍️ Switch to manual entry", key="chat_to_manual"):
        st.session_state["app_mode"] = "manual"; st.rerun()
    if c2.button("🔄 Restart chat", key="chat_restart"):
        st.session_state["chat_messages"] = []; st.rerun()

    # Greeting + full conversation history
    with st.chat_message("assistant"):
        st.write("Hi! Tell me about the service — e.g. *“~2000 alerts, 300 incidents, 150 service "
                 "requests and 40 changes a month, 500 servers, 24×7.”* I'll ask if anything's missing.")
    for m in msgs:
        with st.chat_message(m["role"]):
            st.write(m["content"])

    prompt = st.chat_input("Describe the requirement, or answer my question…")
    if prompt:
        msgs.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.write(prompt)
        with st.chat_message("assistant"):
            with st.spinner("Thinking…"):
                result = CA.run_chat_turn(msgs)
            if result["type"] == "error":
                # Shown inline (no rerun) so the actual reason stays readable; just retry.
                st.error(result["text"])
            elif result["type"] == "question":
                st.write(result["text"])
                msgs.append({"role": "assistant", "content": result["text"]})
            elif result["type"] == "submit":
                st.write(result["preface"])
                msgs.append({"role": "assistant", "content": result["preface"]})
                _apply_and_cook(result["data"])
                st.rerun()   # only rerun to leave chat and show the Results Dashboard
