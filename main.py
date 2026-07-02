"""
IT Managed Services Costing, Effort Estimation, Staffing and Pricing Calculator v2
Shared Managed Services | End-to-End Delivery Model
~"""
import sys, os

if __name__ == "__main__":
    try:
        from streamlit.runtime import exists as st_exists
        if not st_exists():
            import streamlit.web.cli as stcli
            sys.argv = ["streamlit", "run", os.path.abspath(__file__)] + sys.argv[1:]
            sys.exit(stcli.main())
    except ImportError:
        pass

sys.path.insert(0, os.path.dirname(__file__))

import streamlit as st
import streamlit.components.v1 as components

def inject_auto_select():
    components.html(
        """
        <script>
        function addFocusSelect() {
            try {
                const doc = window.parent.document;
                const inputs = doc.querySelectorAll('input');
                inputs.forEach(input => {
                    if (!input.hasAttribute('data-focus-listener')) {
                        // Select the whole value on focus so a single click lets the
                        // user type a replacement (no double-click / manual clearing).
                        input.addEventListener('focus', function() {
                            try { this.select(); } catch (e) {}
                        });
                        input.setAttribute('data-focus-listener', 'true');
                    }
                });
            } catch (e) {}
        }
        if (window.parent && window.parent.document) {
            const observer = new MutationObserver(addFocusSelect);
            observer.observe(window.parent.document.body, { childList: true, subtree: true });
            addFocusSelect();
        }
        </script>
        """,
        height=0,
        width=0,
    )

def inject_close_warning(active: bool):
    """Native browser 'leave site?' prompt while there's unsaved work in progress.
    Autosave persists on every navigation, so this guards in-page edits made since
    the last navigation. Cleared when there's no active WIP."""
    if active:
        body = (
            "try { window.parent.onbeforeunload = function (e) {"
            " e.preventDefault(); e.returnValue = ''; return ''; }; } catch (e) {}"
        )
    else:
        body = "try { window.parent.onbeforeunload = null; } catch (e) {}"
    components.html(f"<script>{body}</script>", height=0, width=0)


st.set_page_config(
    page_title="Cloud & Infrastructure Practices — Ops Effort Estimation Tool",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="expanded",
)
inject_auto_select()

# ── CSS ────────────────────────────────────────────────────────────────────────
_css = os.path.join(os.path.dirname(__file__), "assets", "styles.css")
if os.path.exists(_css):
    with open(_css) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# Sidebar background image — navy top matches the logo plate, sweeps to teal below.
# Embedded as base64 so the browser can render it (a local path isn't reachable).
import base64
_sb_bg = os.path.join(os.path.dirname(__file__), "assets", "sidebar_bg.png")
if os.path.exists(_sb_bg):
    with open(_sb_bg, "rb") as _f:
        _sb_b64 = base64.b64encode(_f.read()).decode()
    st.markdown(
        "<style>section[data-testid='stSidebar'] {"
        f"background-image:url('data:image/png;base64,{_sb_b64}') !important;"
        "background-size:cover !important;"
        "background-position:top center !important;"
        "background-repeat:no-repeat !important;}</style>",
        unsafe_allow_html=True,
    )

# ── Session state ──────────────────────────────────────────────────────────────
from modules.state.session_manager import init_session_state
init_session_state()

# TEMPORARY (TODO: remove before production) — pre-fill a representative multi-skill
# AMS scenario into empty fields for testing. Gated by config.settings.DEMO_SEED_DATA.
# See modules/demo_seed.py + the "demo-seed-temporary" memory note.
from modules.demo_seed import seed_demo_data
seed_demo_data()


# ── Deep link: approval review  (?p=<slug>&v=<version>&t=<token>) ────────────────
def _maybe_load_review():
    qp = st.query_params
    if not (qp.get("t") and qp.get("p") and qp.get("v")):
        return
    if st.session_state.get("_review_loaded"):
        return
    st.session_state["_review_loaded"] = True
    slug, tok = qp.get("p"), qp.get("t")
    try:
        ver = int(qp.get("v"))
    except Exception:
        ver = 0
    st.session_state["_review"] = {"slug": slug, "version": ver, "token": tok}
    try:
        from modules.state import approval_store as A
        from modules.state.estimate_store import load_estimate
        from modules.state.session_manager import load_scenario
        rec = A.get_approval(slug, ver)
        if rec and rec.get("token") == tok and rec.get("estimate_blob"):
            data = load_estimate(rec["estimate_blob"])
            load_scenario({"inputs": data.get("inputs", {})})
            st.session_state["_current_estimate_ref"] = {
                "slug": slug, "version": ver,
                "project": rec.get("project", slug), "blob": rec["estimate_blob"]}
        st.session_state["current_step"] = 10  # Approve & Export page
    except Exception:
        pass

_maybe_load_review()


# ── Deep link: orphan-deletion review  (?orphan=<token>) ─────────────────────────
def _maybe_load_orphan_review():
    qp = st.query_params
    tok = qp.get("orphan")
    if not tok or st.session_state.get("_orphan_loaded"):
        return
    st.session_state["_orphan_loaded"] = True
    st.session_state["_orphan_review"] = {"token": tok}

_maybe_load_orphan_review()

# ── Step renderers ─────────────────────────────────────────────────────────────
from modules.inputs.steps_1_2 import render_step1, render_step2
from modules.inputs.steps_3_5 import render_step3, render_step4, render_step5
from modules.inputs.steps_6_7 import render_step6, render_step7
from modules.outputs.dashboard import render_step8, render_step9, render_step10
from modules.outputs.scenario_comparison import render_scenario_sidebar, render_comparison, render_saved_calc_sidebar

# ── Step manifest ──────────────────────────────────────────────────────────────
STEPS = [
    (1, "Workload Volumetrics"),
    (2, "Resolution Split"),
    (3, "Patching"),
    (4, "Additional Activities"),
    (5, "Effort Summary"),
    (6, "Coverage & FTE"),
    (7, "Grade Mapping"),
    (8, "Costing Inputs"),
    (9, "Results Dashboard"),
    (10, "Approve & Export"),
    (11, "Compare"),
]

RENDERERS = {
    1: (render_step1, "Next: Resolution Split →"),
    2: (render_step2, "Next: Patching →"),
    3: (render_step3, "Next: Additional Activities →"),
    4: (render_step4, "Next: Effort Summary →"),
    5: (render_step5, "Next: Coverage & FTE →"),
    6: (render_step6, "Next: Grade Mapping →"),
    7: (render_step7, "Next: Costing Inputs →"),
    8: (render_step8, "Next: Results Dashboard →"),
    9: (render_step9, "Next: Approve & Export →"),
    10: (render_step10, None),
    11: (render_comparison, None),
}


def step_icon(n):
    cur = st.session_state.get("current_step", 1)
    if n < cur:  return "✅"
    if n == cur: return "▶️"
    return "○"


# ── Draft autosave + restore ────────────────────────────────────────────────────
def _autosave_draft():
    """Silently persist the current WIP as this project's live draft (best-effort).
    Fires on every page navigation (single mode) and on every rerun (multi-skill,
    which is tabbed and has no navigation hook). No-op when the store is unconfigured
    or the project is still unnamed. Skips redundant writes when the inputs are
    unchanged since the last save, so the multi-skill per-rerun call stays cheap."""
    try:
        from modules.state.estimate_store import store_configured, slugify
        if not store_configured():
            return
        project = (st.session_state.get("project_name") or "").strip()
        if not project:
            return
        from modules.state.draft_store import save_draft
        from modules.state.session_manager import serialize_inputs
        slug = slugify(project)
        inputs = serialize_inputs()
        # Skip the write when nothing changed (multi-skill autosaves every rerun).
        import json
        try:
            sig = hash(json.dumps(inputs, sort_keys=True, default=str))
        except Exception:
            sig = None
        if sig is not None and sig == st.session_state.get("_autosave_sig"):
            st.session_state["_active_draft_slug"] = slug
            return
        if save_draft(slug, project, st.session_state.get("prepared_by", ""), inputs):
            # This session now "owns" the draft for this slug, so we don't prompt to
            # restore our own in-progress work.
            st.session_state["_active_draft_slug"] = slug
            st.session_state["_autosave_sig"] = sig
    except Exception:
        pass


def goto_step(n: int):
    """Single navigation entry point: autosave the current draft, then move."""
    _autosave_draft()
    st.session_state.current_step = n
    st.rerun()


def _resume_draft_now(slug: str):
    """Load a stored draft back into the session and land where it was left off."""
    from modules.state.draft_store import get_draft
    from modules.state.session_manager import load_scenario, mark_saved_baseline
    rec = get_draft(slug)
    if not rec:
        return
    load_scenario({"inputs": rec.get("inputs", {})})
    st.session_state["project_name"] = rec.get("project", "")
    st.session_state["prepared_by"] = rec.get("prepared_by", "")
    st.session_state["current_step"] = rec.get("inputs", {}).get("current_step", 1)
    st.session_state["_active_draft_slug"] = slug
    st.session_state["_resume_resolved"] = True
    st.session_state["_ms_mode_resolved"] = True   # resumed draft carries its own mode
    # Record the resumed state as the baseline so subsequent edits are detected and the
    # Step 10 version-note auto-summary diffs against what was resumed (not "Initial").
    mark_saved_baseline()
    st.rerun()


def _render_orphan_admin_page(back_key: str = "orph_back"):
    """Full-page orphan clean-up view. Shared by the single-mode sidebar entry and the
    multi-skill header entry (multi has no sidebar). Ends the run via st.stop()."""
    from modules.outputs.orphan_admin import render_orphan_admin
    render_orphan_admin()
    st.divider()
    if st.button("← Back to estimate", key=back_key, type="secondary"):
        st.session_state.pop("_show_orphan_admin", None)
        st.rerun()
    st.stop()


# ── Identity gate: a valid Nagarro email unlocks the app ─────────────────────────
# Token-link visitors (approval reviewer / orphan-deletion recipient) are identified
# by their token, not an email, so they bypass the gate.
_token_mode = bool(st.session_state.get("_review") or st.session_state.get("_orphan_review"))
if not _token_mode:
    from modules.inputs.identity_gate import (
        valid_nagarro_email, render_email_gate, render_resume_modal, drafts_for_email,
    )
    if not valid_nagarro_email(st.session_state.get("user_email", "")):
        render_email_gate()
        st.stop()
    # Mode selection (Chat vs Manual) — asked every session; switchable from either side.
    if not st.session_state.get("app_mode"):
        from modules.inputs.mode_gate import render_mode_gate
        render_mode_gate()
        st.stop()
    if st.session_state["app_mode"] == "chat":
        from modules.inputs.chat_page import render_chat
        render_chat()
        st.stop()
    # ── Manual mode: offer to resume one of this user's drafts ──
    if not st.session_state.get("_resume_resolved"):
        if drafts_for_email(st.session_state["user_email"]):
            render_resume_modal(st.session_state["user_email"], _resume_draft_now)
            st.stop()
        st.session_state["_resume_resolved"] = True

    # ── Estimation mode: Single (classic stepper) vs Multi-skill (own page) ──
    from modules.inputs.multi_skill import render_mode_chooser, render_multi_skill_app
    if not st.session_state.get("_ms_mode_resolved"):
        render_mode_chooser()
        st.stop()
    if st.session_state.get("estimation_mode") == "multi":
        # Multi has no sidebar (it st.stops before it), so the orphan clean-up page is
        # reached from a header button that sets this flag. Render it here.
        if st.session_state.get("_show_orphan_admin"):
            _render_orphan_admin_page("orph_back_ms")
        render_multi_skill_app()
        _autosave_draft()   # tabbed page has no nav hook — autosave after render
        st.stop()


# Reviewer opened a MULTI-skill estimate via the tokened link (bypasses the manual
# block above): the single-mode Step 10 dashboard can't render multi inputs, so show a
# multi-aware review view. Single-mode reviews fall through to the step renderer.
if st.session_state.get("_review") and st.session_state.get("estimation_mode") == "multi":
    from modules.inputs.multi_skill import render_multi_approve_export
    render_multi_approve_export(review=True)
    st.stop()


# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    _logo = os.path.join(os.path.dirname(__file__), "assets", "nagarro_logo.png")
    if os.path.exists(_logo):
        st.image(_logo, use_container_width=True)
    else:
        # Fallback wordmark until assets/nagarro_logo.png is supplied
        st.markdown(
            "<div style='text-align:center;padding-top:12px'>"
            "<span style='font-family:Arial,Helvetica,sans-serif;font-weight:800;"
            "font-size:1.8rem;color:#FFFFFF;letter-spacing:0.5px'>nagarro</span></div>",
            unsafe_allow_html=True,
        )
    st.markdown("""
    <div style="text-align:center;padding:8px 0 6px 0;">
      <div style="font-weight:700;font-size:0.9rem;color:#FFFFFF;line-height:1.3">
        Cloud &amp; Infrastructure Practices<br>Ops Effort Estimation Tool
      </div>
      <div style="font-size:0.7rem;color:#A8DDD8;margin-top:3px">
        Cloud &amp; Infra · End-to-End Delivery
      </div>
    </div>""", unsafe_allow_html=True)

    st.divider()
    st.markdown(
        "<div style='color:#A8DDD8;font-size:0.72rem;text-transform:uppercase;"
        "letter-spacing:1px;margin-bottom:4px'>Steps</div>",
        unsafe_allow_html=True,
    )

    current = st.session_state.get("current_step", 1)
    for n, name in STEPS:
        icon = step_icon(n)
        is_cur = (n == current)
        btn_type = "primary" if is_cur else "secondary"
        if st.button(f"{icon}  {n}. {name}", key=f"nav_{n}",
                     use_container_width=True, type=btn_type):
            goto_step(n)

    render_saved_calc_sidebar()
    render_scenario_sidebar()

    st.divider()
    if st.button("🔄 Reset All", key="btn_reset_all", use_container_width=True, type="secondary"):
        st.session_state["_confirm_reset_all"] = True

    # Orphaned-draft clean-up indicator (only shown when there's something to clean up)
    try:
        from modules.outputs.orphan_admin import orphan_count_cached
        _orphans = orphan_count_cached()
    except Exception:
        _orphans = 0
    if _orphans:
        if st.button(f"🧹 Clean up drafts ({_orphans})", key="btn_orphan_admin",
                     use_container_width=True, type="secondary"):
            st.session_state["_show_orphan_admin"] = True
            st.rerun()

    st.divider()
    if st.button("💬 Switch to Chat mode", key="btn_switch_chat",
                 use_container_width=True, type="secondary"):
        st.session_state["app_mode"] = "chat"
        st.rerun()


# ── Main content ───────────────────────────────────────────────────────────────
current = st.session_state.get("current_step", 1)
render_fn, next_label = RENDERERS.get(current, (None, None))

# Scroll to the top of the page whenever the step changes
if st.session_state.get("_scroll_last") != current:
    st.session_state["_scroll_last"] = current
    components.html(
        """<script>
        const d = window.parent.document;
        d.querySelectorAll('[data-testid="stMain"],[data-testid="stAppViewContainer"]')
         .forEach(e => { try { e.scrollTo(0, 0); } catch (x) {} });
        try { window.parent.scrollTo(0, 0); } catch (x) {}
        </script>""", height=0, width=0,
    )

# Warn before closing the tab while an estimate is in progress (not on the
# token-gated orphan-deletion page, which carries no WIP of its own).
inject_close_warning(
    bool((st.session_state.get("project_name") or "").strip())
    and not st.session_state.get("_orphan_review")
)


# ── Full-page orphan clean-up views (bypass the step nav) ────────────────────────
if st.session_state.get("_orphan_review"):
    from modules.outputs.orphan_admin import render_orphan_delete
    render_orphan_delete(st.session_state["_orphan_review"]["token"])
    st.stop()

if st.session_state.get("_show_orphan_admin"):
    _render_orphan_admin_page("orph_back")


@st.dialog("Reset this page?")
def _confirm_reset(step):
    st.write("This restores **only this page's** fields to their defaults. "
             "Other pages are not affected.")
    c1, c2 = st.columns(2)
    if c1.button("Yes, reset this page", type="primary", key="confirm_reset_yes"):
        from modules.state.session_manager import reset_step
        reset_step(step)
        st.rerun()
    if c2.button("Cancel", key="confirm_reset_no"):
        st.rerun()


@st.dialog("Reset everything?")
def _confirm_reset_all():
    st.write("This clears **all inputs on every page** and returns the whole "
             "estimate to its defaults. This cannot be undone.")
    c1, c2 = st.columns(2)
    if c1.button("Yes, reset all", type="primary", key="confirm_reset_all_yes"):
        from modules.state.session_manager import reset_all
        st.session_state.pop("_confirm_reset_all", None)
        reset_all()
        st.rerun()
    if c2.button("Cancel", key="confirm_reset_all_no"):
        st.session_state.pop("_confirm_reset_all", None)
        st.rerun()

if st.session_state.get("_confirm_reset_all"):
    _confirm_reset_all()

# One-time banner after a chat-built estimate lands on the Results Dashboard.
if st.session_state.get("_chat_cooked") and current == 9:
    st.success("✅ Estimate built from your chat — using **India delivery location and "
               "India genus rates**.")
    _asm = st.session_state.get("_chat_assumptions") or []
    if _asm:
        st.markdown("**Assumptions I made:**\n" + "\n".join(f"- {a}" for a in _asm))
    st.caption("Review and adjust any field via the steps on the left, then export or save "
               "as usual.")
    st.session_state.pop("_chat_cooked", None)

if render_fn:
    step_valid = render_fn()

    st.divider()
    from modules.state.session_manager import step_has_reset
    nav_l, nav_mid, nav_r = st.columns([1, 1.4, 4])
    with nav_l:
        if current > 1:
            if st.button("← Back", type="secondary", key="btn_back"):
                goto_step(current - 1)
    with nav_mid:
        if step_has_reset(current):
            if st.button("↺ Reset this page", type="secondary", key="btn_reset_page"):
                _confirm_reset(current)

    with nav_r:
        if next_label and step_valid:
            if st.button(next_label, type="primary", key="btn_next"):
                goto_step(current + 1)
        elif next_label and not step_valid:
            st.warning("⚠️ Please fix the validation errors above before proceeding.")
