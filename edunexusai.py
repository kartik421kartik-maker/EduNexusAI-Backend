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
# CONFIGURATION
# ============================================================

MODEL_NAME = "gemini-2.5-flash"

SYSTEM_PROMPT = (
    "You are EduNexus AI, powered by the KX Neural Core, "
    "a friendly and extremely smart study assistant for Indian Class 12 students "
    "(Physics, Chemistry, Maths, Computer Science, English). "

    "Keep answers short and clear by default, around 3 to 6 short sentences "
    "or a few bullet points. Do not write long essays unless the user asks "
    "for a detailed explanation. "

    "If the user asks for a Custom Quiz, act as a strict examiner. "
    "Wait for their answers, evaluate them in the next turn, "
    "and give them a score out of the total questions. "

    "Use simple, exam-friendly language suitable for Class 12 students."
)


# ============================================================
# DISCORD WEBHOOK
# IMPORTANT:
# Never hard-code the webhook URL.
# Add DISCORD_WEBHOOK_URL in Render Environment Variables.
# ============================================================

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")


# ============================================================
# GEMINI API KEY POOL
#
# Render Environment Variables:
#
# GEMINI_API_KEY
# GEMINI_API_KEY_2
# GEMINI_API_KEY_3
#
# Empty/missing keys are automatically ignored.
# ============================================================

_raw_keys = [
    os.environ.get("GEMINI_API_KEY"),
    os.environ.get("GEMINI_API_KEY_2"),
    os.environ.get("GEMINI_API_KEY_3"),
]

# Remove empty keys and accidental spaces
_raw_keys = [
    key.strip()
    for key in _raw_keys
    if key and key.strip()
]


# Create Gemini clients
clients = []

for key in _raw_keys:
    try:
        clients.append(
            genai.Client(api_key=key)
        )
    except Exception as e:
        print(
            f"[GEMINI CLIENT INIT ERROR]: {str(e)}"
        )


# ============================================================
# STARTUP LOGS
# ============================================================

print("--------------------------------------------------")
print("[SYSTEM] EduNexus AI Backend")
print("[SYSTEM] KX Neural Core")
print(f"[SYSTEM] Model: {MODEL_NAME}")
print(f"[SYSTEM] Gemini Keys Loaded: {len(clients)}")
print(
    f"[SYSTEM] Discord Webhook: "
    f"{'CONFIGURED' if DISCORD_WEBHOOK_URL else 'NOT CONFIGURED'}"
)
print("--------------------------------------------------")


# ============================================================
# CONVERSATION MEMORY
# ============================================================

conversation_history = {}


# ============================================================
# DISCORD ALERT
# ============================================================

def send_discord_alert(username):

    if not DISCORD_WEBHOOK_URL:
        print(
            "[DISCORD] Webhook not configured. "
            "Skipping alert."
        )
        return

    try:

        payload = {
            "content": (
                "🚨 **BINGO! New User Logged In!**\n"
                f"🧑‍🎓 **Name:** {username}\n"
                "💻 **Action:** Launched EduNexus AI Dashboard 🚀"
            )
        }

        response = requests.post(
            DISCORD_WEBHOOK_URL,
            json=payload,
            timeout=5
        )

        if response.status_code not in (200, 204):

            print(
                "[DISCORD ERROR] "
                f"Status: {response.status_code}"
            )

            print(
                f"[DISCORD ERROR BODY] {response.text}"
            )

        else:

            print(
                "[DISCORD] Login alert sent successfully."
            )

    except Exception as e:

        print(
            f"[DISCORD EXCEPTION] {str(e)}"
        )


# ============================================================
# HOME / HEALTH CHECK
# ============================================================

@app.route("/", methods=["GET"])
def home():

    return jsonify({
        "status": "online",
        "service": "EduNexus AI",
        "core": "KX Neural Core",
        "model": MODEL_NAME,
        "gemini_keys_loaded": len(clients),
        "discord_webhook": bool(DISCORD_WEBHOOK_URL)
    })


# ============================================================
# HEALTH CHECK
# ============================================================

@app.route("/health", methods=["GET"])
def health():

    return jsonify({
        "status": "healthy",
        "model": MODEL_NAME,
        "gemini_clients": len(clients)
    })


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

        user_message = str(
            data.get("message", "")
        ).strip()

        session_id = str(
            data.get(
                "session_id",
                "default_session"
            )
        )

        user_name = str(
            data.get(
                "user_name",
                "Student"
            )
        ).strip()


        # ----------------------------------------------------
        # Validation
        # ----------------------------------------------------

        if not user_message:

            return jsonify({
                "reply": "Please enter a message."
            }), 400


        if not clients:

            print(
                "[FATAL] No Gemini API clients configured."
            )

            return jsonify({
                "reply": (
                    "Gemini API is not configured. "
                    "Please check Render Environment Variables."
                )
            }), 500


        print("")
        print("==================================================")
        print(
            f"[USER] {user_name}"
        )
        print(
            f"[SESSION] {session_id}"
        )
        print(
            f"[MESSAGE] {user_message}"
        )
        print("==================================================")


        # ====================================================
        # CREATE SESSION
        # ====================================================

        if session_id not in conversation_history:

            print(
                f"[SESSION] Creating new session: {session_id}"
            )

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
                                f"Hello {user_name}! "
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
        # KEEP ONLY LAST 10 MESSAGES
        # ====================================================

        MAX_HISTORY = 10

        if len(
            conversation_history[session_id]
        ) > MAX_HISTORY:

            conversation_history[session_id] = (
                conversation_history[session_id][
                    -MAX_HISTORY:
                ]
            )


        # ====================================================
        # TRY EVERY GEMINI KEY
        # ====================================================

        last_error = None

        for index, client in enumerate(
            clients,
            start=1
        ):

            print("")
            print(
                f"[GEMINI] Trying API Key #{index}..."
            )

            try:

                # ------------------------------------------------
                # GENERATE CONTENT
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
                # GET RESPONSE
                # ------------------------------------------------

                ai_response_text = (
                    response.text
                    if response.text
                    else ""
                )


                if not ai_response_text:

                    raise Exception(
                        "Gemini returned an empty response."
                    )


                # ------------------------------------------------
                # SAVE MODEL RESPONSE
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
                    f"[SUCCESS] Gemini API Key #{index} "
                    f"worked successfully."
                )

                print(
                    f"[MODEL] {MODEL_NAME}"
                )

                print("==================================================")
                print("")

                return jsonify({
                    "reply": ai_response_text
                }), 200


            except Exception as e:

                last_error = e

                error_text = str(e)

                print("")
                print(
                    f"[KEY #{index} FAILED]"
                )
                print(
                    f"[ERROR TYPE] {type(e).__name__}"
                )
                print(
                    f"[ERROR] {error_text}"
                )
                print("")

                # Try next API key
                continue


        # ====================================================
        # ALL GEMINI KEYS FAILED
        # ====================================================

        print("")
        print("==================================================")
        print("[CRITICAL] ALL GEMINI API KEYS FAILED")
        print(
            f"[MODEL] {MODEL_NAME}"
        )
        print(
            f"[LAST ERROR] {last_error}"
        )
        print("==================================================")
        print("")


        # IMPORTANT:
        # During debugging, return the real error.
        # Once everything works, you can hide it.
        return jsonify({
            "reply": (
                "Gemini API Error:\n\n"
                f"{str(last_error)}"
            ),
            "error": True,
            "model": MODEL_NAME
        }), 503


    # ========================================================
    # BACKEND CRASH
    # ========================================================

    except Exception as e:

        print("")
        print("==================================================")
        print("[BACKEND CRASH]")
        traceback.print_exc()
        print("==================================================")
        print("")

        return jsonify({
            "reply": (
                "Backend Error:\n\n"
                f"{str(e)}"
            ),
            "error": True
        }), 500


# ============================================================
# SERVER START
# ============================================================

if __name__ == "__main__":

    port = int(
        os.environ.get(
            "PORT",
            5000
        )
    )

    print("--------------------------------------------------")
    print("[SYSTEM] KX Neural Core LIVE SERVER BOOTING...")
    print(f"[SYSTEM] Port: {port}")
    print(f"[SYSTEM] Model: {MODEL_NAME}")
    print(
        f"[SYSTEM] Gemini Clients: {len(clients)}"
    )
    print("--------------------------------------------------")

    app.run(
        host="0.0.0.0",
        port=port
    )
