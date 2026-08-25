import os
import time
import traceback
import requests

from flask import Flask, request, jsonify
from flask_cors import CORS

from google import genai
from google.genai import types


# ============================================================
# EDU NEXUS AI
# KX NEURAL CORE
# ============================================================

app = Flask(__name__)

CORS(
    app,
    resources={
        r"/*": {
            "origins": "*"
        }
    }
)


# ============================================================
# MODEL
# ============================================================

MODEL_NAME = "gemini-3.6-flash"


# ============================================================
# AI SYSTEM PROMPT
# ============================================================

SYSTEM_PROMPT = """
You are EduNexus AI, powered by the KX Neural Core.

You are a friendly, highly intelligent personal study assistant
for Indian Class 12 students.

Main subjects:
- Physics
- Chemistry
- Mathematics
- Computer Science
- English

Your goal is to help students understand concepts and prepare
for Class 12 examinations.

GENERAL RULES:

1. Use simple, exam-friendly language.
2. Be accurate and educational.
3. Keep normal answers concise.
4. Normally answer in around 3-8 short sentences or bullet points.
5. Do not unnecessarily write huge essays.
6. If the student asks for a detailed explanation, give a detailed answer.
7. For numerical problems, show the important calculation steps.
8. For definitions, give an exam-ready definition.
9. For comparisons, use clear bullet points or a table.
10. For programming questions, provide correct code and explain it simply.
11. If a student appears confused, explain the concept with a simple example.
12. Never claim that you performed an action that you did not perform.


CUSTOM QUIZ MODE:

When the student asks for a custom quiz, follow these rules STRICTLY.

1. Identify the subject and topic.
2. Follow the requested number of questions exactly.
3. If the student asks for MCQs, provide four options:
   A, B, C and D.
4. Provide ALL requested questions in the same response.
5. DO NOT reveal the answers immediately.
6. DO NOT provide explanations immediately.
7. End the quiz with:

   "Submit your answers in this format:
   1-A, 2-B, 3-C..."

8. Wait for the student's next message.
9. When the student submits answers, evaluate them.
10. Give:
    - Score
    - Total marks
    - Correct answers
    - Incorrect answers
    - Short explanations for mistakes
11. Do not restart the quiz unless the student asks for a new quiz.
12. Do not stop after only one question when multiple questions were requested.


CONVERSATION:

Remember useful context from the current conversation.
If the student gives their name, use it naturally.
Be encouraging but do not become overly verbose.
"""


# ============================================================
# DISCORD WEBHOOK
# ============================================================

# Put this in Render Environment Variables:
#
# DISCORD_WEBHOOK_URL=your_new_webhook
#
# NEVER put the actual webhook URL in source code.

DISCORD_WEBHOOK_URL = os.environ.get(
    "DISCORD_WEBHOOK_URL"
)


# ============================================================
# GEMINI API KEY POOL
# ============================================================

_raw_keys = [
    os.environ.get("GEMINI_API_KEY"),
    os.environ.get("GEMINI_API_KEY_2"),
    os.environ.get("GEMINI_API_KEY_3"),
]


api_keys = []

for key in _raw_keys:

    if key:

        clean_key = key.strip()

        if clean_key:
            api_keys.append(clean_key)


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
            f"[CLIENT INIT ERROR] {type(e).__name__}: {e}"
        )


# ============================================================
# CONVERSATION MEMORY
# ============================================================

conversation_history = {}


# ============================================================
# LIMITS
# ============================================================

MAX_HISTORY = 16

MAX_OUTPUT_TOKENS = 2000

MAX_RETRIES_PER_KEY = 2


# ============================================================
# STARTUP LOG
# ============================================================

print("")
print("==================================================")
print("        EDU NEXUS AI - KX NEURAL CORE")
print("==================================================")
print(f"[MODEL] {MODEL_NAME}")
print(f"[API KEYS LOADED] {len(clients)}")
print(
    "[DISCORD]",
    "CONFIGURED"
    if DISCORD_WEBHOOK_URL
    else "NOT CONFIGURED"
)
print("==================================================")
print("")


# ============================================================
# DISCORD ALERT
# ============================================================

def send_discord_alert(username):

    if not DISCORD_WEBHOOK_URL:

        print(
            "[DISCORD] Webhook not configured."
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


        if response.status_code in (200, 204):

            print(
                "[DISCORD] Alert sent successfully."
            )

        else:

            print(
                f"[DISCORD] Error {response.status_code}: "
                f"{response.text[:300]}"
            )


    except Exception as e:

        print(
            f"[DISCORD] Exception: {e}"
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
        "gemini_clients": len(clients)
    })


# ============================================================
# HEALTH
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
        # READ REQUEST
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
        ).strip()


        user_name = str(
            data.get(
                "user_name",
                "Student"
            )
        ).strip()


        # ----------------------------------------------------
        # VALIDATION
        # ----------------------------------------------------

        if not user_message:

            return jsonify({
                "success": False,
                "reply": "Please enter a message."
            }), 400


        if not clients:

            print(
                "[ERROR] No Gemini API keys configured."
            )

            # Return 200 so an existing frontend doesn't
            # incorrectly show "Server Connection Broken".

            return jsonify({
                "success": False,
                "reply": (
                    "KX Neural Core is not configured yet. "
                    "Please check the Gemini API key settings."
                )
            }), 200


        print("")
        print("==================================================")
        print("[CHAT REQUEST]")
        print(f"[USER] {user_name}")
        print(f"[SESSION] {session_id}")
        print(f"[MESSAGE] {user_message}")
        print("==================================================")


        # ====================================================
        # CREATE NEW SESSION
        # ====================================================

        if session_id not in conversation_history:

            print(
                f"[SESSION] New session: {session_id}"
            )


            send_discord_alert(
                user_name
            )


            conversation_history[
                session_id
            ] = [

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
        # KEEP HISTORY UNDER CONTROL
        # ====================================================

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
        # GEMINI KEY LOOP
        # ====================================================

        last_error = None


        for key_index, client in enumerate(
            clients,
            start=1
        ):


            # ------------------------------------------------
            # RETRY LOOP
            # ------------------------------------------------

            for attempt in range(
                1,
                MAX_RETRIES_PER_KEY + 1
            ):


                try:

                    print(
                        f"[GEMINI] Key #{key_index} "
                        f"| Attempt {attempt}"
                    )


                    # ========================================
                    # GENERATE CONTENT
                    # ========================================

                    response = client.models.generate_content(

                        model=MODEL_NAME,

                        contents=conversation_history[
                            session_id
                        ],

                        config=types.GenerateContentConfig(

                            system_instruction=SYSTEM_PROMPT,

                            max_output_tokens=MAX_OUTPUT_TOKENS

                        )

                    )


                    # ========================================
                    # EXTRACT RESPONSE
                    # ========================================

                    ai_response_text = (
                        response.text
                        if response.text
                        else ""
                    ).strip()


                    if not ai_response_text:

                        raise RuntimeError(
                            "Gemini returned an empty response."
                        )


                    # ========================================
                    # SAVE AI RESPONSE
                    # ========================================

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


                    # ========================================
                    # SUCCESS
                    # ========================================

                    print(
                        f"[SUCCESS] Key #{key_index} "
                        f"worked on attempt {attempt}."
                    )

                    print(
                        f"[MODEL] {MODEL_NAME}"
                    )

                    print("")


                    return jsonify({

                        "success": True,

                        "reply": ai_response_text,

                        "model": MODEL_NAME

                    }), 200


                except Exception as e:

                    last_error = e


                    error_text = str(e)


                    print("")
                    print(
                        f"[GEMINI ERROR] "
                        f"Key #{key_index}, "
                        f"Attempt {attempt}"
                    )

                    print(
                        f"[TYPE] {type(e).__name__}"
                    )

                    print(
                        f"[ERROR] {error_text}"
                    )

                    print("")


                    # ----------------------------------------
                    # If another attempt is available
                    # ----------------------------------------

                    if attempt < MAX_RETRIES_PER_KEY:

                        time.sleep(1)


            # ------------------------------------------------
            # Move to next API key
            # ------------------------------------------------

            print(
                f"[GEMINI] Moving from key #{key_index} "
                "to next key..."
            )


        # ====================================================
        # ALL KEYS FAILED
        # ====================================================

        print("")
        print("==================================================")
        print("[ALL GEMINI KEYS FAILED]")
        print(f"[MODEL] {MODEL_NAME}")
        print(f"[LAST ERROR] {last_error}")
        print("==================================================")
        print("")


        # IMPORTANT:
        # Return HTTP 200 so an existing frontend that treats
        # non-2xx responses as "Server Connection Broken"
        # doesn't show a misleading internet error.

        return jsonify({

            "success": False,

            "error": True,

            "reply": (
                "KX Neural Core could not complete that request "
                "right now. Please try again."
            ),

            "model": MODEL_NAME

        }), 200


    # ========================================================
    # BACKEND EXCEPTION
    # ========================================================

    except Exception as e:

        print("")
        print("==================================================")
        print("[BACKEND CRASH]")
        print("==================================================")

        traceback.print_exc()

        print("")


        # Again return JSON/200 to avoid misleading
        # "Server Connection Broken" messages in old frontend.

        return jsonify({

            "success": False,

            "error": True,

            "reply": (
                "KX Neural Core encountered a temporary error. "
                "Please try again."
            )

        }), 200


# ============================================================
# SERVER
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
