"""Share-invitation email template — role-appropriate wording + link presence."""
from modules.notify.email_templates import share_invite

LINK = "https://estimator.example/?sh=acme&v=3&k=TOKEN"


def test_editor_invite_mentions_edit_and_new_version():
    subject, text, html = share_invite("Acme RFP", 3, "editor", LINK, "me@nagarro.com")
    assert "Acme RFP" in subject and "v3" in subject
    assert LINK in text and LINK in html
    assert "new version" in text.lower()
    assert "edit" in html.lower()


def test_viewer_invite_is_read_only():
    subject, text, html = share_invite("Acme RFP", 3, "viewer", LINK, "me@nagarro.com")
    assert LINK in text and LINK in html
    assert "read-only" in text.lower() or "read-only" in html.lower()
    # A viewer must not get the editor-only "saved as a new version" promise.
    assert "new version" not in text.lower()


def test_unknown_role_treated_as_viewer():
    _s, text, _h = share_invite("Acme", 1, "nonsense", LINK)
    assert "read-only" in text.lower()


def test_shared_by_fallback():
    subject, _t, _h = share_invite("Acme", 1, "viewer", LINK, "")
    assert "colleague" in subject.lower()
