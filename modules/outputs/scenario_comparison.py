"""Scenario save/load/compare."""
import json
import streamlit as st
import pandas as pd
from modules.inputs.steps_1_2 import section_hdr, callout


def render_scenario_sidebar():
    st.sidebar.divider()
    st.sidebar.markdown("### 💾 Scenarios")
    with st.sidebar.expander("Save Scenario"):
        name = st.text_input("Scenario Name", key="scen_name")
        desc = st.text_area("Description", key="scen_desc", height=50)
        if st.button("💾 Save", key="btn_save_scen"):
            if not name.strip():
                st.error("Enter a name.")
            else:
                from modules.state.session_manager import export_scenario
                scen = export_scenario(name.strip(), desc.strip())
                st.session_state["_last_scenario"] = scen
                st.success(f"Saved: {name}")
    if st.session_state.get("_last_scenario"):
        s = st.session_state["_last_scenario"]
        st.sidebar.download_button(
            "⬇️ Download JSON",
            data=json.dumps(s, indent=2, default=str),
            file_name=f"{s['meta']['name'].replace(' ','_')}_{s['meta']['date']}.json",
            mime="application/json",
            key="dl_scen",
        )
    with st.sidebar.expander("Load Scenario"):
        up = st.file_uploader("Upload JSON", type=["json"], key="scen_load_upload")
        if up:
            try:
                data = json.load(up)
                if "meta" in data and "inputs" in data:
                    from modules.state.session_manager import load_scenario
                    load_scenario(data)
                    st.success(f"Loaded: {data['meta']['name']}")
                    st.rerun()
                else:
                    st.error("Invalid scenario file.")
            except Exception as e:
                st.error(str(e))


def render_comparison():
    section_hdr("📊 Scenario Comparison")
    callout("Upload 2–3 saved scenario JSON files to compare side by side.", "info")
    cols = st.columns(3)
    scenarios = []
    for i, (col, lbl) in enumerate(zip(cols, ["Scenario A","Scenario B","Scenario C"])):
        with col:
            st.markdown(f"**{lbl}**")
            up = st.file_uploader(f"Upload {lbl}", type=["json"], key=f"cmp_{i}")
            if up:
                try:
                    data = json.load(up)
                    scenarios.append((lbl, data))
                    st.success(data["meta"]["name"])
                except Exception as e:
                    st.error(str(e))
    if len(scenarios) < 2:
        callout("Upload at least 2 scenarios.", "warning")
        return

    def get(d, *keys, default="—"):
        v = d.get("inputs", {})
        for k in keys:
            if isinstance(v, dict): v = v.get(k, default)
            else: return default
        return v

    metrics = [
        ("Coverage Model",       lambda d: get(d,"coverage_model")),
        ("Contingency %",        lambda d: f"{get(d,'contingency_pct',default=0):.1f}%"),
        ("Total Effort (Hrs)",   lambda d: f"{get(d,'_total_effort',default=0):.1f}"),
        ("Delivery Location",    lambda d: f"{get(d,'delivery_country','—')} / {get(d,'delivery_location','—')}"),
        ("Gross Margin %",       lambda d: f"{get(d,'target_margin_pct',default=0):.1f}%"),
    ]
    rows = []
    for lbl, fn in metrics:
        row = {"Metric": lbl}
        for name, data in scenarios:
            try: row[name] = fn(data)
            except: row[name] = "—"
        rows.append(row)
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
