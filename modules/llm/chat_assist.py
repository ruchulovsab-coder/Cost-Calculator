"""
Conversational estimation assistant (Groq — free tier, OpenAI-compatible).

A guarded chat that takes a plain-language brief for a managed-services estimate, asks
for anything missing, and — once it has enough — returns the structured inputs. The
caller (chat_page) applies those inputs to the model using India delivery rates and
lands on the Results Dashboard.

The model is instructed to reply with a single JSON object every turn:
    {"action": "ask"|"submit", "message": "<text>", "inputs": { ... }}
so we don't depend on provider-specific function-calling. Scope is locked to managed-
services estimation; the model refuses anything else and never requests/retains PII.

No AI runs unless GROQ_API_KEY is set (the Chat option degrades gracefully). Model
defaults to llama-3.3-70b-versatile (free, strong at extraction); override with
GROQ_MODEL. The groq SDK is imported lazily so this module imports fine without the
package/key (e.g. tests).
"""
import json
import os

DEFAULT_MODEL = "llama-3.3-70b-versatile"

# Coverage options the engine understands (config.settings.COVERAGE_MODELS keys).
COVERAGE_OPTIONS = ["8×5", "12×5", "16×5", "24×5", "24×7"]


def llm_configured() -> bool:
    return bool(os.environ.get("GROQ_API_KEY", "").strip())


def model_id() -> str:
    return os.environ.get("GROQ_MODEL", "").strip() or DEFAULT_MODEL


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

WHAT TO COLLECT (monthly figures unless noted): monitoring alerts/month, service requests/\
month, incidents/month, change requests/month, number of servers (and, if any, whether \
patching is Manual or Tool-Based), support coverage window (one of 8×5, 12×5, 16×5, 24×5, \
24×7), contingency % (default 10 if unstated), target margin % (default 20 if unstated).

OUTPUT CONTRACT — every reply MUST be a single JSON object, nothing else, of the form:
{"action": "ask" | "submit", "message": "<what to say to the user>", "inputs": { ... }}
- Use action "ask" while you still need essential drivers (volumes, server count, coverage). \
Put your brief, batched question in "message"; omit or empty "inputs".
- You MAY assume reasonable industry defaults for anything not given, but every assumption you \
make MUST appear in inputs.assumptions when you submit.
- When you have enough (at least the monthly volumes and the server count), use action \
"submit", set "message" to "I have sufficient information — let me cook it for you.", and fill \
"inputs" with: monthly_alerts, monthly_service_requests, monthly_incidents, monthly_changes, \
num_servers (all integers), patching_included (boolean), patching_method ("Manual" or \
"Tool-Based"), coverage_model (one of 8×5/12×5/16×5/24×5/24×7), contingency_pct, \
target_margin_pct (numbers), and assumptions (array of short strings).
Respond with ONLY the JSON object — no markdown, no prose around it."""


def _loads(raw: str):
    """Parse the model's JSON reply, tolerating ```json fences / surrounding text."""
    if not raw:
        return None
    s = raw.strip()
    if s.startswith("```"):
        s = s.strip("`")
        if s[:4].lower() == "json":
            s = s[4:]
    try:
        return json.loads(s)
    except Exception:
        a, b = s.find("{"), s.rfind("}")
        if a != -1 and b != -1 and b > a:
            try:
                return json.loads(s[a:b + 1])
            except Exception:
                return None
    return None


_FALLBACK_Q = ("Could you share the monthly volumes (alerts, service requests, incidents, "
               "changes) and the number of servers?")


def parse_response(raw: str) -> dict:
    """Pure: turn the model's raw JSON text into a result dict (unit-tested)."""
    data = _loads(raw)
    if not isinstance(data, dict):
        return {"type": "question", "text": _FALLBACK_Q}
    if str(data.get("action", "")).lower() == "submit":
        return {
            "type": "submit",
            "preface": data.get("message") or "I have sufficient information — let me cook it for you.",
            "data": data.get("inputs") or {},
        }
    return {"type": "question", "text": data.get("message") or _FALLBACK_Q}


def _to_messages(messages: list) -> list:
    """Build OpenAI/Groq-style messages: system prompt first, then the user/assistant
    history (roles already match Groq's 'user'/'assistant')."""
    out = [{"role": "system", "content": SYSTEM_PROMPT}]
    for m in messages:
        role = "assistant" if m.get("role") == "assistant" else "user"
        out.append({"role": role, "content": m.get("content", "")})
    return out


def run_chat_turn(messages: list) -> dict:
    """Send the conversation to Groq and return one of:
       {"type": "question", "text": ...}
       {"type": "submit",  "preface": ..., "data": {...}}
       {"type": "error",   "text": ...}
    """
    if not llm_configured():
        return {"type": "error", "text": "AI chat isn't configured (GROQ_API_KEY not set)."}
    try:
        from groq import Groq
        client = Groq(api_key=os.environ["GROQ_API_KEY"].strip())
        resp = client.chat.completions.create(
            model=model_id(),
            messages=_to_messages(messages),
            response_format={"type": "json_object"},
            temperature=0.2,
            max_tokens=1024,
        )
        raw = resp.choices[0].message.content
    except Exception as e:  # network/auth/SDK errors — surface, don't crash the app
        return {"type": "error", "text": f"AI request failed: {e}"}
    return parse_response(raw)
