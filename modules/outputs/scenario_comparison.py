"""Scenario save / load / compare.

Scenarios live in-session (st.session_state["saved_scenarios"]) so several can be
saved and compared without manual file juggling. Download/upload JSON is still
available for sharing across machines. The comparison view recomputes each
scenario's full model so the figures reflect the actual pipeline, not stale inputs.
"""
import json
import streamlit as st
import pandas as pd

try:
    import plotly.express as px
    PLOTLY_OK = True
except ImportError:
    PLOTLY_OK = False

from modules.inputs.steps_1_2 import section_hdr, callout
from utils.formatters import fmt_currency, fmt_hours


def render_scenario_sidebar():
    st.sidebar.divider()
    st.sidebar.markdown("### 💾 Scenarios")

    saved = st.session_state.setdefault("saved_scenarios", [])

    with st.sidebar.expander(f"Save Scenario ({len(saved)} saved)"):
        name = st.text_input("Scenario Name", key="scen_name")
        desc = st.text_area("Description", key="scen_desc", height=50)
        if st.button("💾 Save to session", key="btn_save_scen"):
            if not name.strip():
                st.error("Enter a name.")
            else:
                from modules.state.session_manager import save_scenario_to_session
                save_scenario_to_session(name.strip(), desc.strip())
                st.success(f"Saved: {name}")
                st.rerun()

        # Per-scenario download + delete
        for i, s in enumerate(list(saved)):
            meta = s.get("meta", {})
            c1, c2 = st.columns([3, 1])
            c1.download_button(
                f"⬇️ {meta.get('name', 'scenario')}",
                data=json.dumps(s, indent=2, default=str),
                file_name=f"{meta.get('name','scenario').replace(' ','_')}_{meta.get('date','')}.json",
                mime="application/json", key=f"dl_scen_{i}", use_container_width=True,
            )
            if c2.button("🗑️", key=f"del_scen_{i}"):
                saved.pop(i)
                st.rerun()

    with st.sidebar.expander("Load Scenario (from file)"):
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


def render_saved_calc_sidebar():
    """Cloud-persisted, versioned calculations (shared team repository)."""
    from modules.state.estimate_store import store_configured
    st.sidebar.divider()
    st.sidebar.markdown("### 📁 Saved Calculations")

    if not store_configured():
        st.sidebar.caption("Cloud storage not configured — use **Scenarios** above to "
                           "download/upload JSON instead.")
        return

    from modules.state.estimate_store import save_estimate, list_estimates, load_estimate
    from modules.state.session_manager import (
        serialize_inputs, build_estimate_summary, run_model, load_scenario,
    )
    sb = st.sidebar  # render inline (no expanders — they had unreadable white-on-white headers)

    # ── Save ──────────────────────────────────────────────────
    sb.markdown("**💾 Save current calculation**")
    proj = (st.session_state.get("project_name") or "").strip()
    if not proj:
        sb.caption("Set a Customer / RFP name on Step 1 first.")
    label = sb.text_input("Version note (optional)", key="est_label", placeholder="e.g. After negotiation")
    if sb.button("💾 Save version", key="btn_save_est", disabled=not proj,
                 use_container_width=True, type="primary"):
        try:
            model = run_model()
            meta = save_estimate(
                proj, label.strip(), (st.session_state.get("prepared_by") or "").strip(),
                serialize_inputs(), build_estimate_summary(model),
            )
            list_estimates.clear()
            st.session_state["_current_estimate_ref"] = {
                "slug": meta["project_slug"], "version": meta["version"],
                "project": meta["project"], "blob": meta.get("_blob")}
            sb.success(f"Saved {meta['project']} — v{meta['version']}")
        except Exception as e:
            sb.error(f"Save failed: {e}")

    # ── Open ──────────────────────────────────────────────────
    sb.markdown("**📂 Open saved calculation**")
    if sb.button("🔄 Refresh list", key="btn_refresh_est", use_container_width=True, type="primary"):
        list_estimates.clear()
        st.rerun()
    try:
        items = list_estimates()
    except Exception as e:
        sb.error(f"Could not list: {type(e).__name__}: {e}")
        items = []
    if not items:
        sb.caption("No saved calculations yet.")
    else:
        projects = sorted({(it["project"] or it["slug"]) for it in items})
        sel_proj = sb.selectbox("Project", projects, key="est_sel_proj")
        versions = sorted(
            [it for it in items if (it["project"] or it["slug"]) == sel_proj],
            key=lambda x: x["version"], reverse=True)

        def _fmt(it):
            ts = (it.get("saved_at") or "")
            if "T" in ts:
                d, _, t = ts.partition("T")
                ts = f"{d} {t.replace('-', ':')[:5]} UTC"
            return f"v{it['version']} · {ts}"

        sel = sb.selectbox("Version (newest first)", versions, format_func=_fmt, key="est_sel_ver")
        if sb.button("📥 Load this version", key="btn_load_est", use_container_width=True, type="primary"):
            try:
                data = load_estimate(sel["blob"])
                load_scenario({"inputs": data.get("inputs", {})})
                st.session_state["_current_estimate_ref"] = {
                    "slug": sel["slug"], "version": sel["version"],
                    "project": (data.get("meta", {}) or {}).get("project", sel["project"]),
                    "blob": sel["blob"]}
                sb.success(f"Loaded {sel_proj} v{sel['version']}")
                st.rerun()
            except Exception as e:
                sb.error(f"Load failed: {e}")


def _safe_model(inputs):
    from modules.state.session_manager import model_from_inputs
    try:
        return model_from_inputs(inputs)
    except Exception:
        return None


def render_comparison():
    section_hdr("📊 Scenario Comparison")

    saved = st.session_state.get("saved_scenarios", [])
    pool = {}  # label -> inputs dict

    # In-session scenarios
    if saved:
        names = [s["meta"]["name"] for s in saved]
        chosen = st.multiselect("Compare saved scenarios", names, default=names, key="cmp_saved")
        for s in saved:
            if s["meta"]["name"] in chosen:
                pool[s["meta"]["name"]] = s.get("inputs", {})
    else:
        callout("No scenarios saved yet. Use **💾 Scenarios → Save to session** in the sidebar, "
                "or upload JSON files below.", "info")

    # External uploads
    with st.expander("➕ Add scenarios from JSON files"):
        ups = st.file_uploader("Upload scenario JSON(s)", type=["json"],
                               accept_multiple_files=True, key="cmp_uploads")
        for up in ups or []:
            try:
                data = json.load(up)
                pool[data["meta"]["name"] + " (file)"] = data.get("inputs", {})
            except Exception as e:
                st.error(f"{getattr(up, 'name', 'file')}: {e}")

    if len(pool) < 2:
        callout("Select or upload at least 2 scenarios to compare.", "warning")
        return

    # Recompute each scenario's model
    models = {}
    for label, inputs in pool.items():
        m = _safe_model(inputs)
        if m is not None:
            models[label] = (inputs, m)

    if len(models) < 2:
        callout("Could not compute enough scenarios to compare.", "error")
        return

    labels = list(models.keys())
    rows = [
        ("Coverage Model",        lambda i, m: i.get("coverage_model", "—") or "—"),
        ("Delivery Location",     lambda i, m: f"{i.get('delivery_country','—')}"
                                               + (f" / {i.get('delivery_location')}" if i.get('delivery_location') else "")),
        ("Contingency %",         lambda i, m: f"{float(i.get('contingency_pct',0) or 0):.1f}%"),
        ("Total Effort",          lambda i, m: fmt_hours(m["total_effort"])),
        ("Total FTE",             lambda i, m: f"{m['total_fte']:.1f}"),
        ("Gross Margin %",        lambda i, m: f"{m['price_result']['margin_pct']:.1f}%"),
        ("Delivery Cost (INR)",   lambda i, m: fmt_currency(m["cost_result"]["total_delivery_cost"])),
        ("Selling Price (INR)",   lambda i, m: fmt_currency(m["price_result"]["selling_price"])),
    ]
    table = []
    for metric, fn in rows:
        r = {"Metric": metric}
        for lbl in labels:
            inputs, m = models[lbl]
            try:
                r[lbl] = fn(inputs, m)
            except Exception:
                r[lbl] = "—"
        table.append(r)
    st.dataframe(pd.DataFrame(table), use_container_width=True, hide_index=True)

    # Visual price comparison
    if PLOTLY_OK:
        prices = {lbl: models[lbl][1]["price_result"]["selling_price"] for lbl in labels}
        fig = px.bar(x=list(prices.keys()), y=list(prices.values()),
                     text=[f"₹{v:,.0f}" for v in prices.values()],
                     color_discrete_sequence=["#00C4B4"])
        fig.update_layout(height=340, margin=dict(l=0, r=0, t=20, b=10),
                          xaxis_title="", yaxis_title="Monthly Selling Price (INR)", showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
