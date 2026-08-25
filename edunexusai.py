import os
import requests
import traceback

from flask import Flask, request, jsonify
from flask_cors import CORS

from google import genai
from google.genai import types


# ============================================================
# APP SETUP
# ============================================================

app = Flask(__name__)
CORS(app)


# ============================================================
# DISCORD WEBHOOK
# IMPORTANT: Keep this in Render Environment Variables
# ============================================================

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")


# ============================================================
# GEMINI API KEY POOL
# Add as many configured keys as you want:
#
# GEMINI_API_KEY
# GEMINI_API_KEY_2
# GEMINI_API_KEY_3
#
# Missing keys are automatically ignored.
# ============================================================

_raw_keys = [
    os.environ.get("GEMINI_API_KEY"),
    os.environ.get("GEMINI_API_KEY_2"),
    os.environ.get("GEMINI_API_KEY_3"),
]

clients = [
    genai.Client(api_key=key)
    for key in _raw_keys
    if key
]


if not clients:
    print("WARNING: Koi GEMINI_API_KEY set nahi hai!")


# ============================================================
# MODEL
# ============================================================

MODEL_NAME = "gemini-2.5-flash"


# ============================================================
# SYSTEM PROMPT
# ============================================================

SYSTEM_PROMPT = (
    "You are EduNexus AI, powered by the KX Neural Core, "
    "a friendly and extremely smart study assistant for Indian Class 12 students "
    "(Physics, Chemistry, Maths, Computer Science, English). "

    "Keep answers SHORT and clear by default -- around 3 to 6 short sentences, "
    "or a few bullet points. Do not write long essays unless the user specifically "
    "asks for a detailed explanation. "

    "If the user asks for a Custom Quiz, act as a strict examiner, "
    "wait for their answers, evaluate them in the next turn, "
    "and give them a score out of the total questions. "

    "Use simple, exam-friendly language. "
    "Explain difficult concepts in an easy way suitable for Class 12 students."
)


# ============================================================
# CONVERSATION MEMORY
# ============================================================

conversation_history = {}


# ============================================================
# DISCORD LOGIN ALERT
# ============================================================

def send_discord_alert(username):
    if not DISCORD_WEBHOOK_URL:
        print("[DISCORD] Webhook configured nahi hai.")
        return

    try:
        data = {
            "content": (
                "🚨 **BINGO!** New User Logged In!\n"
                f"🧑‍🎓 **Name:** {username}\n"
                "💻 **Action:** Launched EduNexus AI Dashboard 🚀"
            )
        }

        response = requests.post(
            DISCORD_WEBHOOK_URL,
            json=data,
            timeout=5
        )

        if response.status_code not in (200, 204):
            print(
                f"[DISCORD] Webhook Error: "
                f"{response.status_code} - {response.text}"
            )

    except Exception as e:
        print(f"[DISCORD Alert Failed]: {e}")


# ============================================================
# CHAT API
# ============================================================

@app.route("/chat", methods=["POST"])
def chat():

    try:

        # ----------------------------------------------------
        # Read JSON
        # ----------------------------------------------------

        data = request.get_json(silent=True) or {}

        user_message = data.get("message", "").strip()
        session_id = data.get(
            "session_id",
            "default_session"
        )
        user_name = data.get(
            "user_name",
            "Student"
        ).strip()

        # ----------------------------------------------------
        # Basic validation
        # ----------------------------------------------------

        if not user_message:
            return jsonify({
                "reply": "Please enter a message."
            }), 400

        if not clients:
            return jsonify({
                "reply": (
                    "Gemini API key is not configured on the backend."
                )
            }), 500

        print(
            f"\n[USER QUERY RECEIVED from {user_name}]: "
            f"{user_message}"
        )


        # ====================================================
        # CREATE NEW SESSION
        # ====================================================

        if session_id not in conversation_history:

            send_discord_alert(user_name)

            conversation_history[session_id] = [

                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_text(
                            text=(
                                f"My name is {user_name}. "
                                "Please remember it."
                            )
                        )
                    ]
                ),

                types.Content(
                    role="model",
                    parts=[
                        types.Part.from_text(
                            text=(
                                f"Hello {user_name}, "
                                "I am KX Neural Core. "
                                "I will remember your name "
                                "and our conversation history."
                            )
                        )
                    ]
                )
            ]


        # ====================================================
        # ADD USER MESSAGE
        # ====================================================

        conversation_history[session_id].append(

            types.Content(
                role="user",
                parts=[
                    types.Part.from_text(
                        text=user_message
                    )
                ]
            )
        )


        # ====================================================
        # LIMIT CONVERSATION MEMORY
        # ====================================================

        MAX_HISTORY = 10

        if len(conversation_history[session_id]) > MAX_HISTORY:

            conversation_history[session_id] = (
                conversation_history[session_id][-MAX_HISTORY:]
            )


        # ====================================================
        # TRY ALL GEMINI CLIENTS
        # ====================================================

        last_error = None

        for i, client in enumerate(clients, start=1):

            try:

                print(
                    f"[KX Neural Core] "
                    f"Trying API key #{i}..."
                )


                # ------------------------------------------------
                # GEMINI GENERATE CONTENT
                # ------------------------------------------------

                response = client.models.generate_content(

                    model=MODEL_NAME,

                    contents=conversation_history[
                        session_id
                    ],

                    config=types.GenerateContentConfig(

                        system_instruction=SYSTEM_PROMPT,

                        max_output_tokens=600
                    )
                )


                # ------------------------------------------------
                # GET RESPONSE TEXT
                # ------------------------------------------------

                ai_response_text = (
                    response.text
                    if response.text
                    else "I could not process that request."
                )


                # ------------------------------------------------
                # SAVE AI RESPONSE
                # ------------------------------------------------

                conversation_history[
                    session_id
                ].append(

                    types.Content(
                        role="model",
                        parts=[
                            types.Part.from_text(
                                text=ai_response_text
                            )
                        ]
                    )
                )


                # ------------------------------------------------
                # SUCCESS
                # ------------------------------------------------

                print(
                    f"[KX Neural Core] "
                    f"Reply sent using key #{i}"
                )

                return jsonify({
                    "reply": ai_response_text
                })


            except Exception as e:

                print(
                    f"[KEY #{i} ERROR]: {str(e)}"
                )

                last_error = e

                # Try next API key
                continue


        # ====================================================
        # ALL KEYS FAILED
        # ====================================================

        print(
            f"[ALL KEYS FAILED]: "
            f"{last_error}"
        )

        return jsonify({
            "reply": (
                "KX Neural Core is temporarily unavailable. "
                "Please try again in a moment."
            )
        }), 503


    except Exception as e:

        traceback.print_exc()

        return jsonify({
            "reply": (
                f"Backend Crash: {str(e)}"
            )
        }), 200


# ============================================================
# HEALTH CHECK
# ============================================================

@app.route("/", methods=["GET"])
def home():

    return jsonify({
        "status": "online",
        "service": "EduNexus AI",
        "core": "KX Neural Core",
        "model": MODEL_NAME,
        "api_keys_configured": len(clients)
    })


# ============================================================
# SERVER START
# ============================================================

if __name__ == "__main__":

    print("--------------------------------------------------")
    print("[SYSTEM] KX Neural Core LIVE SERVER BOOTING...")
    print(f"[SYSTEM] Selected Model: {MODEL_NAME}")
    print(f"[SYSTEM] API Keys Loaded: {len(clients)}")
    print("--------------------------------------------------")

    port = int(
        os.environ.get(
            "PORT",
            5000
        )
    )

    app.run(
        host="0.0.0.0",
        port=port
    )
