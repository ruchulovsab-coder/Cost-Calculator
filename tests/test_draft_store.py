"""Unit tests for the pure draft/orphan logic (no Azure required)."""
from datetime import datetime, timedelta, timezone

from config.settings import DRAFT_ORPHAN_DAYS
from modules.state import draft_store as D


def test_blob_names():
    assert D.draft_blob_name("acme-rfp") == "__drafts__/acme-rfp.json"
    assert D.orphan_blob_name("acme-rfp", "2026-06-18T10-00-00Z") == \
        "__orphans__/acme-rfp__2026-06-18T10-00-00Z.json"


def test_orphan_name_parts_roundtrip():
    name = D.orphan_blob_name("acme-rfp", "2026-06-18T10-00-00Z")
    slug, ts = D.orphan_name_parts(name)
    assert slug == "acme-rfp" and ts == "2026-06-18T10-00-00Z"


def test_age_days_and_resumable_boundary():
    now = datetime(2026, 6, 18, tzinfo=timezone.utc)
    fresh = (now - timedelta(days=2)).strftime("%Y-%m-%dT%H-%M-%SZ")
    stale = (now - timedelta(days=DRAFT_ORPHAN_DAYS + 1)).strftime("%Y-%m-%dT%H-%M-%SZ")
    edge = (now - timedelta(days=DRAFT_ORPHAN_DAYS)).strftime("%Y-%m-%dT%H-%M-%SZ")

    assert round(D.age_days(fresh, now)) == 2
    assert D.is_resumable(fresh, now) is True
    assert D.is_resumable(edge, now) is True       # exactly at the window = still resumable
    assert D.is_resumable(stale, now) is False


def test_age_days_unparseable_is_zero():
    assert D.age_days("not-a-timestamp") == 0.0
    assert D.is_resumable("") is True              # treat unknown age as fresh, not orphaned


def test_build_draft_shape():
    rec = D.build_draft("acme", "Acme RFP", "Jane", {"current_step": 4},
                        saved_at="2026-06-18T10-00-00Z")
    assert rec["slug"] == "acme" and rec["project"] == "Acme RFP"
    assert rec["prepared_by"] == "Jane"
    assert rec["inputs"]["current_step"] == 4
    assert rec["saved_at"] == "2026-06-18T10-00-00Z"
