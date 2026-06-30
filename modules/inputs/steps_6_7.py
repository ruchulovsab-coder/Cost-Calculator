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

    # ── Coverage model is chosen on Step 1; here we use it ────
    model = st.session_state.get("coverage_model") or "8×5"
    custom_hpd = st.session_state.get("custom_hours_per_day", 8)
    custom_dpw = st.session_state.get("custom_days_per_week", 5)
    multiplier = calc_coverage_multiplier(model, custom_hpd, custom_dpw)
    st.session_state["_coverage_multiplier"] = multiplier

    callout(
        f"📊 Coverage model <strong>{model}</strong> → multiplier "
        f"<strong>{multiplier:.2f}×</strong>, applied to <strong>L1 and L2</strong> FTE only "
        f"(L3 / Architect / SDM are standard-hours). "
        f"Change the coverage model on <strong>Step 1</strong>.",
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
            key="monthly_working_hours_w",
            help="Total available hours per FTE per month. Standard: 160 hrs (8 hrs × 20 working days).",
        )
        st.session_state["monthly_working_hours"] = monthly_hrs
    with pc2:
        utilisation = st.number_input(
            "**Productive Utilisation (%)** *(required)*",
            min_value=10.0, max_value=100.0, step=1.0,
            value=float(st.session_state.get("productive_utilisation") or 75.0),
            key="productive_utilisation_w",
            help="% of working hours spent on billable delivery. Typical: 75%.",
        )
        st.session_state["productive_utilisation"] = utilisation

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
    page_header(7, "Role-to-Grade Mapping",
                "Map each active role to a Genus grade from the rate card (loaded on Step 1).")

    auto_load_rate_card()
    df = st.session_state.get("rate_card_df")
    if df is None:
        callout("No rate card loaded yet — add it on <strong>Step 1</strong> "
                "(upload a file, or it auto-loads from the cloud).", "warning")
        return False

    # ── Delivery Location (selected on Step 1) ────────────────
    section_hdr("📍 Delivery Location")
    from modules.calculations.engine import filter_rate_card

    country = st.session_state.get("delivery_country")
    location = st.session_state.get("delivery_location")
    if not country:
        # default to India / first country if it hasn't been chosen on Step 1 yet
        countries = sorted(df["country"].dropna().astype(str).str.strip().unique().tolist())
        country = next((c for c in countries if "india" in c.lower()),
                       countries[0] if countries else None)
        st.session_state["delivery_country"] = country

    scoped = filter_rate_card(df, country, location)
    filtered = scoped.drop_duplicates(subset=["genus"], keep="first")
    scope_label = f"{country or 'All'}" + (f" / {location}" if location else "")
    st.info(f"**{len(filtered)} grade(s)** for {scope_label} — set the location and view the "
            "rate card on **Step 1**.")
    st.session_state["_filtered_rate_card"] = filtered

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


# ── Shared helpers (rate card load + delivery-location selector on Step 1) ──────

def _store_rate_card(data: bytes, source: str):
    """Parse + validate raw .xlsx bytes and store the cleaned df. Returns (ok, msg)."""
    df_raw = _parse_rate_card(data)
    ok, msg = validate_rate_card(df_raw)
    if not ok:
        return False, msg
    df_clean = df_raw.copy()
    df_clean.columns = [c.lower().strip() for c in df_clean.columns]
    df_clean["hourly rate"] = pd.to_numeric(df_clean["hourly rate"], errors="coerce")
    st.session_state.rate_card_df = df_clean
    st.session_state["_rate_card_source"] = source
    return True, msg


def auto_load_rate_card():
    """Load the rate card from Azure Blob if configured and none is loaded yet.
    Safe to call anywhere (e.g. Step 1) so the delivery-location options populate."""
    if st.session_state.get("rate_card_df") is not None:
        return
    from modules.inputs.rate_card_source import blob_configured, fetch_rate_card_bytes
    if not blob_configured():
        return
    try:
        data = fetch_rate_card_bytes()
        if data:
            _store_rate_card(data, "cloud")
    except Exception:
        pass


def render_rate_card_source():
    """Rate-card upload + cloud auto-load + status (relocated to Step 1)."""
    from modules.inputs.rate_card_source import blob_configured
    section_hdr("📂 Rate Card")
    callout("Required Excel columns: <strong>Country, Location, Genus, Hourly Rate, Rate Currency</strong>. "
            "Hourly Rate must be numeric and > 0.", "info")
    if blob_configured():
        bc1, bc2 = st.columns([4, 1])
        bc1.caption("Centrally managed in **Azure Blob Storage** (auto-loaded). "
                    "Upload a file to override for this session.")
        if bc2.button("🔄 Reload from cloud", key="rc_reload"):
            from modules.inputs.rate_card_source import load_rate_card_bytes
            try:
                load_rate_card_bytes.clear()
            except Exception:
                pass
            st.session_state.rate_card_df = None
            st.rerun()
    uploaded = st.file_uploader("Upload Rate Card (.xlsx) — optional override",
                                type=["xlsx"], key="rate_card_upload")
    if uploaded:
        ok, msg = _store_rate_card(uploaded.getvalue(), "upload")
        callout(msg if ok else f"❌ {msg}", "success" if ok else "error")
    auto_load_rate_card()
    df = st.session_state.get("rate_card_df")
    src = st.session_state.get("_rate_card_source")
    if df is not None and src == "cloud":
        st.caption("✅ Rate card loaded from Azure Blob Storage.")
    elif df is not None and src == "upload":
        st.caption("✅ Rate card loaded from your uploaded file.")
    elif df is None and not blob_configured():
        st.caption("Upload a rate card to enable delivery-location and grade mapping.")
    return df is not None


def render_delivery_location():
    """Country/location selectors (relocated to Step 1). Needs a loaded rate card."""
    section_hdr("📍 Delivery Location")
    df = st.session_state.get("rate_card_df")
    if df is None:
        callout("Delivery-location options appear once a rate card is loaded "
                "(auto-loaded from the cloud, or upload one on Step 7).", "info")
        return
    countries = sorted(df["country"].dropna().astype(str).str.strip().unique().tolist())

    def _default_idx(options, current, fb="india"):
        if current and current in options:
            return options.index(current)
        for i, o in enumerate(options):
            if fb in o.lower():
                return i
        return 0

    lc1, lc2 = st.columns(2)
    country = lc1.selectbox("Delivery Country", countries,
                            index=_default_idx(countries, st.session_state.get("delivery_country")),
                            key="dc_select", help="Defaults to India when present in the rate card.")
    st.session_state["delivery_country"] = country
    locs = sorted(df[df["country"].astype(str).str.strip().str.lower() == country.lower()]
                  ["location"].dropna().astype(str).str.strip().unique().tolist())
    loc_options = ["(All locations)"] + locs
    prev = st.session_state.get("delivery_location")
    idx = loc_options.index(prev) if prev in loc_options else 0
    loc_sel = lc2.selectbox("Delivery Location", loc_options, index=idx, key="dl_select")
    location = None if loc_sel == "(All locations)" else loc_sel
    st.session_state["delivery_location"] = location

    # Filtered grades for this location + a collapsible table (default hidden).
    from modules.calculations.engine import filter_rate_card
    scoped = filter_rate_card(df, country, location)
    filtered = scoped.drop_duplicates(subset=["genus"], keep="first")
    st.session_state["_filtered_rate_card"] = filtered
    scope = f"{country or 'All'}" + (f" / {location}" if location else "")
    with st.expander(f"📋 View rate card grades for {scope} ({len(filtered)})", expanded=False):
        st.dataframe(
            filtered[["genus", "hourly rate", "rate currency"]].rename(columns={
                "genus": "Genus", "hourly rate": "Hourly Rate", "rate currency": "Currency"
            }),
            use_container_width=True, hide_index=True,
        )
