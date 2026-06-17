"""
Send approval emails via Azure Communication Services (Email). Two auth options:

  A) Connection string (simplest):   ACS_CONNECTION_STRING + ACS_SENDER
  B) Managed identity (no secret):    ACS_ENDPOINT + ACS_SENDER

ACS_SENDER is the verified sender address, e.g. DoNotReply@<your-domain>.
When unset, email_configured() is False and the UI falls back to showing the link.
"""
import os


def email_configured() -> bool:
    sender = os.environ.get("ACS_SENDER", "").strip()
    conn = os.environ.get("ACS_CONNECTION_STRING", "").strip()
    endpoint = os.environ.get("ACS_ENDPOINT", "").strip()
    return bool(sender and (conn or endpoint))


def send_review_email(reviewer_email: str, project: str, version, link: str, requested_by: str = ""):
    """Send the approval-review email. Raises on failure; returns the send result."""
    from azure.communication.email import EmailClient

    sender = os.environ["ACS_SENDER"].strip()
    conn = os.environ.get("ACS_CONNECTION_STRING", "").strip()
    if conn:
        client = EmailClient.from_connection_string(conn)
    else:
        from azure.identity import DefaultAzureCredential
        endpoint = os.environ["ACS_ENDPOINT"].strip()
        client = EmailClient(endpoint, DefaultAzureCredential(exclude_interactive_browser_credential=True))

    by = f" by {requested_by}" if requested_by else ""
    subject = f"Approval requested: {project} (v{version})"
    text = (f"An estimate '{project}' (version {version}) has been submitted for your "
            f"approval{by}.\n\nReview and approve/reject here:\n{link}\n")
    # Single-column, inline-styled HTML (Gmail/Outlook strip <style> blocks).
    # The CTA is a brand-teal button with a ≥44px tap target.
    html = (
        "<div style=\"font-family:Arial,Helvetica,sans-serif;max-width:600px;margin:0 auto;"
        "color:#0D1B2A;font-size:15px;line-height:1.5\">"
        "<div style=\"background:#0D1B2A;color:#FFFFFF;padding:16px 20px;border-radius:8px 8px 0 0;"
        "font-weight:bold;font-size:16px\">Nagarro · Ops Effort Estimation Tool</div>"
        "<div style=\"background:#FFFFFF;padding:20px;border:1px solid #E0ECEC;border-top:none;"
        "border-radius:0 0 8px 8px\">"
        f"<p style=\"margin:0 0 16px\">An estimate <b>{project} — v{version}</b> has been "
        f"submitted for your approval{by}. Please review and approve or send it back for rework.</p>"
        "<table role=\"presentation\" cellpadding=\"0\" cellspacing=\"0\"><tr><td "
        "style=\"border-radius:8px;background:#00C4B4\">"
        f"<a href=\"{link}\" style=\"display:inline-block;padding:14px 28px;color:#FFFFFF;"
        "text-decoration:none;font-weight:bold;font-size:15px\">Review &amp; approve →</a>"
        "</td></tr></table>"
        f"<p style=\"color:#666666;font-size:12px;margin:18px 0 0\">If the button doesn't work, "
        f"paste this link into your browser:<br>{link}</p>"
        "</div></div>"
    )

    message = {
        "senderAddress": sender,
        "recipients": {"to": [{"address": reviewer_email}]},
        "content": {"subject": subject, "plainText": text, "html": html},
    }
    poller = client.begin_send(message)
    return poller.result()
