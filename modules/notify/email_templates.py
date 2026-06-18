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
    <table role="presentation" cellpadding="0" cellspacing="0"><tr>
      <td style="border-radius:8px;background:{primary}">
        <a href="{link}" style="display:inline-block;padding:14px 28px;color:#FFFFFF;text-decoration:none;font-weight:bold;font-size:15px">Review &amp; approve →</a>
      </td>
    </tr></table>
    <p style="color:{muted};font-size:12px;margin:18px 0 0">If the button doesn't work, paste this link into your browser:<br>{link}</p>
  </div>
</div>"""


def review_request(project: str, version, link: str, requested_by: str = ""):
    """Build (subject, plain_text, html) for an approval-review request email."""
    by = f" by {requested_by}" if requested_by else ""
    subject = f"Approval requested: {project} (v{version})"
    text = (f"An estimate '{project}' (version {version}) has been submitted for your "
            f"approval{by}.\n\nReview and approve/reject here:\n{link}\n")
    html = _REVIEW_HTML.format(
        text=THEME["text"], navy=THEME["navy"], primary=THEME["primary"],
        muted=THEME["text_muted"], org=ORG_NAME, app=APP_NAME_SHORT,
        project=project, version=version, by=by, link=link,
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
