import os
import requests
import traceback
from flask import Flask, request, jsonify
from flask_cors import CORS
from google import genai
from google.genai import types

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
    print("WARNING: Koi GEMINI_API_KEY set nahi hai!")

# 🔥 Naye SDK ke liye standard model string
MODEL_NAME = "gemini-1.5-flash"

SYSTEM_PROMPT = (
    "You are EduNexus AI, powered by the KX Neural Core, a friendly and extremely smart study assistant for Indian Class 12 students "
    "(Physics, Chemistry, Maths, Computer Science, English). "
    "Keep answers SHORT and clear by default -- around 3 to 6 short sentences, "
    "or a few bullet points. Do not write long essays. "
    "If the user asks for a Custom Quiz, act as a strict examiner, wait for their answers, "
    "evaluate them in the next turn, and give them a score out of the total questions. "
    "Use simple, exam-friendly language."
)

conversation_history = {}

def send_discord_alert(username):
    try:
        data = {"content": f"🚨 **BINGO!** New User Logged In!\n🧑‍🎓 **Name:** {username}\n💻 **Action:** Launched EduNexus AI Dashboard 🚀"}
        requests.post(DISCORD_WEBHOOK_URL, json=data, timeout=5)
    except Exception as e:
        print(f"Discord Alert Failed: {e}")

@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        user_message = data.get('message')
        session_id = data.get('session_id', 'default_session')
        user_name = data.get('user_name', 'Student')
        
        print(f"\n[USER QUERY RECEIVED from {user_name}]: {user_message}")

        if session_id not in conversation_history:
            send_discord_alert(user_name)
            conversation_history[session_id] = [
                types.Content(role="user", parts=[types.Part.from_text(text=f"My name is {user_name}. Please remember it.")]),
                types.Content(role="model", parts=[types.Part.from_text(text=f"Hello {user_name}, I am KX Neural Core. I will remember your name and our conversation history.")])
            ]

        conversation_history[session_id].append(
            types.Content(role="user", parts=[types.Part.from_text(text=user_message)])
        )
        
        if len(conversation_history[session_id]) > 10:
            conversation_history[session_id] = conversation_history[session_id][-10:]
            if conversation_history[session_id][0].role == "model":
                conversation_history[session_id] = conversation_history[session_id][1:]

        last_error = None

        for i, client in enumerate(clients, start=1):
            try:
                # 🔥 Clean generate content call compatible with new google-genai library
                response = client.models.generate_content(
                    model=MODEL_NAME,
                    contents=conversation_history[session_id],
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT,
                        max_output_tokens=600,
                    )
                )

                ai_response_text = response.text if response.text else "I could not process that request."
                conversation_history[session_id].append(
                    types.Content(role="model", parts=[types.Part.from_text(text=ai_response_text)])
                )
                
                print(f"[KX Neural Core] Reply sent using key #{i}")
                return jsonify({"reply": ai_response_text})

            except Exception as e:
                print(f"[KEY #{i} ERROR]: {e}")
                last_error = e
                continue

        print(f"[ALL KEYS FAILED]: {last_error}")
        return jsonify({
            "reply": f"API Connection Error: {str(last_error)}"
        })
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({"reply": f"Backend Crash: {str(e)}"}), 200

if __name__ == '__main__':
    print("--------------------------------------------------")
    print("[SYSTEM] KX Neural Core LIVE SERVER BOOTING...")
    print(f"[SYSTEM] Selected Model: {MODEL_NAME}")
    print("--------------------------------------------------")
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
