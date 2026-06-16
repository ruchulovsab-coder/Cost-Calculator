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
                        input.addEventListener('focus', function() {
                            if (this.value === '0' || this.value === '0.0' || this.value === '0.00') {
                                this.select();
                            }
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

# ── Session state ──────────────────────────────────────────────────────────────
from modules.state.session_manager import init_session_state
init_session_state()

# ── Step renderers ─────────────────────────────────────────────────────────────
from modules.inputs.steps_1_2 import render_step1, render_step2
from modules.inputs.steps_3_5 import render_step3, render_step4, render_step5
from modules.inputs.steps_6_7 import render_step6, render_step7
from modules.outputs.dashboard import render_step8
from modules.outputs.scenario_comparison import render_scenario_sidebar, render_comparison, render_saved_calc_sidebar
from modules.outputs.excel_export import generate_excel_report
from modules.outputs.pdf_export import generate_pdf_report

# ── Step manifest ──────────────────────────────────────────────────────────────
STEPS = [
    (1, "Workload Volumetrics"),
    (2, "Resolution Split"),
    (3, "Patching"),
    (4, "Additional Activities"),
    (5, "Effort Summary"),
    (6, "Coverage & FTE"),
    (7, "Rate Card & Mapping"),
    (8, "Cost, Pricing & Dashboard"),
    (9, "Scenario Comparison"),
]

RENDERERS = {
    1: (render_step1, "Next: Resolution Split →"),
    2: (render_step2, "Next: Patching →"),
    3: (render_step3, "Next: Additional Activities →"),
    4: (render_step4, "Next: Effort Summary →"),
    5: (render_step5, "Next: Coverage & FTE →"),
    6: (render_step6, "Next: Rate Card & Mapping →"),
    7: (render_step7, "Next: Cost, Pricing & Dashboard →"),
    8: (render_step8, None),
    9: (render_comparison, None),
}


def step_icon(n):
    cur = st.session_state.get("current_step", 1)
    if n < cur:  return "✅"
    if n == cur: return "▶️"
    return "○"


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
            st.session_state.current_step = n
            st.rerun()

    render_saved_calc_sidebar()
    render_scenario_sidebar()

    st.divider()
    if st.button("🔄 Reset All", use_container_width=True, type="secondary"):
        from modules.state.session_manager import reset_all
        reset_all()
        st.rerun()


# ── Main content ───────────────────────────────────────────────────────────────
current = st.session_state.get("current_step", 1)
render_fn, next_label = RENDERERS.get(current, (None, None))

if render_fn:
    step_valid = render_fn()

    st.divider()
    nav_l, nav_r = st.columns([1, 5])
    with nav_l:
        if current > 1:
            if st.button("← Back", type="secondary", key="btn_back"):
                st.session_state.current_step = current - 1
                st.rerun()

    with nav_r:
        if next_label and step_valid:
            if st.button(next_label, type="primary", key="btn_next"):
                st.session_state.current_step = current + 1
                st.rerun()
        elif next_label and not step_valid:
            st.warning("⚠️ Please fix the validation errors above before proceeding.")

        # Dashboard export buttons
        if current == 8 and step_valid:
            ec1, ec2, ec3, ec4 = st.columns(4)
            with ec1:
                try:
                    xl = generate_excel_report()
                    st.download_button(
                        "⬇️ Excel Report",
                        data=xl,
                        file_name="IT_MS_Calculator_Report.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        type="primary",
                        key="dl_excel",
                    )
                except Exception as e:
                    st.error(f"Excel error: {e}")
            with ec2:
                try:
                    from modules.outputs.excel_model import generate_excel_model
                    xlm = generate_excel_model()
                    st.download_button(
                        "⬇️ Editable Excel (formulas)",
                        data=xlm,
                        file_name="IT_MS_Editable_Model.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        type="primary",
                        key="dl_excel_model",
                    )
                except Exception as e:
                    st.error(f"Editable Excel error: {e}")
            with ec3:
                try:
                    pdf = generate_pdf_report()
                    st.download_button(
                        "⬇️ PDF Proposal",
                        data=pdf,
                        file_name="IT_MS_Proposal.pdf",
                        mime="application/pdf",
                        type="primary",
                        key="dl_pdf",
                    )
                except Exception as e:
                    st.error(f"PDF error: {e}")
            with ec4:
                if st.button("📊 Compare Scenarios", type="secondary", key="btn_compare"):
                    st.session_state.current_step = 9
                    st.rerun()
