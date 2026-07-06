"""Unit tests for the pure share-store logic (per-recipient tokened access)."""
from modules.state import share_store as S


def test_blob_name_and_token():
    assert S.share_blob_name("acme-rfp", 3) == "__shares__/acme-rfp__v3.json"
    t1, t2 = S.new_token(), S.new_token()
    assert t1 and t2 and t1 != t2 and len(t1) >= 20


def test_normalize_role_defaults_to_viewer():
    assert S.normalize_role("editor") == S.ROLE_EDITOR
    assert S.normalize_role("Viewer") == S.ROLE_VIEWER
    assert S.normalize_role("") == S.ROLE_VIEWER
    assert S.normalize_role("nonsense") == S.ROLE_VIEWER
    assert S.normalize_role(None) == S.ROLE_VIEWER


def test_build_share_empty():
    rec = S.build_share("acme", 2, "Acme", "acme/x__v2.json", "me@x.com")
    assert rec["slug"] == "acme" and rec["version"] == 2
    assert rec["project"] == "Acme" and rec["estimate_blob"] == "acme/x__v2.json"
    assert rec["shared_by"] == "me@x.com" and rec["recipients"] == []
    assert rec["created_at"]


def test_add_recipient_creates_with_token_and_role():
    rec = S.build_share("a", 1, "A", "b", "u")
    rec, r = S.add_recipient(rec, "viewer@x.com", "viewer")
    assert r["email"] == "viewer@x.com" and r["role"] == S.ROLE_VIEWER
    assert r["token"] and not r["revoked"] and r["last_opened_at"] == ""
    assert len(rec["recipients"]) == 1


def test_add_recipient_reinvite_updates_role_keeps_token():
    rec = S.build_share("a", 1, "A", "b", "u")
    rec, r1 = S.add_recipient(rec, "x@x.com", "viewer")
    rec, r2 = S.add_recipient(rec, "X@X.com", "editor")  # same email, different case
    assert len(rec["recipients"]) == 1            # no duplicate
    assert r2["token"] == r1["token"]             # original token preserved
    assert r2["role"] == S.ROLE_EDITOR            # role upgraded


def test_add_recipient_purity():
    rec = S.build_share("a", 1, "A", "b", "u")
    rec2, _ = S.add_recipient(rec, "x@x.com", "viewer")
    assert rec["recipients"] == []                # original untouched
    assert len(rec2["recipients"]) == 1


def test_resolve_valid_and_role():
    rec = S.build_share("a", 1, "A", "b", "u")
    rec, r = S.add_recipient(rec, "e@x.com", "editor")
    got, err = S.resolve(rec, r["token"])
    assert err is None and got["role"] == S.ROLE_EDITOR


def test_resolve_bad_token():
    rec = S.build_share("a", 1, "A", "b", "u")
    got, err = S.resolve(rec, "nope")
    assert got is None and "invalid" in err.lower()


def test_resolve_none_record():
    got, err = S.resolve(None, "tok")
    assert got is None and err


def test_revoke_blocks_resolve():
    rec = S.build_share("a", 1, "A", "b", "u")
    rec, r = S.add_recipient(rec, "e@x.com", "viewer")
    rec, err = S.revoke(rec, r["token"])
    assert err is None
    got, rerr = S.resolve(rec, r["token"])
    assert got is None and "revoked" in rerr.lower()


def test_reinvite_after_revoke_creates_new_recipient():
    rec = S.build_share("a", 1, "A", "b", "u")
    rec, r1 = S.add_recipient(rec, "e@x.com", "viewer")
    rec, _ = S.revoke(rec, r1["token"])
    rec, r2 = S.add_recipient(rec, "e@x.com", "editor")   # revoked one is skipped
    assert r2["token"] != r1["token"]
    assert len(rec["recipients"]) == 2
    assert len(S.active_recipients(rec)) == 1


def test_set_role():
    rec = S.build_share("a", 1, "A", "b", "u")
    rec, r = S.add_recipient(rec, "e@x.com", "viewer")
    rec, err = S.set_role(rec, r["token"], "editor")
    assert err is None
    got, _ = S.resolve(rec, r["token"])
    assert got["role"] == S.ROLE_EDITOR


def test_mark_opened():
    rec = S.build_share("a", 1, "A", "b", "u")
    rec, r = S.add_recipient(rec, "e@x.com", "viewer")
    rec, changed = S.mark_opened(rec, r["token"], "2026-07-06T10:00:00Z")
    assert changed
    got, _ = S.resolve(rec, r["token"])
    assert got["last_opened_at"] == "2026-07-06T10:00:00Z"


def test_mark_opened_revoked_noop():
    rec = S.build_share("a", 1, "A", "b", "u")
    rec, r = S.add_recipient(rec, "e@x.com", "viewer")
    rec, _ = S.revoke(rec, r["token"])
    rec, changed = S.mark_opened(rec, r["token"])
    assert not changed
