"""Unit tests for the pure parts of the cloud estimate store + summary builder."""
import pytest

from modules.state.estimate_store import (
    slugify, next_version_from_names, build_payload, store_configured,
)
from modules.state.session_manager import build_estimate_summary


def test_slugify():
    assert slugify("Acme Corp — RFP 2026!") == "acme-corp-rfp-2026"
    assert slugify("A/B\\C") == "a-b-c"
    assert slugify("   ") == "untitled"
    assert slugify("") == "untitled"


def test_next_version_from_names():
    names = ["acme/2026__v1.json", "acme/2026__v2.json", "other/x__v1.json"]
    assert next_version_from_names(names, "acme") == 3
    assert next_version_from_names([], "acme") == 1
    assert next_version_from_names(["acme/notes.txt"], "acme") == 1  # non-json ignored


def test_build_payload_structure():
    p = build_payload("Acme Corp", "after negotiation", "me",
                      {"target_margin_pct": 20}, {"selling_price": 100}, 2, "2026-06-16T00-00-00Z")
    assert p["meta"]["project"] == "Acme Corp"
    assert p["meta"]["project_slug"] == "acme-corp"
    assert p["meta"]["version"] == 2
    assert p["meta"]["label"] == "after negotiation"
    assert p["meta"]["author"] == "me"
    assert p["meta"]["saved_at"] == "2026-06-16T00-00-00Z"
    assert p["inputs"]["target_margin_pct"] == 20
    assert p["summary"]["selling_price"] == 100


def test_store_not_configured_by_default(monkeypatch):
    monkeypatch.delenv("ESTIMATES_ACCOUNT_URL", raising=False)
    monkeypatch.delenv("ESTIMATES_CONTAINER", raising=False)
    assert store_configured() is False


def test_build_estimate_summary():
    model = {
        "total_fte": 3.456,
        "cost_result": {"total_delivery_cost": 1000.4},
        "price_result": {"selling_price": 1250.6},
        "reporting_currency": "USD",
        "fte_basis": "raw",
    }
    s = build_estimate_summary(model)
    assert s["total_fte"] == 3.46
    assert s["delivery_cost"] == 1000
    assert s["selling_price"] == 1251
    assert s["reporting_currency"] == "USD"
    assert s["fte_basis"] == "raw"
