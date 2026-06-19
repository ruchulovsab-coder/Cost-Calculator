"""Unit tests for the pure chat-assist helpers (no Gemini SDK / network needed)."""
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
    from config.settings import COVERAGE_MODELS
    for v in ["24x7", "16x5", "8*5", "nonsense", ""]:
        assert CA.normalize_coverage(v) in COVERAGE_MODELS


def test_model_id_default_and_override(monkeypatch):
    monkeypatch.delenv("GROQ_MODEL", raising=False)
    assert CA.model_id() == "llama-3.3-70b-versatile"
    monkeypatch.setenv("GROQ_MODEL", "llama-3.1-8b-instant")
    assert CA.model_id() == "llama-3.1-8b-instant"


def test_llm_configured_reflects_env(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    assert CA.llm_configured() is False
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    assert CA.llm_configured() is True


def test_run_chat_turn_unconfigured_returns_error(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    out = CA.run_chat_turn([{"role": "user", "content": "hi"}])
    assert out["type"] == "error"


def test_parse_response_ask():
    out = CA.parse_response('{"action": "ask", "message": "How many servers?"}')
    assert out["type"] == "question"
    assert out["text"] == "How many servers?"


def test_parse_response_submit_with_fences():
    raw = ('```json\n{"action": "submit", "message": "let me cook it", '
           '"inputs": {"monthly_alerts": 2000, "num_servers": 500, "assumptions": ["24x7 assumed"]}}\n```')
    out = CA.parse_response(raw)
    assert out["type"] == "submit"
    assert out["data"]["monthly_alerts"] == 2000
    assert out["data"]["num_servers"] == 500
    assert out["preface"]


def test_parse_response_garbage_falls_back_to_question():
    out = CA.parse_response("not json at all")
    assert out["type"] == "question" and out["text"]


def test_to_messages_prepends_system_and_maps_roles():
    out = CA._to_messages([
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
    ])
    assert out[0]["role"] == "system" and out[0]["content"]
    assert out[1] == {"role": "user", "content": "hi"}
    assert out[2] == {"role": "assistant", "content": "hello"}
