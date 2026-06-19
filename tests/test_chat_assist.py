"""Unit tests for the pure chat-assist helpers (no Anthropic SDK / network needed)."""
import os

from modules.llm import chat_assist as CA


def test_normalize_coverage_variants():
    assert CA.normalize_coverage("24x7") == "24×7"
    assert CA.normalize_coverage("24/7") == "24×7"
    assert CA.normalize_coverage("24×7") == "24×7"
    assert CA.normalize_coverage("8*5") == "8×5"
    assert CA.normalize_coverage("16 x 5") == "16×5"
    assert CA.normalize_coverage("12x5") == "12×5"
    assert CA.normalize_coverage("24x5") == "24×5"


def test_normalize_coverage_fallback():
    assert CA.normalize_coverage("") == "8×5"
    assert CA.normalize_coverage("whatever") == "8×5"
    # All normalized values must be real COVERAGE_MODELS keys
    from config.settings import COVERAGE_MODELS
    for v in ["24x7", "16x5", "8*5", "nonsense", ""]:
        assert CA.normalize_coverage(v) in COVERAGE_MODELS


def test_model_id_default_and_override(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_MODEL", raising=False)
    assert CA.model_id() == "claude-haiku-4-5"
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-opus-4-8")
    assert CA.model_id() == "claude-opus-4-8"


def test_llm_configured_reflects_env(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert CA.llm_configured() is False
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    assert CA.llm_configured() is True


def test_run_chat_turn_unconfigured_returns_error(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    out = CA.run_chat_turn([{"role": "user", "content": "hi"}])
    assert out["type"] == "error"


def test_submit_tool_schema_shape():
    schema = CA.SUBMIT_TOOL["input_schema"]
    for f in ["monthly_alerts", "monthly_incidents", "num_servers", "coverage_model",
              "contingency_pct", "target_margin_pct", "assumptions"]:
        assert f in schema["properties"]
        assert f in schema["required"]
