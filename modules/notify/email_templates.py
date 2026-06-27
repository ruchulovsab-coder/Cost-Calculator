"""
Email content templates — kept separate from the mailer (email_sender.py) so the
brand/content lives in one place and the transport layer just fills the slots.

Each builder returns (subject, plain_text, html). The HTML is a single-column,
inline-styled layout (Gmail/Outlook strip <style> blocks) with a ≥44px-tall
brand-teal CTA button and a raw-link fallback.
"""
from config.settings import ORG_NAME, APP_NAME_SHORT, THEME

# Inline-styled, table-based button works across Outlook/Gmail. {slots} are filled
# by .format(); the only braces in the template are the placeholders themselves.
_REVIEW_HTML = """\
<div style="font-family:Arial,Helvetica,sans-serif;max-width:600px;margin:0 auto;color:{text};font-size:15px;line-height:1.5">
  <div style="background:{navy};color:#FFFFFF;padding:16px 20px;border-radius:8px 8px 0 0;font-weight:bold;font-size:16px">
    {org} · {app}
  </div>
  <div style="background:#FFFFFF;padding:20px;border:1px solid #E0ECEC;border-top:none;border-radius:0 0 8px 8px">
    <p style="margin:0 0 16px">An estimate <b>{project} — v{version}</b> has been submitted for your approval{by}. Please review and approve it or send it back for rework.</p>
    {figures}
    <table role="presentation" cellpadding="0" cellspacing="0"><tr>
      <td style="border-radius:8px;background:{primary}">
        <a href="{link}" style="display:inline-block;padding:14px 28px;color:#FFFFFF;text-decoration:none;font-weight:bold;font-size:15px">Review &amp; approve →</a>
      </td>
    </tr></table>
    <p style="color:{muted};font-size:12px;margin:18px 0 0">If the button doesn't work, paste this link into your browser:<br>{link}</p>
  </div>
</div>"""


def _figures_blocks(summary):
    """(plain_text, html) headline figures for the review email, from a saved
    estimate's summary. Figures are the INR base values (gross margin is currency-
    independent). Returns ('','') when there's nothing usable to show."""
    if not summary:
        return "", ""
    try:
        sp = float(summary.get("selling_price", 0) or 0)
        dc = float(summary.get("delivery_cost", 0) or 0)
        fte = float(summary.get("total_fte", 0) or 0)
    except (TypeError, ValueError):
        return "", ""
    if sp <= 0 and dc <= 0:
        return "", ""
    margin = (1 - dc / sp) * 100 if sp > 0 else 0.0
    rows = [
        ("Monthly Selling Price", f"INR {sp:,.0f}"),
        ("Monthly Delivery Cost", f"INR {dc:,.0f}"),
        ("Gross Margin", f"{margin:.1f}%"),
        ("Total FTE", f"{fte:.1f}"),
    ]
    text = "\nKey figures (INR):\n" + "\n".join(f"  - {k}: {v}" for k, v in rows) + "\n"
    cells = "".join(
        f'<tr><td style="padding:6px 10px;border-bottom:1px solid #E0ECEC;color:{THEME["text_muted"]}">{k}</td>'
        f'<td style="padding:6px 10px;border-bottom:1px solid #E0ECEC;text-align:right;font-weight:bold">{v}</td></tr>'
        for k, v in rows)
    html = (f'<table role="presentation" cellpadding="0" cellspacing="0" '
            f'style="width:100%;border-collapse:collapse;margin:0 0 16px;font-size:14px">'
            f'<tr><td colspan="2" style="padding:0 0 6px;font-weight:bold;color:{THEME["navy"]}">'
            f'Key figures (INR)</td></tr>{cells}</table>')
    return text, html


def review_request(project: str, version, link: str, requested_by: str = "", summary=None):
    """Build (subject, plain_text, html) for an approval-review request email.
    `summary` is the saved estimate's summary dict (selling_price/delivery_cost/
    total_fte) so the reviewer sees the headline figures before opening the link."""
    by = f" by {requested_by}" if requested_by else ""
    subject = f"Approval requested: {project} (v{version})"
    fig_text, fig_html = _figures_blocks(summary)
    text = (f"An estimate '{project}' (version {version}) has been submitted for your "
            f"approval{by}.\n{fig_text}\nReview and approve/reject here:\n{link}\n")
    html = _REVIEW_HTML.format(
        text=THEME["text"], navy=THEME["navy"], primary=THEME["primary"],
        muted=THEME["text_muted"], org=ORG_NAME, app=APP_NAME_SHORT,
        project=project, version=version, by=by, link=link, figures=fig_html,
    )
    return subject, text, html


# Orphan clean-up: ask a recipient to confirm deletion of abandoned draft estimates.
_ORPHAN_HTML = """\
<div style="font-family:Arial,Helvetica,sans-serif;max-width:600px;margin:0 auto;color:{text};font-size:15px;line-height:1.5">
  <div style="background:{navy};color:#FFFFFF;padding:16px 20px;border-radius:8px 8px 0 0;font-weight:bold;font-size:16px">
    {org} · {app}
  </div>
  <div style="background:#FFFFFF;padding:20px;border:1px solid #E0ECEC;border-top:none;border-radius:0 0 8px 8px">
    <p style="margin:0 0 16px">{who} has flagged <b>{count} abandoned draft estimate(s)</b> for clean-up. Please review them and confirm deletion — the items are removed only when you approve.</p>
    <table role="presentation" cellpadding="0" cellspacing="0"><tr>
      <td style="border-radius:8px;background:{primary}">
        <a href="{link}" style="display:inline-block;padding:14px 28px;color:#FFFFFF;text-decoration:none;font-weight:bold;font-size:15px">Review &amp; delete →</a>
      </td>
    </tr></table>
    <p style="color:{muted};font-size:12px;margin:18px 0 0">If the button doesn't work, paste this link into your browser:<br>{link}</p>
  </div>
</div>"""


def orphan_review_request(requested_by: str, count, link: str):
    """Build (subject, plain_text, html) for an orphan-cleanup deletion request."""
    who = requested_by or "A colleague"
    subject = f"Draft clean-up: {count} abandoned estimate(s) to review"
    text = (f"{who} has flagged {count} abandoned draft estimate(s) for clean-up.\n\n"
            f"Review and confirm deletion here:\n{link}\n")
    html = _ORPHAN_HTML.format(
        text=THEME["text"], navy=THEME["navy"], primary=THEME["primary"],
        muted=THEME["text_muted"], org=ORG_NAME, app=APP_NAME_SHORT,
        who=who, count=count, link=link,
    )
    return subject, text, html
