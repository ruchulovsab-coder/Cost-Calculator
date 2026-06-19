"""
Conversational estimation assistant (Claude / Anthropic API).

A guarded chat that takes a plain-language brief for a managed-services estimate, asks
for anything missing, and — once it has enough — emits the structured inputs via the
`submit_estimate` tool. The caller (chat_page) applies those inputs to the model using
India delivery rates and lands on the Results Dashboard.

Scope is locked to managed-services effort/cost estimation; the model is instructed to
refuse anything else and to never request or retain PII. No AI runs unless
ANTHROPIC_API_KEY is set, so the Chat option degrades gracefully otherwise.

Model defaults to Claude Haiku 4.5 (plenty for input extraction); override with the
ANTHROPIC_MODEL env var. The `anthropic` SDK is imported lazily so this module imports
fine in environments where the package/key isn't present (e.g. local tests).
"""
import os

DEFAULT_MODEL = "claude-haiku-4-5"

# Coverage options the engine understands (config.settings.COVERAGE_MODELS keys).
COVERAGE_OPTIONS = ["8×5", "12×5", "16×5", "24×5", "24×7"]


def llm_configured() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())


def model_id() -> str:
    return os.environ.get("ANTHROPIC_MODEL", "").strip() or DEFAULT_MODEL


def normalize_coverage(value: str) -> str:
    """Map a free-form coverage string ('24x7', '24/7', '8*5', '24×7') to a
    COVERAGE_MODELS key. Falls back to 8×5."""
    s = (value or "").strip().lower().replace(" ", "")
    for sep in ("/", "*", "×", "by", "-"):
        s = s.replace(sep, "x")
    table = {"8x5": "8×5", "12x5": "12×5", "16x5": "16×5", "24x5": "24×5", "24x7": "24×7"}
    if s in table:
        return table[s]
    if "24" in s and "7" in s:
        return "24×7"
    if "24" in s and "5" in s:
        return "24×5"
    if "16" in s:
        return "16×5"
    if "12" in s:
        return "12×5"
    return "8×5"


SYSTEM_PROMPT = """You are the estimation assistant for Nagarro's Cloud & Infrastructure \
Managed Services effort & cost calculator. Your only job is to gather the inputs needed to \
produce a managed-services operations estimate, then submit them.

STRICT SCOPE: Only discuss this estimate. If the user asks anything outside managed-services \
effort/cost estimation (general knowledge, coding, chit-chat, etc.), politely decline in one \
sentence and steer back to the estimate. Do not answer off-topic questions.

NO PII: Never ask for, repeat, or store personal or client-identifying information — customer \
names, people's names, locations, addresses, emails, phone numbers, contacts. If the user \
volunteers any, do not echo it; silently ignore it and continue.

DELIVERY: This estimate always uses India delivery rates. Do not ask about location, currency, \
or rates.

WHAT TO COLLECT (monthly figures unless noted):
- Monitoring alerts per month
- Service requests per month
- Incidents per month
- Change requests per month
- Number of servers (and, if any, whether patching is Manual or Tool-Based)
- Support coverage window (one of: 8×5, 12×5, 16×5, 24×5, 24×7)
- Contingency % (effort buffer) — default 10 if unstated
- Target margin % — default 20 if unstated

HOW TO BEHAVE:
- Ask brief, batched clarifying questions for the essential drivers you don't yet have \
(volumes, servers, coverage). Keep it to a couple of short turns.
- You MAY assume reasonable industry defaults for anything the user doesn't give, but every \
assumption you make MUST be listed in the `assumptions` array when you submit.
- When you have enough to proceed, FIRST tell the user "I have sufficient information — let me \
cook it for you." THEN call the `submit_estimate` tool with your best values and the full list \
of assumptions. Do not call the tool before you have at least the monthly volumes and the \
server count (assume coverage/contingency/margin defaults if needed, and list them)."""


SUBMIT_TOOL = {
    "name": "submit_estimate",
    "description": "Submit the gathered inputs to run the managed-services estimate (India rates).",
    "input_schema": {
        "type": "object",
        "properties": {
            "monthly_alerts": {"type": "integer", "minimum": 0},
            "monthly_service_requests": {"type": "integer", "minimum": 0},
            "monthly_incidents": {"type": "integer", "minimum": 0},
            "monthly_changes": {"type": "integer", "minimum": 0},
            "num_servers": {"type": "integer", "minimum": 0},
            "patching_included": {"type": "boolean"},
            "patching_method": {"type": "string", "enum": ["Manual", "Tool-Based"]},
            "coverage_model": {"type": "string"},
            "contingency_pct": {"type": "number"},
            "target_margin_pct": {"type": "number"},
            "assumptions": {"type": "array", "items": {"type": "string"}},
        },
        "required": [
            "monthly_alerts", "monthly_service_requests", "monthly_incidents",
            "monthly_changes", "num_servers", "coverage_model",
            "contingency_pct", "target_margin_pct", "assumptions",
        ],
    },
}


def run_chat_turn(messages: list) -> dict:
    """Send the conversation to Claude and return one of:
       {"type": "question", "text": <assistant text>}
       {"type": "submit",  "preface": <assistant text>, "data": <tool input dict>}
       {"type": "error",   "text": <message>}
    `messages` is a list of {"role": "user"|"assistant", "content": str}.
    """
    if not llm_configured():
        return {"type": "error", "text": "AI chat isn't configured (ANTHROPIC_API_KEY not set)."}
    try:
        import anthropic
        client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from the environment
        resp = client.messages.create(
            model=model_id(),
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            tools=[SUBMIT_TOOL],
            messages=messages,
        )
    except Exception as e:  # network/auth/SDK errors — surface, don't crash the app
        return {"type": "error", "text": f"AI request failed: {e}"}

    text = " ".join(b.text for b in resp.content if getattr(b, "type", "") == "text").strip()
    tool = next((b for b in resp.content
                 if getattr(b, "type", "") == "tool_use" and getattr(b, "name", "") == "submit_estimate"),
                None)
    if tool is not None:
        return {
            "type": "submit",
            "preface": text or "I have sufficient information — let me cook it for you.",
            "data": dict(tool.input),
        }
    return {
        "type": "question",
        "text": text or ("Could you share the monthly volumes (alerts, service requests, "
                         "incidents, changes) and the number of servers?"),
    }
