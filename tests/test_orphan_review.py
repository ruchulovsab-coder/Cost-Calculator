"""Unit tests for the pure orphan-deletion review logic (no Azure required)."""
from modules.state import orphan_review as OR
from modules.notify.email_templates import orphan_review_request

BLOBS = ["__orphans__/acme__2026-06-01T10-00-00Z.json",
         "__orphans__/acme__2026-06-02T10-00-00Z.json"]


def test_blob_name():
    assert OR.review_blob_name("TKN") == "__orphan_reviews__/TKN.json"


def test_build_defaults_pending():
    rec = OR.build_orphan_review("owner@x.com", BLOBS, "Jane", token="TKN")
    assert rec["status"] == OR.STATUS_PENDING
    assert rec["token"] == "TKN"
    assert rec["recipient"] == "owner@x.com"
    assert rec["orphan_blobs"] == BLOBS
    assert rec["requested_by"] == "Jane"
    assert rec["deleted_blobs"] == [] and rec["decided_at"] == ""


def test_build_generates_token_when_absent():
    a = OR.build_orphan_review("o", BLOBS, "j")
    b = OR.build_orphan_review("o", BLOBS, "j")
    assert a["token"] and b["token"] and a["token"] != b["token"]


def test_chosen_in_scope_filters_unauthorised():
    rec = OR.build_orphan_review("o", BLOBS, "j", token="T")
    chosen = OR.chosen_in_scope(rec, [BLOBS[0], "__orphans__/evil.json"])
    assert chosen == [BLOBS[0]]


def test_apply_delete_bad_token():
    rec = OR.build_orphan_review("o", BLOBS, "j", token="T")
    updated, err = OR.apply_delete(rec, "WRONG", BLOBS)
    assert updated is None and "Invalid" in err


def test_apply_delete_requires_in_scope_selection():
    rec = OR.build_orphan_review("o", BLOBS, "j", token="T")
    updated, err = OR.apply_delete(rec, "T", ["__orphans__/not-in-request.json"])
    assert updated is None and "at least one" in err


def test_apply_delete_partial_then_done():
    rec = OR.build_orphan_review("o", BLOBS, "j", token="T")
    partial, err = OR.apply_delete(rec, "T", [BLOBS[0]])
    assert err is None
    assert partial["status"] == OR.STATUS_PARTIAL
    assert partial["deleted_blobs"] == [BLOBS[0]] and partial["decided_at"]

    done, err = OR.apply_delete(partial, "T", [BLOBS[1]])
    assert err is None
    assert done["status"] == OR.STATUS_DONE
    assert set(done["deleted_blobs"]) == set(BLOBS)


def test_apply_delete_no_record():
    updated, err = OR.apply_delete(None, "T", BLOBS)
    assert updated is None and err


def test_email_template_contains_link_and_count():
    subject, text, html = orphan_review_request("Jane", 3, "https://app/?orphan=TKN")
    assert "3" in subject
    assert "https://app/?orphan=TKN" in text
    assert "https://app/?orphan=TKN" in html
    assert "Jane" in html
