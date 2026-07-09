"""The review-email key-figures block surfaces the multi-skill extras (one-time transition
cost + roster headcount) when the saved summary carries them, and omits them otherwise."""
from modules.notify.email_templates import _figures_blocks


def test_figures_blocks_includes_transition_and_roster():
    summary = {"selling_price": 1_000_000, "delivery_cost": 700_000, "total_fte": 12.0,
               "transition_selling": 500_000, "transition_cost": 300_000, "roster_seats": 18}
    text, html = _figures_blocks(summary)
    assert "Transition Cost (one-time)" in text and "Transition Cost (one-time)" in html
    assert "500,000" in text                       # selling preferred over cost when present
    assert "Roster Headcount (seats)" in text and "18" in text


def test_figures_blocks_omits_extras_when_absent():
    summary = {"selling_price": 1_000_000, "delivery_cost": 700_000, "total_fte": 12.0}
    text, html = _figures_blocks(summary)
    assert "Transition Cost" not in text
    assert "Roster Headcount" not in text
