"""Feedback viewer + CSV export — review every note captured across the app during
demos/reviews. Read-only over the cloud feedback store."""
import streamlit as st

from modules.state.feedback_store import list_feedback, to_csv, store_configured


def render_feedback_admin():
    st.header("🗒️ Captured Feedback")
    if not store_configured():
        st.info("The feedback store isn't configured in this environment, so nothing is captured here.")
        return
    rows = list_feedback()
    if not rows:
        st.info("No feedback captured yet. Use the **💬 Feedback** button on any page during the demo.")
        return

    modes = sorted({r.get("mode", "") for r in rows if r.get("mode")})
    cats = sorted({r.get("category", "") for r in rows if r.get("category")})
    f1, f2 = st.columns(2)
    mode_f = f1.multiselect("Mode", modes, default=modes, key="fb_admin_mode")
    cat_f = f2.multiselect("Category", cats, default=cats, key="fb_admin_cat")
    view = [r for r in rows
            if (not modes or r.get("mode", "") in mode_f)
            and (not cats or r.get("category", "") in cat_f)]

    top = st.columns([3, 1])
    top[0].caption(f"Showing **{len(view)}** of **{len(rows)}** notes.")
    top[1].download_button("⬇️ Export CSV", data=to_csv(view), file_name="feedback.csv",
                           mime="text/csv", key="fb_admin_csv", use_container_width=True)

    try:
        import pandas as pd
        df = pd.DataFrame([{
            "When (UTC)": r.get("saved_at", ""), "Stage": r.get("stage", ""),
            "Mode": r.get("mode", ""), "Category": r.get("category", ""),
            "Raised by": r.get("raised_by", ""), "Feedback": r.get("note", ""),
            "By": r.get("submitted_by", ""), "Project": r.get("project", ""),
        } for r in view])
        st.dataframe(df, use_container_width=True, hide_index=True)
    except Exception:
        # Fallback if pandas is unavailable for any reason.
        for r in view:
            st.markdown(f"**{r.get('category','')}** · _{r.get('stage','')}_ · {r.get('saved_at','')}")
            st.write(r.get("note", ""))
            st.caption(f"Raised by {r.get('raised_by','—')} · by {r.get('submitted_by','')}")
            st.divider()
