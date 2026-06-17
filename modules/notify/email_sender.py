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

    from modules.notify.email_templates import review_request
    subject, text, html = review_request(project, version, link, requested_by)

    message = {
        "senderAddress": sender,
        "recipients": {"to": [{"address": reviewer_email}]},
        "content": {"subject": subject, "plainText": text, "html": html},
    }
    poller = client.begin_send(message)
    return poller.result()
