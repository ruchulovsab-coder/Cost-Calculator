"""Display formatters."""
from config.settings import CURRENCY_SYMBOLS


def fmt_currency(value: float, currency: str = "INR", decimals: int = 0) -> str:
    sym = CURRENCY_SYMBOLS.get(currency, currency + " ")
    return f"{sym}{value:,.{decimals}f}"


def fmt_number(value: float, decimals: int = 1) -> str:
    return f"{value:,.{decimals}f}"


def fmt_pct(value: float, decimals: int = 1) -> str:
    return f"{value:.{decimals}f}%"


def fmt_hours(value: float) -> str:
    return f"{value:,.1f} hrs"
