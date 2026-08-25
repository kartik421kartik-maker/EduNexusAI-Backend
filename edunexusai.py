"""EduNexus AI Flask backend.

Required Render environment variable:
    GEMINI_API_KEY=<your Google AI Studio key>

Optional:
    GEMINI_API_KEY_2, GEMINI_API_KEY_3, GEMINI_MODEL, ALLOWED_ORIGINS
"""

import logging
import os
from threading import Lock

from flask import Flask, jsonify, request
from flask_cors import CORS
from google import genai
from google.genai import types


logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("edunexus")

app = Flask(__name__)

# For a public GitHub Pages frontend, keep the default '*'.  To restrict it later,
# set ALLOWED_ORIGINS to a comma-separated list of HTTPS frontend URLs.
allowed_origins = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", "*").split(",")
    if origin.strip()
]
CORS(app, resources={r"/*": {"origins": allowed_origins}})

MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
SYSTEM_PROMPT = """
You are EduNexus AI, a friendly and academically accurate study assistant for
Indian Class 12 students. Help with Physics, Chemistry, Mathematics, Computer
Science, and English. Keep ordinary answers clear and concise. Use exam-friendly
language, show key steps for numerical problems, and give clean definitions.

If the student requests a custom quiz, act as a strict examiner: provide only
the requested questions and options first, wait for answers, then mark them and
explain incorrect answers.
""".strip()


def configured_keys():
    """Read non-empty API keys without ever logging their values."""
    names = ("GEMINI_API_KEY", "GEMINI_API_KEY_2", "GEMINI_API_KEY_3")
    return [os.getenv(name, "").strip() for name in names if os.getenv(name, "").strip()]


clients = [genai.Client(api_key=key) for key in configured_keys()]

# In-memory history is enough for a small demo.  It resets whenever Render restarts.
conversation_history = {}
history_lock = Lock()
MAX_HISTORY_MESSAGES = 12


def to_contents(messages):
    return [
        types.Content(
            role=item["role"],
            parts=[types.Part.from_text(text=item["text"])],
        )
        for item in messages
    ]


def generate_reply(messages):
    """Try each configured key and return the first usable answer."""
    errors = []

    for number, client in enumerate(clients, start=1):
        try:
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=to_contents(messages),
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    max_output_tokens=600,
                    temperature=0.4,
                ),
            )
            reply = (getattr(response, "text", None) or "").strip()
            if reply:
                logger.info("Gemini request succeeded with key #%s", number)
                return reply
            raise RuntimeError("Gemini returned no text")
        except Exception as exc:  # Try the next key without exposing provider details.
            logger.warning("Gemini key #%s failed: %s", number, exc)
            errors.append(f"key #{number}: {type(exc).__name__}")

    raise RuntimeError("; ".join(errors) or "No Gemini client is configured")


@app.get("/")
def home():
    return jsonify(
        status="online",
        service="EduNexus AI",
        model=MODEL_NAME,
        gemini_clients=len(clients),
    )


@app.get("/health")
def health():
    return jsonify(
        status="healthy" if clients else "misconfigured",
        model=MODEL_NAME,
        gemini_clients=len(clients),
    ), (200 if clients else 503)


@app.post("/chat")
def chat():
    data = request.get_json(silent=True) or {}
    user_message = str(data.get("message", "")).strip()
    session_id = str(data.get("session_id", "default_session")).strip()[:128] or "default_session"

    if not user_message:
        return jsonify(reply="Please enter a message."), 400
    if not clients:
        logger.error("Chat was requested but GEMINI_API_KEY is not set")
        return jsonify(reply="Server configuration is incomplete. Please contact the site owner."), 503

    new_message = {"role": "user", "text": user_message}

    # Do not save a message until Gemini succeeds.  Otherwise a temporary API
    # failure pollutes the conversation and makes the next answer look confused.
    with history_lock:
        previous = conversation_history.get(session_id, [])[-MAX_HISTORY_MESSAGES:]
        pending_history = previous + [new_message]

    try:
        reply = generate_reply(pending_history)
    except Exception:
        logger.exception("All configured Gemini clients failed")
        return jsonify(reply="AI service is temporarily unavailable. Please try again in a moment."), 503

    with history_lock:
        conversation_history[session_id] = (
            pending_history + [{"role": "model", "text": reply}]
        )[-MAX_HISTORY_MESSAGES:]

    return jsonify(reply=reply), 200


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    logger.info("Starting EduNexus AI on port %s with %s Gemini key(s)", port, len(clients))
    app.run(host="0.0.0.0", port=port, debug=False)
