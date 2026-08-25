import os
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
from google import genai
from google.genai import types
from google.genai import errors as genai_errors

app = Flask(__name__)
CORS(app)

# [SYSTEM] Hide Webhook in Backend for Security
DISCORD_WEBHOOK_URL = "https://discordapp.com/api/webhooks/1540079598224809984/oDDtB_T22-8lQK3R1HLTk_L_1Fv6IW-atoHBjo7zq0Wc4BQpVr6Hor2ssAtH7RxXP_fA"

_raw_keys = [
    os.environ.get("GEMINI_API_KEY"),
    os.environ.get("GEMINI_API_KEY_2"),
    os.environ.get("GEMINI_API_KEY_3"),
]

clients = [genai.Client(api_key=k) for k in _raw_keys if k]

if not clients:
    raise RuntimeError("No GEMINI_API_KEY is set in the Environment Variables!")

MODEL_NAME = "gemini-2.5-flash"

SYSTEM_PROMPT = (
    "You are EduNexus AI, powered by the KX Neural Core, a friendly and extremely smart study assistant for Indian Class 12 students "
    "(Physics, Chemistry, Maths, Computer Science, English). "
    "Keep answers SHORT and clear by default -- around 3 to 6 short sentences, "
    "or a few bullet points. Do not write long essays. "
    "If the user asks for a Custom Quiz, act as a strict examiner, wait for their answers, "
    "evaluate them in the next turn, and give them a score out of the total questions. "
    "Use simple, exam-friendly language."
)

# [SYSTEM] KX Core Conversation Memory Store
conversation_history = {}

def send_discord_alert(username):
    """Securely sends login alerts to Discord from Backend"""
    try:
        data = {"content": f"🚨 **BINGO!** New User Logged In!\n🧑‍🎓 **Name:** {username}\n💻 **Action:** Launched EduNexus AI Dashboard 🚀"}
        requests.post(DISCORD_WEBHOOK_URL, json=data, timeout=5)
    except Exception as e:
        print(f"Discord Alert Failed: {e}")

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    user_message = data.get('message')
    session_id = data.get('session_id', 'default_session')
    user_name = data.get('user_name', 'Student')
    
    print(f"\n[USER QUERY RECEIVED from {user_name}]: {user_message}")

    # Track new user securely on backend based on first message
    if session_id not in conversation_history:
        send_discord_alert(user_name)
        # Initialize memory for new session
        conversation_history[session_id] = [{"role": "user", "parts": [{"text": f"My name is {user_name}. Please remember it."}]}, {"role": "model", "parts": [{"text": f"Hello {user_name}, I am KX Neural Core. I will remember your name and our conversation history."}]}]

    # Append new user message to memory
    conversation_history[session_id].append({"role": "user", "parts": [{"text": user_message}]})
    
    # Keep memory size manageable (last 10 interactions) to avoid token limits
    if len(conversation_history[session_id]) > 10:
        conversation_history[session_id] = conversation_history[session_id][-10:]

    last_error = None

    for i, client in enumerate(clients, start=1):
        try:
            # Pass the entire conversation history instead of just one message
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=conversation_history[session_id],
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    max_output_tokens=600,
                )
            )

            # Save AI's response to memory
            conversation_history[session_id].append({"role": "model", "parts": [{"text": response.text}]})
            
            print(f"[KX Neural Core] Reply sent using key #{i}")
            return jsonify({"reply": response.text})

        except genai_errors.ClientError as e:
            if getattr(e, "code", None) == 429:
                print(f"[QUOTA HIT on key #{i}] trying next key if available...")
                last_error = e
                continue
            print(f"[ERROR DETAILS]: {e}")
            return jsonify({"reply": "Oops! Something went wrong. Please try again later!"})

        except Exception as e:
            print(f"[ERROR DETAILS]: {e}")
            return jsonify({"reply": "Oops! The KX Neural Core is overloaded. Please try again later!"})

    print(f"[ALL KEYS EXHAUSTED]: {last_error}")
    return jsonify({
        "reply": "⏳ The KX Neural Core's free limit has been exhausted for today. Please try again tomorrow!"
    })

if __name__ == '__main__':
    print("--------------------------------------------------")
    print("[SYSTEM] KX Neural Core LIVE SERVER BOOTING...")
    print(f"[SYSTEM] {len(clients)} API key(s) loaded in the fallback pool")
    print("[SYSTEM] Ready to receive frontend requests with Memory enabled")
    print("--------------------------------------------------")
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
