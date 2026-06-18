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
    Fires on every page navigation. No-op when the store is unconfigured or the
    project is still unnamed."""
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
        if save_draft(slug, project, st.session_state.get("prepared_by", ""), serialize_inputs()):
            # This session now "owns" the draft for this slug, so we don't prompt to
            # restore our own in-progress work.
            st.session_state["_active_draft_slug"] = slug
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
    from modules.state.session_manager import load_scenario
    rec = get_draft(slug)
    if not rec:
        return
    load_scenario({"inputs": rec.get("inputs", {})})
    st.session_state["project_name"] = rec.get("project", "")
    st.session_state["prepared_by"] = rec.get("prepared_by", "")
    st.session_state["current_step"] = rec.get("inputs", {}).get("current_step", 1)
    st.session_state["_active_draft_slug"] = slug
    st.session_state["_restore_resolved_slug"] = slug
    st.rerun()


@st.dialog("Resume previous work?")
def _restore_dialog(slug, rec):
    proj = rec.get("project") or slug
    when = rec.get("saved_at", "")
    by = rec.get("prepared_by") or "—"
    st.write(f"An unsaved draft for **{proj}** already exists "
             f"(last edited {when} UTC, by {by}).")
    st.caption("Load it to continue where it was left off, or start afresh. "
               "Starting afresh keeps the old draft as an orphan — it is not deleted.")
    c1, c2 = st.columns(2)
    if c1.button("↩️ Continue previous", type="primary", key="restore_continue",
                 use_container_width=True):
        _resume_draft_now(slug)
    if c2.button("🆕 Start afresh", key="restore_fresh", use_container_width=True):
        from modules.state.draft_store import orphan_draft
        from modules.state.session_manager import reset_all
        orphan_draft(slug)
        keep_name = st.session_state.get("project_name", proj)
        keep_by = st.session_state.get("prepared_by", "")
        reset_all()
        st.session_state["project_name"] = keep_name
        st.session_state["prepared_by"] = keep_by
        st.session_state["current_step"] = 1
        st.session_state["_active_draft_slug"] = slug
        st.session_state["_restore_resolved_slug"] = slug
        st.rerun()


def _maybe_prompt_restore():
    """When the user identifies a project (Step 1) that has a resumable draft this
    session didn't create, offer to resume it. Name-driven discovery."""
    if st.session_state.get("_review") or st.session_state.get("_confirm_reset_all"):
        return
    try:
        from modules.state.estimate_store import store_configured, slugify
        if not store_configured():
            return
        project = (st.session_state.get("project_name") or "").strip()
        if not project:
            return
        slug = slugify(project)
        if st.session_state.get("_active_draft_slug") == slug:
            return  # our own in-progress work
        if st.session_state.get("_restore_resolved_slug") == slug:
            return  # already chosen for this project
        from modules.state.draft_store import get_draft, is_resumable
        rec = get_draft(slug)
        if not rec or not is_resumable(rec.get("saved_at", "")):
            return
        _restore_dialog(slug, rec)
    except Exception:
        pass


def render_resumable_sidebar():
    """Backstop discovery: list every resumable draft so work can be picked up even
    when the exact Customer/RFP name isn't remembered."""
    try:
        from modules.state.estimate_store import store_configured
        if not store_configured():
            return
        from modules.state.draft_store import list_drafts
        drafts = list_drafts()
    except Exception:
        return
    active = st.session_state.get("_active_draft_slug")
    others = [d for d in drafts if d["slug"] != active]
    if not others:
        return
    st.divider()
    st.markdown(
        "<div style='color:#A8DDD8;font-size:0.72rem;text-transform:uppercase;"
        "letter-spacing:1px;margin-bottom:4px'>Resume a draft</div>",
        unsafe_allow_html=True,
    )
    for d in others[:8]:
        label = d["project"] or d["slug"]
        age = d["age_days"]
        agestr = "today" if age < 1 else f"{int(age)}d ago"
        if st.button(f"↩️ {label}  ·  {agestr}", key=f"resume_{d['slug']}",
                     use_container_width=True, type="secondary"):
            _resume_draft_now(d["slug"])


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

    render_resumable_sidebar()
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


# ── Full-page orphan clean-up views (bypass the step nav) ────────────────────────
if st.session_state.get("_orphan_review"):
    from modules.outputs.orphan_admin import render_orphan_delete
    render_orphan_delete(st.session_state["_orphan_review"]["token"])
    st.stop()

if st.session_state.get("_show_orphan_admin"):
    from modules.outputs.orphan_admin import render_orphan_admin
    render_orphan_admin()
    st.divider()
    if st.button("← Back to estimate", key="orph_back", type="secondary"):
        st.session_state.pop("_show_orphan_admin", None)
        st.rerun()
    st.stop()


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
else:
    # Offer to resume a prior unsaved draft once the user names the project.
    _maybe_prompt_restore()

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
