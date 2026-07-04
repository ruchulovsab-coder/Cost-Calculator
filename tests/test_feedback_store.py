"""Feedback store — pure helpers (no Azure required)."""
from modules.state.feedback_store import (
    build_feedback, feedback_blob_name, to_csv, FIELDS, FEEDBACK_PREFIX,
)


def test_build_feedback_fields_and_defaults():
    rec = build_feedback(
        stage=" Multi · 8 · Transition ", category="Bug / Defect", raised_by="  Manager  ",
        note="  Gantt should end at Go-Live  ", submitted_by="a@nagarro.com", mode="multi",
        project=" Acme RFP ", app_version="1.62", saved_at="2026-07-04T10-00-00Z", fid="abcd1234")
    assert rec["id"] == "abcd1234"
    assert rec["saved_at"] == "2026-07-04T10-00-00Z"
    assert rec["stage"] == "Multi · 8 · Transition"          # trimmed
    assert rec["category"] == "Bug / Defect"
    assert rec["raised_by"] == "Manager"                     # trimmed
    assert rec["note"] == "Gantt should end at Go-Live"      # trimmed
    assert rec["submitted_by"] == "a@nagarro.com"
    assert rec["mode"] == "multi"
    assert rec["project"] == "Acme RFP"                      # trimmed
    assert rec["app_version"] == "1.62"


def test_build_feedback_autofills_id_and_timestamp():
    rec = build_feedback("Stage", "General", "", "note")
    assert rec["id"] and len(rec["id"]) == 8
    assert rec["saved_at"].endswith("Z")
    assert rec["category"] == "General"


def test_feedback_blob_name():
    name = feedback_blob_name("2026-07-04T10-00-00Z", "abcd1234")
    assert name == f"{FEEDBACK_PREFIX}2026-07-04T10-00-00Z__abcd1234.json"
    assert name.endswith(".json")


def test_to_csv_header_and_rows():
    rows = [build_feedback("S1", "Idea / Enhancement", "Team", "note one", fid="11111111"),
            build_feedback("S2", "Question", "", "note, with comma", fid="22222222")]
    csv = to_csv(rows)
    lines = csv.strip().splitlines()
    assert lines[0] == ",".join(FIELDS)
    assert len(lines) == 3                                   # header + 2 rows
    assert "note one" in csv and "S1" in csv and "S2" in csv


def test_to_csv_empty():
    assert to_csv([]).strip() == ",".join(FIELDS)
