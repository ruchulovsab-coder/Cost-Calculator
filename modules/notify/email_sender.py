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


def _email_client():
    """Build an ACS EmailClient from a connection string or managed identity."""
    from azure.communication.email import EmailClient
    conn = os.environ.get("ACS_CONNECTION_STRING", "").strip()
    if conn:
        return EmailClient.from_connection_string(conn)
    from azure.identity import DefaultAzureCredential
    endpoint = os.environ["ACS_ENDPOINT"].strip()
    return EmailClient(endpoint, DefaultAzureCredential(exclude_interactive_browser_credential=True))


def _send(recipient_email: str, subject: str, text: str, html: str, attachments=None):
    """Dispatch one email. `attachments` is a list of {name, content_type, bytes}.
    Raises on failure; returns the send result."""
    message = {
        "senderAddress": os.environ["ACS_SENDER"].strip(),
        "recipients": {"to": [{"address": recipient_email}]},
        "content": {"subject": subject, "plainText": text, "html": html},
    }
    if attachments:
        import base64
        message["attachments"] = [
            {"name": a["name"], "contentType": a["content_type"],
             "contentInBase64": base64.b64encode(a["bytes"]).decode("ascii")}
            for a in attachments if a.get("bytes")
        ]
    return _email_client().begin_send(message).result()


def send_review_email(reviewer_email: str, project: str, version, link: str,
                      requested_by: str = "", summary=None, body_html: str = "",
                      attachments=None):
    """Send the approval-review email. Raises on failure; returns the send result.
    `summary` → plain-text headline figures; `body_html` → the rich dashboard summary
    in the HTML body; `attachments` → e.g. the editable Excel model workbook."""
    from modules.notify.email_templates import review_request
    subject, text, html = review_request(project, version, link, requested_by, summary, body_html)
    return _send(reviewer_email, subject, text, html, attachments)


def send_orphan_review_email(recipient_email: str, requested_by: str, count, link: str):
    """Send the orphan-cleanup deletion-request email. Raises on failure."""
    from modules.notify.email_templates import orphan_review_request
    subject, text, html = orphan_review_request(requested_by, count, link)
    return _send(recipient_email, subject, text, html)
