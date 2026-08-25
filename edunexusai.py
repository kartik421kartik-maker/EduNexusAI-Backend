import os
import requests
import traceback

from flask import Flask, request, jsonify
from flask_cors import CORS

from google import genai
from google.genai import types


# ============================================================
# EDU NEXUS AI - KX NEURAL CORE
# ============================================================

app = Flask(__name__)
CORS(app)


# ============================================================
# MODEL
# ============================================================

# IMPORTANT:
# Current Google Gemini model for this backend.
MODEL_NAME = "gemini-3.6-flash"


# ============================================================
# SYSTEM PROMPT
# ============================================================

SYSTEM_PROMPT = """
You are EduNexus AI, powered by the KX Neural Core.

You are a friendly, highly intelligent study assistant
for Indian Class 12 students.

Subjects:
- Physics
- Chemistry
- Mathematics
- Computer Science
- English

Your job is to help students understand concepts clearly
and prepare for exams.

IMPORTANT RESPONSE RULES:

1. Keep normal answers short and clear.
2. Prefer 3 to 6 short sentences or bullet points.
3. Use simple, exam-friendly language.
4. Do not unnecessarily write huge essays.
5. If a student asks for a detailed explanation,
   then provide a detailed explanation.
6. For numerical problems, show the important steps.
7. For definitions, give a clean exam-ready definition.
8. For comparisons, use simple bullet points or a table.
9. For coding questions, explain the code clearly.
10. Be friendly but academically accurate.

CUSTOM QUIZ RULE:

If the student asks for a Custom Quiz:
- Act as a strict examiner.
- Generate the requested questions.
- Wait for the student's answers.
- On the next turn evaluate the answers.
- Give marks obtained and total marks.
- Clearly explain incorrect answers.

Always behave like a smart personal Class 12 tutor.
"""


# ============================================================
# DISCORD WEBHOOK
# ============================================================

# IMPORTANT:
# Put the NEW webhook in Render Environment Variables.
#
# DISCORD_WEBHOOK_URL=your_new_webhook
#
# NEVER hard-code the webhook here.
# ============================================================

DISCORD_WEBHOOK_URL = os.environ.get(
    "DISCORD_WEBHOOK_URL"
)


# ============================================================
# GEMINI API KEYS
# ============================================================

_raw_keys = [
    os.environ.get("GEMINI_API_KEY"),
    os.environ.get("GEMINI_API_KEY_2"),
    os.environ.get("GEMINI_API_KEY_3"),
]


# Remove empty keys and spaces
api_keys = []

for key in _raw_keys:

    if key:

        key = key.strip()

        if key:
            api_keys.append(key)


# ============================================================
# CREATE GEMINI CLIENTS
# ============================================================

clients = []

for key in api_keys:

    try:

        client = genai.Client(
            api_key=key
        )

        clients.append(client)

    except Exception as e:

        print(
            "[GEMINI CLIENT ERROR]:",
            str(e)
        )


# ============================================================
# CONVERSATION MEMORY
# ============================================================

conversation_history = {}


# ============================================================
# STARTUP INFORMATION
# ============================================================

print("")
print("==================================================")
print("        EDU NEXUS AI - KX NEURAL CORE")
print("==================================================")
print(f"[MODEL] {MODEL_NAME}")
print(f"[GEMINI KEYS] {len(clients)}")
print(
    "[DISCORD WEBHOOK]",
    "CONFIGURED"
    if DISCORD_WEBHOOK_URL
    else "NOT CONFIGURED"
)
print("==================================================")
print("")


# ============================================================
# DISCORD LOGIN ALERT
# ============================================================

def send_discord_alert(username):

    if not DISCORD_WEBHOOK_URL:

        print(
            "[DISCORD] Webhook not configured."
        )

        return


    try:

        payload = {

            "content":
                "🚨 **BINGO! New User Logged In!**\n"
                f"🧑‍🎓 **Name:** {username}\n"
                "💻 **Action:** Launched EduNexus AI Dashboard 🚀"

        }


        response = requests.post(

            DISCORD_WEBHOOK_URL,

            json=payload,

            timeout=5

        )


        if response.status_code in (200, 204):

            print(
                "[DISCORD] Login alert sent."
            )

        else:

            print(
                "[DISCORD ERROR]",
                response.status_code
            )


    except Exception as e:

        print(
            "[DISCORD ERROR]",
            str(e)
        )


# ============================================================
# HOME
# ============================================================

@app.route("/", methods=["GET"])
def home():

    return jsonify({

        "status": "online",

        "service": "EduNexus AI",

        "core": "KX Neural Core",

        "model": MODEL_NAME,

        "gemini_keys": len(clients)

    })


# ============================================================
# HEALTH CHECK
# ============================================================

@app.route("/health", methods=["GET"])
def health():

    return jsonify({

        "status": "healthy",

        "service": "EduNexus AI",

        "model": MODEL_NAME,

        "gemini_clients": len(clients)

    })


# ============================================================
# CHAT
# ============================================================

@app.route("/chat", methods=["POST"])
def chat():

    try:

        # ----------------------------------------------------
        # GET REQUEST DATA
        # ----------------------------------------------------

        data = request.get_json(
            silent=True
        ) or {}


        user_message = str(
            data.get(
                "message",
                ""
            )
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
        # VALIDATE MESSAGE
        # ----------------------------------------------------

        if not user_message:

            return jsonify({

                "reply":
                    "Please enter a message."

            }), 400


        # ----------------------------------------------------
        # CHECK API KEYS
        # ----------------------------------------------------

        if not clients:

            return jsonify({

                "reply":
                    "Gemini API keys are not configured. "
                    "Please check Render Environment Variables."

            }), 500


        print("")
        print("==================================================")
        print("[NEW CHAT REQUEST]")
        print(f"[USER] {user_name}")
        print(f"[SESSION] {session_id}")
        print(f"[MESSAGE] {user_message}")
        print("==================================================")


        # ====================================================
        # NEW SESSION
        # ====================================================

        if session_id not in conversation_history:


            # Discord alert
            send_discord_alert(
                user_name
            )


            conversation_history[
                session_id
            ] = [

                # User name memory
                types.Content(

                    role="user",

                    parts=[

                        types.Part.from_text(

                            text=(
                                f"My name is {user_name}. "
                                "Please remember my name."
                            )

                        )

                    ]

                ),


                # AI greeting
                types.Content(

                    role="model",

                    parts=[

                        types.Part.from_text(

                            text=(
                                f"Hello {user_name}! "
                                "I am KX Neural Core, "
                                "your EduNexus AI tutor. "
                                "How can I help you study today?"
                            )

                        )

                    ]

                )

            ]


        # ====================================================
        # ADD USER MESSAGE
        # ====================================================

        conversation_history[
            session_id
        ].append(

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
        # LIMIT MEMORY
        # ====================================================

        MAX_HISTORY = 12


        if len(
            conversation_history[
                session_id
            ]
        ) > MAX_HISTORY:

            conversation_history[
                session_id
            ] = conversation_history[
                session_id
            ][-MAX_HISTORY:]


        # ====================================================
        # TRY GEMINI KEYS
        # ====================================================

        last_error = None


        for index, client in enumerate(
            clients,
            start=1
        ):

            try:

                print(
                    f"[GEMINI] Trying key #{index}..."
                )


                # ------------------------------------------------
                # GENERATE RESPONSE
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
                # GET TEXT
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
                # SAVE RESPONSE
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
                    f"[SUCCESS] Gemini key #{index} worked."
                )


                print(
                    f"[MODEL] {MODEL_NAME}"
                )


                return jsonify({

                    "reply":
                        ai_response_text

                }), 200


            except Exception as e:

                last_error = e


                print("")
                print(
                    f"[KEY #{index} FAILED]"
                )

                print(
                    f"[ERROR TYPE] {type(e).__name__}"
                )

                print(
                    f"[ERROR] {str(e)}"
                )

                print("")


                # Try next key
                continue


        # ====================================================
        # ALL KEYS FAILED
        # ====================================================

        print("")
        print("==================================================")
        print("[ALL GEMINI KEYS FAILED]")
        print(f"[MODEL] {MODEL_NAME}")
        print(f"[ERROR] {last_error}")
        print("==================================================")
        print("")


        return jsonify({

            "reply":
                "KX Neural Core is temporarily unavailable. "
                "Please try again in a moment."

        }), 503


    # ========================================================
    # BACKEND ERROR
    # ========================================================

    except Exception as e:

        traceback.print_exc()


        return jsonify({

            "reply":
                "Backend Error. Please try again later."

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


    print("")
    print("==================================================")
    print("KX NEURAL CORE LIVE")
    print(f"PORT: {port}")
    print(f"MODEL: {MODEL_NAME}")
    print(f"GEMINI CLIENTS: {len(clients)}")
    print("==================================================")
    print("")


    app.run(

        host="0.0.0.0",

        port=port

    )
    
