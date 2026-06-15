"""Input validators."""
import pandas as pd
from typing import Tuple

REQUIRED_RATE_CARD_COLS = {"country", "location", "genus", "hourly rate", "rate currency"}

VALID_ISO_CURRENCIES = {
    "AED","AFN","ALL","AMD","ANG","AOA","ARS","AUD","AWG","AZN","BAM","BBD","BDT","BGN",
    "BHD","BIF","BMD","BND","BOB","BRL","BSD","BTN","BWP","BYN","BZD","CAD","CDF","CHF",
    "CLP","CNY","COP","CRC","CUP","CVE","CZK","DJF","DKK","DOP","DZD","EGP","ERN","ETB",
    "EUR","FJD","FKP","GBP","GEL","GHS","GIP","GMD","GNF","GTQ","GYD","HKD","HNL","HRK",
    "HTG","HUF","IDR","ILS","INR","IQD","IRR","ISK","JMD","JOD","JPY","KES","KGS","KHR",
    "KMF","KPW","KRW","KWD","KYD","KZT","LAK","LBP","LKR","LRD","LSL","LYD","MAD","MDL",
    "MGA","MKD","MMK","MNT","MOP","MRU","MUR","MVR","MWK","MXN","MYR","MZN","NAD","NGN",
    "NIO","NOK","NPR","NZD","OMR","PAB","PEN","PGK","PHP","PKR","PLN","PYG","QAR","RON",
    "RSD","RUB","RWF","SAR","SBD","SCR","SDG","SEK","SGD","SHP","SLL","SOS","SRD","STN",
    "SYP","SZL","THB","TJS","TMT","TND","TOP","TRY","TTD","TWD","TZS","UAH","UGX","USD",
    "UYU","UZS","VES","VND","VUV","WST","XAF","XCD","XOF","XPF","YER","ZAR","ZMW","ZWL",
}


def validate_rate_card(df: pd.DataFrame) -> Tuple[bool, str]:
    actual = {c.lower().strip() for c in df.columns}
    missing = REQUIRED_RATE_CARD_COLS - actual
    if missing:
        return False, f"Missing required columns: {', '.join(sorted(missing))}"

    df = df.copy()
    df.columns = [c.lower().strip() for c in df.columns]

    for col in REQUIRED_RATE_CARD_COLS:
        blank = df[df[col].isna() | (df[col].astype(str).str.strip() == "")].index.tolist()
        if blank:
            return False, f"Column '{col}' has blank values at rows: {[r+2 for r in blank[:5]]}"

    rates = pd.to_numeric(df["hourly rate"], errors="coerce")
    bad = df[rates.isna() | (rates <= 0)].index.tolist()
    if bad:
        return False, f"'Hourly Rate' has non-numeric or zero/negative values at rows: {[r+2 for r in bad[:5]]}"

    invalid_curr = df[~df["rate currency"].str.upper().str.strip().isin(VALID_ISO_CURRENCIES)]["rate currency"].unique()
    if len(invalid_curr) > 0:
        return False, f"Invalid ISO 4217 currency codes found: {list(invalid_curr)}"

    return True, (f"✅ Rate card loaded — {len(df)} records across "
                  f"{df['country'].nunique()} countries, {df['location'].nunique()} locations.")
