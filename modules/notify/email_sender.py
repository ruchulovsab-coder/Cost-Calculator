"""
Send approval emails via Azure Communication Services (Email), authenticated with the
Container App's managed identity (no connection string / key). Configured via env:

    ACS_ENDPOINT   https://<acs-resource>.communication.azure.com
    ACS_SENDER     DoNotReply@<your-domain>   (the verified sender address)

When unset, email_configured() is False and the UI falls back to showing the link.
"""
import os


def email_configured() -> bool:
    return bool(os.environ.get("ACS_ENDPOINT", "").strip()
                and os.environ.get("ACS_SENDER", "").strip())


def send_review_email(reviewer_email: str, project: str, version, link: str, requested_by: str = ""):
    """Send the approval-review email. Raises on failure; returns the send result."""
    from azure.communication.email import EmailClient
    from azure.identity import DefaultAzureCredential

    endpoint = os.environ["ACS_ENDPOINT"].strip()
    sender = os.environ["ACS_SENDER"].strip()
    client = EmailClient(endpoint, DefaultAzureCredential(exclude_interactive_browser_credential=True))

    by = f" by {requested_by}" if requested_by else ""
    subject = f"Approval requested: {project} (v{version})"
    text = (f"An estimate '{project}' (version {version}) has been submitted for your "
            f"approval{by}.\n\nReview and approve/reject here:\n{link}\n")
    html = (f"<p>An estimate <b>{project} — v{version}</b> has been submitted for your "
            f"approval{by}.</p>"
            f"<p><a href=\"{link}\">Open the estimate to review &amp; approve / reject</a></p>"
            f"<p style='color:#666;font-size:12px'>If the button doesn't work, paste this link:<br>{link}</p>")

    message = {
        "senderAddress": sender,
        "recipients": {"to": [{"address": reviewer_email}]},
        "content": {"subject": subject, "plainText": text, "html": html},
    }
    poller = client.begin_send(message)
    return poller.result()
