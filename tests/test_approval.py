"""Unit tests for the pure approval-workflow logic."""
from modules.state import approval_store as A


def test_blob_name_and_token():
    assert A.approval_blob_name("acme-rfp", 3) == "__approvals__/acme-rfp__v3.json"
    t1, t2 = A.new_token(), A.new_token()
    assert t1 and t2 and t1 != t2 and len(t1) >= 20


def test_build_request_defaults_pending():
    rec = A.build_request("acme", 1, "Acme", "acme/x__v1.json", "rev@x.com", "me", token="TKN")
    assert rec["status"] == A.STATUS_PENDING
    assert rec["token"] == "TKN"
    assert rec["version"] == 1 and rec["project"] == "Acme"
    assert rec["reviewer_email"] == "rev@x.com"
    assert rec["comment"] == "" and rec["decided_at"] == ""


def test_apply_decision_approve():
    rec = A.build_request("a", 1, "A", "b", "r", "u", token="T")
    updated, err = A.apply_decision(rec, "T", True, "")
    assert err is None
    assert updated["status"] == A.STATUS_APPROVED and updated["decided_at"]


def test_apply_decision_reject_requires_comment():
    rec = A.build_request("a", 1, "A", "b", "r", "u", token="T")
    updated, err = A.apply_decision(rec, "T", False, "")
    assert updated is None and "comment" in err.lower()
    updated, err = A.apply_decision(rec, "T", False, "needs rework")
    assert err is None and updated["status"] == A.STATUS_REJECTED and updated["comment"] == "needs rework"


def test_apply_decision_bad_token():
    rec = A.build_request("a", 1, "A", "b", "r", "u", token="T")
    updated, err = A.apply_decision(rec, "WRONG", True, "")
    assert updated is None and "invalid" in err.lower()


def test_apply_decision_already_decided():
    rec = A.build_request("a", 1, "A", "b", "r", "u", token="T")
    rec["status"] = A.STATUS_APPROVED
    updated, err = A.apply_decision(rec, "T", True, "")
    assert err and "already" in err.lower()


def test_apply_decision_no_record():
    updated, err = A.apply_decision(None, "T", True, "")
    assert updated is None and err
