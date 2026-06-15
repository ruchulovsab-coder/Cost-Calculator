"""
Step 6 — Coverage Model & FTE Calculation
Step 7 — Rate Card Upload, Delivery Location & Grade Mapping
"""
import io
import streamlit as st
import pandas as pd
from modules.inputs.steps_1_2 import page_header, section_hdr, callout
from modules.calculations.engine import (
    calc_productive_hours, calc_coverage_multiplier, calc_fte, convert_rate_to_inr,
)
from config.settings import ALL_ROLES, COVERAGE_MODELS, GRADE_ELIGIBILITY, DEFAULT_CURRENCIES
from utils.validators import validate_rate_card


@st.cache_data(show_spinner=False)
def _parse_rate_card(file_bytes: bytes) -> pd.DataFrame:
    """Parse an uploaded rate-card .xlsx. Cached on file content so the workbook
    is only read once per distinct upload instead of on every rerun."""
    df_raw = pd.read_excel(io.BytesIO(file_bytes), engine="openpyxl")
    df_raw.columns = [c.strip() for c in df_raw.columns]
    return df_raw


# ── Step 6: Coverage & FTE ─────────────────────────────────────────────────────

def render_step6() -> bool:
    page_header(6, "Coverage Model & FTE Calculation",
                "Define support coverage window and calculate staffing requirements.")

    # ── Coverage Model ────────────────────────────────────────
    section_hdr("📅 Coverage Model")
    model_options = list(COVERAGE_MODELS.keys())

    prev_model = st.session_state.get("coverage_model")
    default_idx = model_options.index(prev_model) if prev_model in model_options else 0

    model = st.radio(
        "**Support Coverage Model** *(required)*",
        options=model_options,
        index=default_idx,
        key="coverage_model",
        horizontal=True,
        help="Coverage window determines shift multiplier for L1 and L2 FTE only.",
    )

    custom_hpd = st.session_state.get("custom_hours_per_day", 8)
    custom_dpw = st.session_state.get("custom_days_per_week", 5)

    if model == "Custom":
        cc1, cc2 = st.columns(2)
        with cc1:
            custom_hpd = st.number_input("Hours Per Day", min_value=1, max_value=24, step=1,
                                         value=int(custom_hpd), key="custom_hours_per_day")
        with cc2:
            custom_dpw = st.number_input("Days Per Week", min_value=1, max_value=7, step=1,
                                         value=int(custom_dpw), key="custom_days_per_week")

    multiplier = calc_coverage_multiplier(model, custom_hpd, custom_dpw)
    st.session_state["_coverage_multiplier"] = multiplier

    callout(
        f"📊 <strong>Coverage Multiplier: {multiplier:.2f}×</strong> — "
        f"Applied to <strong>L1 and L2</strong> FTE only. "
        f"L3, Architect, SDM, SSDM are standard-hours roles.",
        "info",
    )

    # ── Productivity Inputs ───────────────────────────────────
    st.divider()
    section_hdr("⚙️ Productivity & Capacity")
    pc1, pc2 = st.columns(2)
    with pc1:
        monthly_hrs = st.number_input(
            "**Monthly Working Hours Per FTE** *(required)*",
            min_value=1.0, max_value=300.0, step=1.0,
            value=float(st.session_state.get("monthly_working_hours") or 160.0),
            key="monthly_working_hours",
            help="Total available hours per FTE per month. Standard: 160 hrs (8 hrs × 20 working days).",
        )
    with pc2:
        utilisation = st.number_input(
            "**Productive Utilisation (%)** *(required)*",
            min_value=10.0, max_value=100.0, step=1.0,
            value=float(st.session_state.get("productive_utilisation") or 75.0),
            key="productive_utilisation",
            help="% of working hours spent on billable delivery. Typical: 75%.",
        )

    if utilisation < 60:
        callout("⚠️ Utilisation below 60% will significantly increase FTE estimates.", "warning")

    productive_hrs = calc_productive_hours(monthly_hrs, utilisation)
    st.info(f"**Available Productive Hours per FTE = {monthly_hrs:.0f} × {utilisation:.0f}% = {productive_hrs:.1f} hrs/month**")

    # ── FTE Calculation ───────────────────────────────────────
    st.divider()
    section_hdr("👥 FTE Calculation")

    role_hours = st.session_state.get("_role_hours", {r: 0.0 for r in ALL_ROLES})

    if productive_hrs <= 0:
        callout("⚠️ Productive hours must be > 0.", "error")
        return False

    fte_result = calc_fte(role_hours, productive_hrs, multiplier)
    st.session_state["_fte_result"] = fte_result

    total_fte = sum(v["final_fte"] for v in fte_result.values())

    rows_html = ""
    for role in ALL_ROLES:
        r = fte_result[role]
        cov = "✅ Yes" if r["coverage_applied"] else "—"
        rows_html += (
            f"<tr>"
            f"<td>{role}</td>"
            f"<td class='r'>{r['hours']:.1f}</td>"
            f"<td class='r'>{productive_hrs:.1f}</td>"
            f"<td class='r'>{r['raw_fte']:.3f}</td>"
            f"<td style='text-align:center'>{cov}</td>"
            f"<td class='r'><strong>{r['final_fte']:.1f}</strong></td>"
            f"</tr>"
        )
    rows_html += (
        f"<tr class='total-row'>"
        f"<td><strong>TOTAL</strong></td>"
        f"<td class='r'></td><td class='r'></td><td class='r'></td><td></td>"
        f"<td class='r'><strong>{total_fte:.1f}</strong></td>"
        f"</tr>"
    )

    st.markdown(f"""
    <table class="styled-table">
      <thead><tr>
        <th>Role</th>
        <th class="r">Effort Hours</th>
        <th class="r">Productive Hrs</th>
        <th class="r">Raw FTE</th>
        <th style="text-align:center">Cov. Multiplier</th>
        <th class="r">Final FTE ⌈0.5⌉</th>
      </tr></thead>
      <tbody>{rows_html}</tbody>
    </table>""", unsafe_allow_html=True)

    callout(
        "Rounding: Final FTE = CEILING(Raw FTE, 0.5). Minimum 0.5 FTE for any role with hours > 0.",
        "info",
    )
    return True


# ── Step 7: Rate Card & Grade Mapping ─────────────────────────────────────────

def render_step7() -> bool:
    page_header(7, "Rate Card, Location & Grade Mapping",
                "Upload your Genus rate card, select delivery location, and map roles to grades.")

    # ── Upload ────────────────────────────────────────────────
    section_hdr("📂 Rate Card Upload")
    callout(
        "Required Excel columns: <strong>Country, Location, Genus, Hourly Rate, Rate Currency</strong>. "
        "All required. Hourly Rate must be numeric and > 0. "
        "A sample rate card is included in the download package.",
        "info",
    )

    uploaded = st.file_uploader("Upload Rate Card (.xlsx)", type=["xlsx"], key="rate_card_upload")
    if uploaded:
        try:
            df_raw = _parse_rate_card(uploaded.getvalue())
            ok, msg = validate_rate_card(df_raw)
            if ok:
                df_clean = df_raw.copy()
                df_clean.columns = [c.lower().strip() for c in df_clean.columns]
                df_clean["hourly rate"] = pd.to_numeric(df_clean["hourly rate"], errors="coerce")
                st.session_state.rate_card_df = df_clean
                callout(msg, "success")
            else:
                callout(f"❌ {msg}", "error")
                st.session_state.rate_card_df = None
        except Exception as e:
            callout(f"❌ Error reading file: {e}", "error")
            st.session_state.rate_card_df = None

    df = st.session_state.get("rate_card_df")
    if df is None:
        callout("Please upload a valid rate card to continue.", "warning")
        return False

    # ── Delivery Location ─────────────────────────────────────
    st.divider()
    section_hdr("📍 Delivery Location")
    from modules.calculations.engine import filter_rate_card

    countries = sorted(df["country"].dropna().astype(str).str.strip().unique().tolist())

    def _default_idx(options, current, fallback_contains="india"):
        if current and current in options:
            return options.index(current)
        for i, o in enumerate(options):
            if fallback_contains in o.lower():
                return i
        return 0

    lc1, lc2 = st.columns(2)
    with lc1:
        country = st.selectbox(
            "Delivery Country", countries,
            index=_default_idx(countries, st.session_state.get("delivery_country")),
            key="dc_select", help="Defaults to India when present in the rate card.",
        )
    st.session_state["delivery_country"] = country

    locs = sorted(
        df[df["country"].astype(str).str.strip().str.lower() == country.lower()]
        ["location"].dropna().astype(str).str.strip().unique().tolist()
    )
    loc_options = ["(All locations)"] + locs
    with lc2:
        prev_loc = st.session_state.get("delivery_location")
        loc_idx = loc_options.index(prev_loc) if prev_loc in loc_options else 0
        loc_sel = st.selectbox("Delivery Location", loc_options, index=loc_idx, key="dl_select")
    location = None if loc_sel == "(All locations)" else loc_sel
    st.session_state["delivery_location"] = location

    scoped = filter_rate_card(df, country, location)
    filtered = scoped.drop_duplicates(subset=["genus"], keep="first")
    scope_label = f"{country}" + (f" / {location}" if location else "")
    st.info(f"**{len(filtered)} grade(s) found** for {scope_label}")

    st.session_state["_filtered_rate_card"] = filtered

    st.dataframe(
        filtered[["genus", "hourly rate", "rate currency"]].rename(columns={
            "genus": "Genus", "hourly rate": "Hourly Rate", "rate currency": "Currency"
        }),
        use_container_width=True, hide_index=True,
    )

    # ── Grade Mapping ─────────────────────────────────────────
    st.divider()
    section_hdr("🎓 Role-to-Grade Mapping")
    callout(
        "Select the Genus grade for each active role. "
        "Only grades in your rate card for the selected location appear as options. "
        "Roles with zero hours are automatically marked Not Required.",
        "info",
    )

    role_hours  = st.session_state.get("_role_hours", {r: 0.0 for r in ALL_ROLES})
    role_genus  = st.session_state.role_genus
    rates_inr_preview = {}
    available_grades = filtered["genus"].unique().tolist()
    all_mapped = True

    hc0, hc1, hc2, hc3 = st.columns([2, 2.5, 2, 2])
    hc0.markdown("**Role**")
    hc1.markdown("**Genus Grade**")
    hc2.markdown("**Hourly Rate**")
    hc3.markdown("**Status**")

    for role in ALL_ROLES:
        hours = role_hours.get(role, 0.0)
        eligible = GRADE_ELIGIBILITY.get(role, [])
        avail_eligible = [g for g in eligible if g in available_grades]

        c0, c1, c2, c3 = st.columns([2, 2.5, 2, 2])
        c0.markdown(f"**{role}**  \n`{hours:.1f} hrs`")

        if hours <= 0:
            c1.markdown("*Not Required*")
            c2.markdown("—")
            c3.markdown('<span class="pill-ok">—</span>', unsafe_allow_html=True)
            role_genus[role] = None
            continue

        if not avail_eligible:
            c1.error(f"No eligible grades in rate card. Required: {', '.join(eligible)}")
            c2.markdown("—")
            c3.markdown('<span class="pill-err">Missing</span>', unsafe_allow_html=True)
            all_mapped = False
            continue

        prev_g = role_genus.get(role)
        g_idx = avail_eligible.index(prev_g) if prev_g in avail_eligible else 0
        selected = c1.selectbox(
            "grade", options=avail_eligible, index=g_idx,
            key=f"genus_{role}", label_visibility="collapsed",
            help=f"Eligible: {', '.join(eligible)}",
        )
        role_genus[role] = selected

        rate_row = filtered[filtered["genus"] == selected]
        if len(rate_row) > 0:
            rate = float(rate_row.iloc[0]["hourly rate"])
            rates_inr_preview[role] = rate
            row_cur = str(rate_row.iloc[0].get("rate currency", "INR")).upper().strip() or "INR"
            c2.markdown(f"**{row_cur} {rate:,.0f}/hr**")
            c3.markdown('<span class="pill-ok">✓ Mapped</span>', unsafe_allow_html=True)
        else:
            c2.markdown("—")
            c3.markdown('<span class="pill-err">Rate not found</span>', unsafe_allow_html=True)
            all_mapped = False

    st.session_state["_role_rates_raw"] = rates_inr_preview
    if not all_mapped:
        callout("❌ Some active roles are missing grade mappings. Please resolve before continuing.", "error")

    return all_mapped
