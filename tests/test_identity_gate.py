"""Unit tests for the Nagarro-email gate validation (pure)."""
from modules.inputs.identity_gate import valid_nagarro_email


def test_accepts_nagarro_trimmed_and_lowercased():
    assert valid_nagarro_email("jane.doe@nagarro.com")
    assert valid_nagarro_email("  Jane.Doe@Nagarro.Com  ")
    assert valid_nagarro_email("a1@nagarro.com")
    assert valid_nagarro_email("first_last+tag@nagarro.com")


def test_rejects_non_nagarro():
    for bad in ["jane@gmail.com", "jane@nagarro.co", "jane@sub.nagarro.com",
                "jane@nagarro.com.evil.com", "jane@nagarrocom", "@nagarro.com",
                "nagarro.com", "jane@nagarro.com x", "", None]:
        assert not valid_nagarro_email(bad), bad
